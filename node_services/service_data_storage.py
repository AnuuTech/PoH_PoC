#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import os
import json
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
import binascii
import time
import random

class ServiceRunning(ReconnectingNodeConsumer):
    DATA_STORAGE_STAT_PATH='node_data/data_storage_stat.file'
    DATA_STORAGE_PATH='node_data/data_storage/'
    MIN_NUMBER_OF_REPLICA=2
    _data_stats={}

    def _initnode(self):
        super()._initnode()
        #Datastat updated from file
        if os.path.isfile(self.DATA_STORAGE_STAT_PATH):
            with open(self.DATA_STORAGE_STAT_PATH, 'r') as pst_file:
                self._data_stats=json.load(pst_file)

        #Ensure data storage directory exists
        if not os.path.exists(self.DATA_STORAGE_PATH):
            os.makedirs(self.DATA_STORAGE_PATH)

        self.LOGGER.info("INITALISATION data storage service done")

 
    def _msg_process(self, msg, hdrs):

        if (hdrs.get('type')=='SAVE_DATA' or hdrs.get('type')=='SAVE_DATA_REPLICATE'): #and hdrs.get('dest_uid') == self._uid):
            # Hash file content
            file_hash=binascii.hexlify((SHA256.new(msg['content'].encode())).digest()).decode()

            # Save file locally using hash as filename
            data_path=self.DATA_STORAGE_PATH+str(file_hash)
            with open(data_path, 'w') as data_file:
                data_file.write(json.dumps(msg['content']))

            # Inform client of saved data
            hdrs_cli=hdrs.copy()
            hdrs_cli['dest_uid']=hdrs.get('sender_uid')
            hdrs_cli['dest_IP']=hdrs.get('sender_node_IP')
            #hiding IP of level 1/2 nodes
            hdrs_cli['sender_node_IP']=''
            hdrs_cli['sender_uid']=self._uid
            hdrs_cli['type']='DATA_SAVED'
            msgback=self._initmsg()
            msgback['uid']=msg['uid'] #keeps the same id so that the client knows which file it was
            msgback['content']='File saved, hash is in content_hash'
            msgback['content_hash']=file_hash
            self.LOGGER.info("Data storage sends back confirmation msg "+str(msgback['uid'])+" " +str(hdrs))
            self._msgs_to_send.append([msgback, hdrs_cli, hdrs_cli['dest_IP'], 'L3'])

            # Write on DB
            # Prepare query in good format
            db_query = { "hash": file_hash }
            size=sys.getsizeof(msg['content'])
            db_values_toset = {"$set":{self._uid: 'local', 'size' : size}}

            # Insert data hash on DB
            self._updateDB('data_storage_files', db_query, db_values_toset)
            self.LOGGER.info("Hash sent to data storage files on DB" +str(db_query))

            if hdrs['type'] == 'SAVE_DATA':
                # Send file to other nodes, up to min number of replica
                hdrs['type']='SAVE_DATA_REPLICATE'
                # Get a node on lower layer node with corresponding service
                nodes_cs=[]
                for n in self._nodeslist:
                    if 'services' in n:
                        if 'data_storage' in n['services']:
                            if n['services']['data_storage'] == 1:
                                nodes_cs.append(n)
                random.shuffle(nodes_cs)
                if len(nodes_cs) == 0:
                    self.LOGGER.warning("No node with service data storage is available, impossible to replicate msg "+msg['uid']+"!")
                else:
                    sent=0
                    for j in range(0, len(nodes_cs)): 
                        if 'IP_address' in nodes_cs[j] and sent < self.MIN_NUMBER_OF_REPLICA-1:
                                if nodes_cs[j]['uid'] != self._uid:
                                    self._msgs_to_send.append([msg, hdrs, nodes_cs[j]['IP_address'], self._nodelevel])
                                    sent=sent+1
                                    self.LOGGER.info("msg "+msg['uid']+" forwarded to node with data storage service on node "+nodes_cs[j]['IP_address'])
                        else:
                            self.LOGGER.warning("One "+self._nodelevel+" node has no IP set! Impossible to replicate msg "+msg['uid']+"!") 

        # Update data stats
        if str(hdrs['sender_uid']) in list(self._data_stats.keys()):
            self._data_stats[hdrs['sender_uid']]=self._data_stats[hdrs['sender_uid']]+1
        else:
            self._data_stats[hdrs['sender_uid']]=1
        return True

    def _ticking_actions(self):
        #nodelist updated from file
        if os.path.isfile(self.NODESLIST_PATH):
            with open(self.NODESLIST_PATH, 'r') as nodes_file:
                self._nodeslist=json.load(nodes_file)

        #lower nodelist updated from file
        if os.path.isfile(self.NODESLIST_LOWER_PATH):
            with open(self.NODESLIST_LOWER_PATH, 'r') as nodes_file:
                self._nodeslist_lower=json.load(nodes_file)

        #write DATA_STORAGE_STAT_PATH stats to file
        with open(self.DATA_STORAGE_STAT_PATH, 'w') as pst_file:
            pst_file.write(json.dumps(self._data_stats))

        self._stat_updateDB()        
        return

    def _stat_updateDB(self):
        # Determine total sum of messages processed
        tot=0
        for cc in self._data_stats.keys():
            tot=tot+self._data_stats[cc]
        db_query = { "uid": self._uid }
        db_values_toset = {"$set":{"service_data_storage":{"nb_of_msg_processed": tot}}}
        # Write to DB
        self._updateDB('nodes', db_query, db_values_toset)
        self.LOGGER.debug("Node information updated on DB, IP = " + str(db_values_toset))

#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            nodelevel=sys.argv[1]

            # Create Instance and start the service
            consumer = ServiceRunning(nodelevel, 'data_storage')
            consumer.run()
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
