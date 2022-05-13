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

class ServiceRunning(ReconnectingNodeConsumer):
    
    def _msg_process(self, msg, hdrs):
        super()._msg_process(msg, hdrs)
        self.LOGGER.info("Entered extended msg process method")
        return True

    def _initnode(self):
        self._check_IP()
        # Update list of nodes in the actual and lower layer and save files
        self._nodeslist = self._update_nodeslist(self._nodeslist, self._nodelevel)
        self._nodeslist_lower = self._update_lowerlayer_nodeslist()
        with open(self.NODESLIST_PATH, 'w') as nodes_file:
            nodes_file.write(json.dumps(self._nodeslist))
        with open(self.NODESLIST_LOWER_PATH, 'w') as nodes_file:
            nodes_file.write(json.dumps(self._nodeslist_lower))

        # Maintain network structure    
        self._net_check()
    
        self.LOGGER.info("INITALISATION net_maintenance done")
        super()._initnode()
        
    def _check_IP(self):
        # Check own IP and save into a file
        own_ip = requests.get('https://api.ipify.org', timeout=self.REQ_TIMEOUT).text
        if len(own_ip)>15:
            own_ip= requests.get('https://ident.me').text
        self._own_IP=own_ip
        with open(self.IP_PATH, 'w') as ip_file:
            ip_file.write(self._own_IP)
            self.LOGGER.info("IP determined as being: "+self._own_IP)
            
    def _ticking_actions(self):
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
        self._net_check() 

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
                return nodeslist

        # Select a node
        IP_sel=''
        if nodeslist_empty:
            # select randomly from the default nodes
            IP_sel=random.choice(defaultnodesIP)
        else:
            # Select randomly from the existing list of nodes
            nodes_ns=[n for n in nodeslist if n['services']['net_storage'] == 1]
            if len(nodes_ns) == 0:
                self.LOGGER.warning("ERROR! No nodes with net_storage service are available! will retry at next ticking.")
                return nodeslist
            random.shuffle(nodes_ns)
            IP_sel=nodes_ns[0]['IP_address']

        try:    
            # query the list of nodes from DB
            db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
            with pymongo.MongoClient(db_url) as db_client:
                at_db = db_client["AnuuTechDB"]
                nodes_col = at_db["nodes"]
                #service_str='services.'+self._service
                #db_query = { "level": nodelevel, service_str:0} query for only one service type
                db_query = { "level": nodelevel}
                db_filter = {"IP_address":1, "uid":1, "_id":0, "services":1}
                nodeslist=list(nodes_col.find(db_query, db_filter).max_time_ms(5000))
                if len(nodeslist) == 0:
                    self.LOGGER.info("while updating nodes list of "+nodelevel+", DB access works but no input in DB received back!")
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
    
    def _net_check(self):
        # Create/Update infos on AnuuTechDB
        # Prepare query in good format
        pem = self._PUBKEY.exportKey('PEM')
        db_query = { "uid": self._uid }
        db_values_toset = {"$set":{"pubkey": pem, "level": self._nodelevel, "last_view" : time.time(),
                                   "platform": platform.system(), "platform_version": platform.version(),
                                   "platform_release": platform.release(),# does not work: "cpu_maxspeed_MhZ": psutil.cpu_freq()[2],
                                   "cpu_avg_usage_percent": (psutil.getloadavg()[0]/ psutil.cpu_count() * 100),
                                   "mem_total": psutil.virtual_memory()[0], "mem_percent_used": psutil.virtual_memory()[2],
                                   "disk_total": psutil.disk_usage('/')[0], "disk_percent_used": psutil.disk_usage('/')[3],
                                   "IP_address": self._own_IP, "SW_version": self.SW_VERSION}}
        self._updateDB('nodes', db_query, db_values_toset)
        # Additional update
        serv_list={}
        with open(self.SERVICES_PATH, 'r') as serv_file:
            serv_list=json.load(serv_file)
        db_values_toset2 = {"$set":{"services":serv_list}}
        self._updateDB('nodes', db_query, db_values_toset2)

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
