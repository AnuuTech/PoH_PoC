#import class_service
from service_class import ReconnectingNodeConsumer
import settings as S
import os
import sys
import time
import platform
import psutil
import requests
import json
import pika
import threading
from filelock import FileLock

class ServiceRunning(ReconnectingNodeConsumer):
    
    def _msg_process(self, msg, hdrs):
        # Get a node on lower layer node with corresponding service
        if self._nodelevel == 'L3' and len(hdrs['service_forward'])>0 :
            # get a random node from lower layer
            IP_sel=self._get_rand_nodeIP(hdrs['service_forward'], self._nodeslist_lower, '')
            if len(IP_sel) > 6:
                hdrs['service']=hdrs['service_forward']
                hdrs['service_forward']=''
                self._msgs_to_send.append([msg, hdrs, IP_sel, 'L2'])
                self.LOGGER.info("msg "+msg['uid']+" forwarded to node with service: "+ hdrs['service_forward']+" on node "+IP_sel)

        # Get request nodeslist
        if msg.get('type')=='REQUEST_NODESLIST':
            # prepare the msg to be sent
            headers=self._initheaders()
            headers['service']='net_maintenance'
            headers['dest_IP']=hdrs['sender_node_IP']
            msgback=self._initmsg()
            msgback['type']='NODESLIST'
            msgback['content']['nodeslist']=self._nodeslist
            msgback['content']['level']=self._nodelevel
            self._msgs_to_send.append([msgback, headers, hdrs['sender_node_IP'], msg['content']])#incoming msg content was containing node level!

        # Update with received nodeslist
        if msg.get('type')=='NODESLIST':
            if msg['content']['level'] == self._nodelevel:
                self._nodeslist=self._update_nodeslist(msg['content']['nodeslist'], self._nodeslist)
            elif int(msg['content']['level'][1]) == int(self._nodelevel[1])-1:
                self._nodeslist_lower=self._update_nodeslist(msg['content']['nodeslist'], self._nodeslist_lower)
            elif int(msg['content']['level'][1]) == int(self._nodelevel[1])+1:
                self._nodeslist_upper=self._update_nodeslist(msg['content']['nodeslist'], self._nodeslist_upper)

        return True

    def _initnode(self):
        self._node_tick_interval=20
        self._exchange_check() # ensure exchange exists as soon as possible to allow other services starting correctly
        self._check_IP()

        #send and request nodeslist to/from other nodes
        self._sandr_nodeslists()

        self.LOGGER.info("INITALISATION net_maintenance done")
        super()._initnode()
            
    def _ticking_actions(self):
        self.LOGGER.debug("Threads number: "+str(threading.activeCount()))
        #super()._ticking_actions() on purpose commented, since net_maintenance is updating the nodeslists.
        self._stats_update() # because it is in super().ticking_actions()

        #send and request nodeslist to/from other nodes
        self._sandr_nodeslists()
        
        self._check_IP()
        
        #write nodeslists into files
        with FileLock(S.NODESLIST_PATH+'.lock', timeout=1):
            with open(S.NODESLIST_PATH, 'w') as nodes_file:
                nodes_file.write(json.dumps(self._nodeslist))
        with FileLock(S.NODESLIST_LOWER_PATH+'.lock', timeout=1):
            with open(S.NODESLIST_LOWER_PATH, 'w') as nodes_file:
                nodes_file.write(json.dumps(self._nodeslist_lower))
        with FileLock(S.NODESLIST_UPPER_PATH+'.lock', timeout=1):
            with open(S.NODESLIST_UPPER_PATH, 'w') as nodes_file:
                nodes_file.write(json.dumps(self._nodeslist_upper))

        # Ensure exchange is working
        self._exchange_check()

        # Check nodes list
        self._nodeslist=self._check_nodes(self._nodeslist)
        self._nodeslist_lower=self._check_nodes(self._nodeslist_lower)
        self._nodeslist_upper=self._check_nodes(self._nodeslist_upper)
 
    def _check_IP(self):
        # Check own IP and save into a file
        own_ip=''
        try:
            own_ip = requests.get('https://api.ipify.org', timeout=S.REQ_TIMEOUT).text
        except:
            self.LOGGER.info("WARNING! Impossible to api ipify: " + str(sys.exc_info()[0]))
            try:
                own_ip= requests.get('https://ident.me').text
            except:
                self.LOGGER.info("WARNING! Impossible to identme: " + str(sys.exc_info()[0]))
        if len(own_ip)>6:
            self._own_IP=own_ip
            with FileLock(S.IP_PATH+'.lock', timeout=1):
                with open(S.IP_PATH, 'w') as ip_file:
                    ip_file.write(self._own_IP)
                self.LOGGER.info("IP determined as being: "+self._own_IP)
        else:
            self.LOGGER.warning("WARNING! Impossible to get own IP")
            
    def _sandr_nodeslists(self):
        # SEND NODESLIST REQUESTS TO UPPER AND LOWER LAYER
        # prepare the msg to be sent
        headers=self._initheaders()
        headers['service']='net_maintenance'
        msg=self._initmsg()
        msg['type']='REQUEST_NODESLIST'
        msg['content']=self._nodelevel

        # Upper layer
        if self._nodelevel != 'L3':
            upper_level='L'+str(int(self._nodelevel[1])+1)
            IP_sel=''
            # get a random node from upper layer
            if len(self._nodeslist_upper) > 0:
                IP_sel=self._get_rand_nodeIP('net_maintenance', self._nodeslist_upper, '') #net maintenance service is on all nodes
            else: # if no nodes, get default ones
                IP_def_list=self._get_default_IPs(upper_level)
                if len(IP_def_list)>0:
                    IP_sel=IP_def_list[0]
            if len(IP_sel)>6:
                headers['dest_IP']=IP_sel
                self._msgs_to_send.append([msg, headers, IP_sel, upper_level])
                self.LOGGER.info("Net maintenance, upper nodeslist requested to: "+str(IP_sel))
            else:
                self.LOGGER.info("Net maintenance, no upper nodeslist found!")

        # Lower layer
        if self._nodelevel != 'L1':
            lower_level='L'+str(int(self._nodelevel[1])-1)
            IP_sel=''
            # get a random node from upper layer
            if len(self._nodeslist_lower) > 0:
                IP_sel=self._get_rand_nodeIP('net_maintenance', self._nodeslist_lower, '') #net maintenance service is on all nodes
            else: # if no nodes, get default ones
                IP_def_list=self._get_default_IPs(lower_level)
                if len(IP_def_list)>0:
                    IP_sel=IP_def_list[0]
            if len(IP_sel)>6:
                headers['dest_IP']=IP_sel
                self._msgs_to_send.append([msg, headers, IP_sel, lower_level])
                self.LOGGER.info("Net maintenance, lower nodeslist requested to: "+str(IP_sel))
            else:
                self.LOGGER.info("Net maintenance, no lower nodeslist found!")
            
        # SEND NODESLIST TO ALL NODES AT SAME LAYER
        IPs=[]
        # if no nodes, get default ones
        if len(self._nodeslist) <= 1: # excluding itself
            IPs=self._get_default_IPs(self._nodelevel)

        # update node info
        self._nodeslist[self._uid]=self._get_nodeinfo()

        # prepare the msg to be sent
        msg=self._initmsg()
        msg['type']='NODESLIST'
        msg['content']['nodeslist']=self._nodeslist
        msg['content']['level']=self._nodelevel

        #send to all nodes of current level
        if len(IPs)>0:
            for ip in IPs:
                if ip != self._own_IP:
                    headers['dest_IP']=ip
                    self._msgs_to_send.append([msg, headers, ip, self._nodelevel])
            self.LOGGER.info("Net maintenance, nodeslist shared with default : "+str(len(IPs))+" nodes.")
        else:
            for nk in self._nodeslist.keys():
                if 'IP_address' in self._nodeslist[nk]:
                    if self._nodeslist[nk]['IP_address'] != self._own_IP:
                        headers['dest_IP']=self._nodeslist[nk]['IP_address']
                        self._msgs_to_send.append([msg, headers, self._nodeslist[nk]['IP_address'], self._nodelevel])
            self.LOGGER.info("Net maintenance, nodeslist shared with : "+str(len(self._nodeslist)-1)+" nodes.")

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
            
    def _check_nodes(self, nodeslist):
        # check if some nodes are not responding anymore (at node level)
        nodes_down=[]
        for nk in nodeslist.keys():
            if 'last_view' in nodeslist[nk]:
                if (time.time()-nodeslist[nk]['last_view'])> S.NODE_DOWNTIME_LIMIT:
                    nodes_down.append(nk)
            else:
                nodes_down.append(nk)# add to delete because node does not have a last view
            
        # delete nodes down from own list
        for nk in nodes_down:
            nodeslist.pop(nk)
            self.LOGGER.info("Deleted node "+nk+" from own list, not responding for more than " + str(S.NODE_DOWNTIME_LIMIT)+"s")

        return nodeslist

    def _update_nodeslist(self, newlist, nodeslist):
        for nk in newlist.keys():
            if nk not in nodeslist.keys(): # node not existing yet -> put in
                nodeslist[nk]=newlist[nk]
            else: # only update if more recent data
                if 'last_view' in nodeslist[nk] and 'last_view' in newlist[nk]:
                    if newlist[nk]['last_view'] > nodeslist[nk]['last_view']:
                        nodeslist[nk]=newlist[nk]
        return nodeslist
        
    def _get_nodeinfo(self):
        # Update infos of node
        values = {'pubkey': self._pubkey.exportKey('PEM').decode(), 'level': self._nodelevel,
                  'last_view' : time.time(), 'platform': platform.system(), 'platform_version': platform.version(),
                  'platform_release': platform.release(),# does not work: 'cpu_maxspeed_MhZ': psutil.cpu_freq()[2],
                  'cpu_avg_usage_percent': (psutil.getloadavg()[0]/ psutil.cpu_count() * 100),
                  'mem_total': psutil.virtual_memory()[0], 'mem_percent_used': psutil.virtual_memory()[2],
                  'disk_total': psutil.disk_usage('/')[0], 'disk_percent_used': psutil.disk_usage('/')[3],
                  'IP_address': self._own_IP, 'SW_version': S.SW_VERSION, 'services':self._nodeservices}
        # load all services stats
        for ser in self._nodeservices.keys():
            if self._nodeservices[ser] == 1:
                # Service stats loaded from file
                service_stats_path=S.SERVICES_STATS_PATH+ser+S.SERVICES_STATS_PATHEND
                if os.path.isfile(service_stats_path):
                    with FileLock(service_stats_path+'.lock', timeout=1):
                        with open(service_stats_path, 'r') as stat_file:
                            stats=json.load(stat_file)
                    tot=0
                    for st in stats.keys():
                        tot=tot+stats[st]
                    values['service_'+ser]={'nb_of_msg_processed': tot}

        return values


#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2 and (sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3') :
        nodelevel=sys.argv[1]
        # Create Instance and start the service
        consumer = ServiceRunning(nodelevel, 'net_maintenance')
        consumer.run()
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
