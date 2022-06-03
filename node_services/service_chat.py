#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import os
import json

class ServiceRunning(ReconnectingNodeConsumer):
    CHAT_CLIENTS_STAT_PATH='node_data/chat_stat.file'
    _chat_clients_list={}

    def _initnode(self):
        super()._initnode()
        #chat client stat updated from file
        if os.path.isfile(self.CHAT_CLIENTS_STAT_PATH):
            with open(self.CHAT_CLIENTS_STAT_PATH, 'r') as cc_file:
                self._chat_clients_list=json.load(cc_file)
        self.LOGGER.info("INITALISATION chat service done")
 
        
    def _msg_process(self, msg, hdrs):

        if len(hdrs['dest_IP'])>6 and hdrs['dest_IP'] != self._own_IP:
            # dest IP known, forward to node with the IP
            IP=hdrs['dest_IP']
            self._msgs_to_send.append([msg, hdrs, IP, 'L3'])
            self.LOGGER.info("CHAT msg "+msg['uid']+" forwarded to "+IP)
            
        elif (hdrs['dest_all'] == 'clients' or hdrs['dest_uid'].startswith('client_')):
            # check nb of hop
            willhop= False
            if msg.get('hop') is None:
                willhop=True
                msg['hop']=1
            elif msg.get('hop') < 1: # hop only once:
                willhop=True
                msg['hop']=msg['hop']+1
            else:
                willhop=False
                self.LOGGER.info("CHAT msg "+msg['uid']+" is discarded by node, hop: "+str(msg['hop']))
                
            if willhop:
                # send to all nodes with chat service
                # nodes_cs=[n for n in self._nodeslist if n['services']['chat'] == 1] Replaced by iteration loop to avoid errors
                nodes_cs=[]
                for n in self._nodeslist:
                    if 'services' in n:
                        if 'chat' in n['services']:
                            if (n['services']['chat'] == 1):
                                nodes_cs.append(n)
                self.LOGGER.info("CHAT broadcast msg "+msg['uid']+" will be forwarded to: "+str(len(nodes_cs))+" nodes.")
                for n in nodes_cs:
                    if 'IP_address' in n:
                        if n['IP_address'] != self._own_IP:
                            self._msgs_to_send.append([msg, hdrs, n['IP_address'], 'L3'])
                                 
##        elif hdrs['dest_uid'].startswith('client_'): NOT NEEDED IF CLIENTS HAVE TO ONLY CONNECT TO NODES WITH CHAT SERVICE
##            # if dest was connected to the node he would have received the msg,
##            # thus check if client IP is known and it is not ours
##            if hdrs['dest_uid'] in self._chat_clients_list.keys():
##                IP= self._chat_clients_list[hdrs['dest_uid']]
##                if len(IP)>6 and IP != self._own_IP:
##                    #self._msgs_to_send.append([msg, hdrs, IP, 'L3']) 
##                    self.LOGGER.info("CHAT msg "+msg['uid']+" forwarded to last known IP: "+IP)
        else:
            self.LOGGER.info("CHAT msg "+msg['uid']+" is discarded by node.")

        # Update list of chat clients
        if str(hdrs['sender_uid']) in list(self._chat_clients_list.keys()):
            self._chat_clients_list[hdrs['sender_uid']]=self._chat_clients_list[hdrs['sender_uid']]+1
        else:
            self._chat_clients_list[hdrs['sender_uid']]=1
        return True

    def _ticking_actions(self):
        super()._ticking_actions()

        #write chat stats to file
        with open(self.CHAT_CLIENTS_STAT_PATH, 'w') as chat_file:
            chat_file.write(json.dumps(self._chat_clients_list))

        self._stat_updateDB()        
        return

    def _stat_updateDB(self):
        # Determine total sum of messages processed
        tot=0
        for cc in self._chat_clients_list.keys():
            tot=tot+self._chat_clients_list[cc]
        db_query = { 'uid': self._uid }
        db_values_toset = {'$set':{'service_chat':{'nb_of_msg_processed': tot}}}
        # Write to DB
        self._updateDB('nodes', db_query, db_values_toset, False)
        self.LOGGER.debug("Node information updated on DB, IP = " + str(db_values_toset))

#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2:
        if (sys.argv[1] == 'L3'):
            nodelevel=sys.argv[1]
            
            # Create Instance and start the service
            consumer = ServiceRunning(nodelevel, 'chat')
            consumer.run()
    else:
        print("The 'chat' service only works on L3")
        exit()
        
if __name__ == '__main__':
    main()
