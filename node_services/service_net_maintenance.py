#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import time
import platform
import psutil
import pymongo
import requests
import json
import socket
import random
import urllib
import pika
import threading

class ServiceRunning(ReconnectingNodeConsumer):
    _NODE_DOWNTIME_LIMIT=900 #in seconds
    
    def _msg_process(self, msg, hdrs):
        # Get a node on lower layer node with corresponding service
        if self._nodelevel == 'L3' and (hdrs['service'] == 'data_storage' or hdrs['service'] == 'next_service_to_be_implemented') :
            nodes_cs=[]
            for n in self._nodeslist_lower:
                if 'services' in n:
                    if hdrs['service'] in n['services']:
                        if n['services'][hdrs['service']] == 1:
                            nodes_cs.append(n)
            random.shuffle(nodes_cs)
            if len(nodes_cs) == 0:
                self.LOGGER.warning("No node with service "+ hdrs['service']+" is available, impossible to forward msg "+msg['uid']+"!")
            else:
                if 'IP_address' in nodes_cs[0]:
                    self._msgs_to_send.append([msg, hdrs, nodes_cs[0]['IP_address'], 'L2'])
                    self.LOGGER.info("msg "+msg['uid']+" forwarded to node with service: "+ hdrs['service']+" on node "+nodes_cs[0]['IP_address'])
                else:
                    self.LOGGER.warning("One L2 node has no IP set! Impossible to forward "+ hdrs['service']+" msg!") 
        return True

    def _initnode(self):
        self.NODE_TICK_INTERVAL=20.0
        self._exchange_check() # ensure exchange exists as soon as possible to allow other services starting correctly
        self._check_IP()
        # Update list of nodes in the actual and lower layer and save files
        updated=self._update_nodeslist(self._nodeslist, self._nodelevel)
        if updated is not None:
            self._nodeslist = updated
        updated_low = self._update_lowerlayer_nodeslist()
        if updated_low is not None:
            self._nodeslist_lower = updated_low
        with open(self.NODESLIST_PATH, 'w') as nodes_file:
            nodes_file.write(json.dumps(self._nodeslist))
        with open(self.NODESLIST_LOWER_PATH, 'w') as nodes_file:
            nodes_file.write(json.dumps(self._nodeslist_lower))

        # Update info to DB  
        self._nodeinfo_to_DB()

        self.LOGGER.info("INITALISATION net_maintenance done")
        super()._initnode()

    def _get_headers_arg(self): # Override to listen to other services to forward corresponding messages
        argum={'x-match': 'any', 'service': 'data_storage'}
        return argum
        
    def _check_IP(self):
        # Check own IP and save into a file
        own_ip=''
        try:
            own_ip = requests.get('https://api.ipify.org', timeout=self.REQ_TIMEOUT).text
        except:
            self.LOGGER.info("WARNING! Impossible to api ipify: " + str(sys.exc_info()[0]))
            try:
                own_ip= requests.get('https://ident.me').text
            except:
                self.LOGGER.info("WARNING! Impossible to identme: " + str(sys.exc_info()[0]))
        if len(own_ip)>6:
            self._own_IP=own_ip
            with open(self.IP_PATH, 'w') as ip_file:
                ip_file.write(self._own_IP)
                self.LOGGER.info("IP determined as being: "+self._own_IP)
        else:
            self.LOGGER.warning("WARNING! Impossible to get own IP")
            
    def _ticking_actions(self):
        self.LOGGER.debug("Threads number: "+str(threading.activeCount()))
        #super()._ticking_actions()
        self._check_IP()
        #update nodeslists
        updated=self._update_nodeslist(self._nodeslist, self._nodelevel)
        if updated is not None:
            self._nodeslist = updated
        updated_low = self._update_lowerlayer_nodeslist()
        if updated_low is not None:
            self._nodeslist_lower = updated_low
        #write nodeslists into files
        with open(self.NODESLIST_PATH, 'w') as nodes_file:
            nodes_file.write(json.dumps(self._nodeslist))
        with open(self.NODESLIST_LOWER_PATH, 'w') as nodes_file:
            nodes_file.write(json.dumps(self._nodeslist_lower))

        # Update info to DB and ensure exchange is working
        self._nodeinfo_to_DB()
        self._exchange_check()

    def _update_nodeslist(self, nodeslist, nodelevel):     
        # populate with default nodes if existing nodeslist is empty
        nodeslist_empty = False
        if len(nodeslist) == 0:
            nodeslist_empty=True
            defaultnodesIP=[]
            defaultnodes_hosts=['at-cluster'+nodelevel+self.ii_helper('node_data/access.bin', '8'),
                      'at-cluster'+nodelevel+'b'+self.ii_helper('node_data/access.bin', '8')]
            for dlh in defaultnodes_hosts:
                try:
                    defaultnodesIP.append(socket.gethostbyname(dlh))
                    self.LOGGER.info('Defaultnode obtained: '+ socket.gethostbyname(dlh) )
                except:
                    self.LOGGER.info("WARNING! Impossible to get one of the default node: " + dlh+ str(sys.exc_info()[0]))
            if len(defaultnodesIP) == 0:
                self.LOGGER.warning("ERROR! Impossible to get any default node... will retry at next ticking.")
                return

        # Select a node
        IP_sel=''
        if nodeslist_empty:
            # select randomly from the default nodes
            IP_sel=random.choice(defaultnodesIP)
        else:
            # Select randomly from the existing list of nodes
            # nodes_ns=[n for n in nodeslist if n['services']['net_storage'] == 1] Replaced by iteration loop to avoid errors
            nodes_ns=[]
            for n in nodeslist:
                if 'services' in n:
                    if 'net_storage' in n['services']:
                        if n['services']['net_storage'] == 1:
                            nodes_ns.append(n)
            if len(nodes_ns) == 0:
                self.LOGGER.warning("ERROR! No nodes with net_storage service at "+nodelevel+" are available! will retry at next ticking.")
                # force to re-use the default nodes
                if self._nodelevel == nodelevel:
                    self._nodeslist={}
                else:
                    self._nodeslist.lower={}
                return
            random.shuffle(nodes_ns)
            if 'IP_address' in nodes_ns[0]:
                IP_sel=nodes_ns[0]['IP_address']

        try:    
            # query the list of nodes from DB 
            db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
            with pymongo.MongoClient(db_url) as db_client:
                at_db = db_client['AnuuTechDB']
                nodes_col = at_db['nodes']
                #service_str='services.'+self._service
                #db_query = { 'level': nodelevel, service_str:0} query for only one service type
                db_query = { 'level': nodelevel}
                db_filter = {'IP_address':1, 'uid':1, '_id':0, 'services':1, 'last_view':1}
                nodeslist=list(nodes_col.find(db_query, db_filter))
                # check if some nodes are not responding anymore (at node level)
                if nodelevel == self._nodelevel:
                    #nodes_down=[n for n in nodeslist if (time.time()-n['last_view']) > self._NODE_DOWNTIME_LIMIT] Replaced by iteration loop to avoir errors
                    nodes_down=[]
                    for n in nodeslist:
                        if 'last_view' in n:
                            if (time.time()-n['last_view'])> self._NODE_DOWNTIME_LIMIT:
                                nodes_down.append(n)
                        else:
                            nodes_down.append(n)# add to delete because node does not have a last view
                    # delete nodes down from DB # TODO restrict process to delete nodes
                    for n in nodes_down:
                        if 'uid' in n:
                            db_query = { 'uid': n['uid']}
                            nodes_col.delete_many(db_query) # usage of delete_many instead of delete_one to delete duplciate if any
                            self.LOGGER.info("Deleted node "+n['uid']+" from DB, not responding for more than " + str(self._NODE_DOWNTIME_LIMIT)+"s")
                        else:
                            self.LOGGER.info("Impossible to delete node, no uid exists!")
                    # update nodeslist
                    nodeslist=[n for n in nodeslist if n not in nodes_down]
            if len(nodeslist) == 0:
                self.LOGGER.info("while updating nodes list of "+nodelevel+", DB access works but no valid nodes have been found!")
            else:
                # update nodes list
                self.LOGGER.info("The list of nodes in the layer "+nodelevel+" has been updated: " + str(nodeslist))
        except:
            self.LOGGER.warning("WARNING! Impossible to reach the DB on "+str(IP_sel)+" "+ str(sys.exc_info()[0]))
        return nodeslist

    def _update_lowerlayer_nodeslist(self):
        if self._nodelevel == 'L3':
            lname='L2'
        elif self._nodelevel == 'L2':
            lname='L1'
        else:
            return
        return self._update_nodeslist(self._nodeslist_lower, lname)
    
    def _nodeinfo_to_DB(self):
        # Create/Update infos on AnuuTechDB
        # Prepare query in good format
        pem = self._PUBKEY.exportKey('PEM').decode()
        db_query = { 'uid': self._uid }
        db_values_toset = {'$set':{'pubkey': pem, 'level': self._nodelevel, 'last_view' : time.time(),
                                   'platform': platform.system(), 'platform_version': platform.version(),
                                   'platform_release': platform.release(),# does not work: 'cpu_maxspeed_MhZ': psutil.cpu_freq()[2],
                                   'cpu_avg_usage_percent': (psutil.getloadavg()[0]/ psutil.cpu_count() * 100),
                                   'mem_total': psutil.virtual_memory()[0], 'mem_percent_used': psutil.virtual_memory()[2],
                                   'disk_total': psutil.disk_usage('/')[0], 'disk_percent_used': psutil.disk_usage('/')[3],
                                   'IP_address': self._own_IP, 'SW_version': self.SW_VERSION, 'services':self._nodeservices}}
        self._updateDB('nodes', db_query, db_values_toset, False)

    def _exchange_check(self):
        # Ensure local exchange exists
        try:
            connection = pika.BlockingConnection(self._pikaconn_parameters)
            channel=connection.channel()
    
            # main exchange
            exname_i='%s_main_exchange' %self._nodelevel
            channel.exchange_declare(exchange=exname_i,exchange_type='headers')

            #Close the connection
            connection.close()
            
        except pika.exceptions.AMQPConnectionError as err:
            logmsg=str("Impossible to create the initial connection for exchange!".format(err))
            self.LOGGER.critical(logmsg)


#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            nodelevel=sys.argv[1]

            # Create Instance and start the service
            consumer = ServiceRunning(nodelevel, 'net_maintenance')
            consumer.run()
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
