#import class_service
from service_class import ReconnectingNodeConsumer
import settings as S
import sys
import os
import json
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
import binascii
import time
import random

class ServiceRunning(ReconnectingNodeConsumer):
    _all_files={} # node_uid with corresponding list of files(hashes)

    def _initnode(self):
        super()._initnode()

        #Ensure data storage directory exists
        if not os.path.exists(S.DATA_STORAGE_PATH):
            os.makedirs(S.DATA_STORAGE_PATH)

        self.LOGGER.info("INITALISATION data storage service done")
 
    def _msg_process(self, msg, hdrs):

        # First CHECK FEE is paid and correct
        if msg.get('type') == 'SAVE_DATA' :
            if not self._check_fee(msg, hdrs, S.FEE_DATASTORAGE, self.ii_helper('node_data/access.bin', '18')):
                # Message is thus not processed
                return True

        if (msg.get('type')=='SAVE_DATA' or msg.get('type')=='SAVE_DATA_REPLICATE'): #and hdrs.get('dest_uid') == self._uid):
            # Hash file content
            file_hash=binascii.hexlify((SHA256.new(json.dumps(msg['content']).encode())).digest()).decode()

            # Save file locally using hash as filename
            data_path=S.DATA_STORAGE_PATH+str(file_hash)
            with open(data_path, 'w') as data_file:
                data_file.write(json.dumps(msg['content']))

            # Inform client of saved data
            hdrs_cli=hdrs.copy()
            hdrs_cli['dest_uid']=hdrs.get('sender_uid')
            hdrs_cli['dest_IP']=hdrs.get('sender_node_IP')
            #hiding IP of level 1/2 nodes
            hdrs_cli['sender_node_IP']=''
            hdrs_cli['sender_uid']=self._uid
            msgback=self._initmsg()
            msgback['uid']=msg['uid'] #keeps the same id so that the client knows which file it was
            msgback['type']='DATA_SAVED'
            msgback['content']=file_hash
            self.LOGGER.info("Data storage sends back confirmation msg "+str(msgback['uid'])+" " +str(hdrs_cli))
            self._msgs_to_send.append([msgback, hdrs_cli, hdrs_cli['dest_IP'], 'L3'])


            if msg.get('type') == 'SAVE_DATA':
                # Send file to other nodes, up to min number of replica
                msg['type']='SAVE_DATA_REPLICATE'
                # Get nodes with corresponding service
                nodes_cs={}
                for nk in self._nodeslist.keys():
                    if 'services' in self._nodeslist[nk]:
                        if 'data_storage' in self._nodeslist[nk]['services']:
                            if self._nodeslist[nk]['services']['data_storage'] == 1:
                                nodes_cs[nk]=self._nodeslist[nk]
                ns_keys=list(nodes_cs.keys())
                random.shuffle(ns_keys)
                if len(nodes_cs) == 0:
                    self.LOGGER.warning("No node with service data storage is available, impossible to replicate msg "+msg['uid']+"!")
                else:
                    sent=0
                    for ns_key in ns_keys: 
                        if 'IP_address' in nodes_cs[ns_key] and sent < S.MIN_NUMBER_OF_DATA_REPLICA-1:
                                if ns_key != self._uid:
                                    self._msgs_to_send.append([msg, hdrs, nodes_cs[ns_key]['IP_address'], self._nodelevel])
                                    sent=sent+1
                                    self.LOGGER.info("msg "+msg['uid']+" forwarded to node with data storage service on node "+nodes_cs[ns_key]['IP_address'])
                        elif 'IP_address' not in nodes_cs[ns_key]:
                            self.LOGGER.warning("One "+self._nodelevel+" node has no IP set! Impossible to replicate msg "+msg['uid']+"!")
                        else:
                            self.LOGGER.info("Maximum number of replica reached.")

        if (msg.get('type')=='GET_DATA'):
            # Check if Data are stored locally file content
            listoffiles = next(os.walk(S.DATA_STORAGE_PATH), (None, None, []))[2]
            self.LOGGER.debug("Msg content is: "+str(msg['content']))
            if msg['content'] in listoffiles:
                # Read it
                with open(S.DATA_STORAGE_PATH+str(msg['content']), 'r') as filedata:
                    msg['content']=json.load(filedata)
                # Send it back to client
                self._sends_back(msg, hdrs,'DATA_LOADED')
            elif msg.get('trials') is None or msg.get('trials') < 3: # 'or' is lazy
                # Forward message to another potential node
                if msg.get('trials') is None:
                    msg['trials']=1
                else:
                    msg['trials']=msg['trials']+1
                # Get list of nodes storing the corresponding file
                nodes_uid=[el for el in self._all_files if msg['content'] in self._all_files[el]]
                self.LOGGER.info("List of nodes having file of the given hash is: " + str(nodes_uid))
                if len(nodes_uid)==0: # hash has not been found in any node
                    msg['content']='Data storage have not found any corresponding file, ensure your hash is correct.'
                    self._sends_back(msg, hdrs,'DATA_NOT_FOUND')
                sent=0
                for j in range(0, len(nodes_uid)): 
                    if nodes_uid[j] in self._nodeslist.keys() and sent < 1:
                        if nodes_uid[j] != self._uid:
                            if 'IP_address' in self._nodeslist[nodes_uid[j]]:
                                self._msgs_to_send.append([msg, hdrs, self._nodeslist[nodes_uid[j]]['IP_address'], self._nodelevel])
                                sent=sent+1
                                self.LOGGER.info("msg "+msg['uid']+" forwarded to node with data storage service on node "+self._nodeslist[nodes_uid[j]]['IP_address'])
                            else:
                                self.LOGGER.warning("One "+self._nodelevel+" node has no IP set! Impossible to forward hash get msg "+msg['uid']+" to it! "+nodes_uid[j])
            else:
                # We have not found file after 3 trials, send back failure to client
                msg['content']='Data storage have not found any node with a valid copy of the file!'
                self._sends_back(msg, hdrs,'DATA_NOT_FOUND')
                
        if (msg.get('type')=='FILESLIST'):
            # Store received list of files
            self._all_files[msg['content']['node_uid']]=msg['content']['fileslist']
                    
        return True

    def _sends_back(self, msg, hdrs, htype):
        hdrs_cli=hdrs.copy()
        hdrs_cli['dest_uid']=hdrs.get('sender_uid')
        hdrs_cli['dest_IP']=hdrs.get('sender_node_IP')
        #hiding IP of level 1/2 nodes
        hdrs_cli['sender_node_IP']=''
        hdrs_cli['sender_uid']=self._uid
        msg['type']=htype
        self.LOGGER.info("Sending back "+str(msg['uid'])+" " +str(hdrs))
        self._msgs_to_send.append([msg, hdrs_cli, hdrs_cli['dest_IP'], 'L3'])

    def _share_saved_files(self):
        # Update all known files
        listoffiles = next(os.walk(S.DATA_STORAGE_PATH), (None, None, []))[2]
        
        # prepare the msg to be sent
        headers=self._initheaders()
        headers['service']='data_storage'
        msg=self._initmsg()
        msg['type']='FILESLIST'
        msg['content']['node_uid']=self._uid
        msg['content']['fileslist']=listoffiles
        
        #send to all nodes at the level with Data storage
        j=0
        for nk in self._nodeslist.keys():
            if 'services' in self._nodeslist[nk]:
                if 'data_storage' in self._nodeslist[nk]['services']:
                    if (self._nodeslist[nk]['services']['data_storage'] == 1):
                        if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                            headers['dest_IP']=self._nodeslist[nk]['IP_address']
                            self._msgs_to_send.append([msg, headers, self._nodeslist[nk]['IP_address'], self._nodelevel])
                            j=j+1
        self.LOGGER.info("Data storage, save files shared with : "+str(j)+" nodes.")
        
    def _ticking_actions(self):
        super()._ticking_actions()

        # Share own list of saved files with all other nodes with data storage service
        self._share_saved_files()
        
        #TODO implement a check of all files and see if an additional copy is needed, also remove non responding nodes  
        return

#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2 and sys.argv[1] == 'L2':
            nodelevel=sys.argv[1]
            # Create Instance and start the service
            consumer = ServiceRunning(nodelevel, 'data_storage')
            consumer.run()
    else:
        print("The 'data_storage' service only works on L2.")
        exit()
        
if __name__ == '__main__':
    main()
