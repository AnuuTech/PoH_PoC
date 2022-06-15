#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import os
import json

class ServiceRunning(ReconnectingNodeConsumer):
        
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
                j=0
                for nk in self._nodeslist.keys():
                    if 'services' in self._nodeslist[nk]:
                        if 'chat' in self._nodeslist[nk]['services']:
                            if (self._nodeslist[nk]['services']['chat'] == 1):
                                if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                                    hdrs['dest_IP']=self._nodeslist[nk]['IP_address']
                                    self._msgs_to_send.append([msg, hdrs, self._nodeslist[nk]['IP_address'], 'L3'])
                                    j=j+1
                self.LOGGER.info("CHAT broadcast msg "+msg['uid']+" will be forwarded to: "+str(j)+" nodes.")

                                 
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

        return True


#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2 and (sys.argv[1] == 'L3'):
        nodelevel=sys.argv[1]
        # Create Instance and start the service
        consumer = ServiceRunning(nodelevel, 'chat')
        consumer.run()
    else:
        print("The 'chat' service only works on L3.")
        exit()
        
if __name__ == '__main__':
    main()
