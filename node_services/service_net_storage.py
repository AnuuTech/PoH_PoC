#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import os
import json
from Crypto.Hash import SHA256
import binascii
import time
import random
import urllib
import pymongo

class ServiceRunning(ReconnectingNodeConsumer):
    NET_STORAGE_PATH='node_data/data_storage/blocks/'
    _last_block_hash_stored=''

    def _initnode(self):
        super()._initnode()

        #Ensure net storage directory exists
        if not os.path.exists(self.NET_STORAGE_PATH):
            os.makedirs(self.NET_STORAGE_PATH)

        self.LOGGER.info("INITALISATION net storage service done")
 
    def _msg_process(self, msg, hdrs):

        if msg.get('type')=='SAVE_BLOCK':
            # Verify Hash is correct
            hh=SHA256.new(msg['content']['previous_hash'].encode())# put previous block hash
            hh.update(str(msg['content']['epoch']).encode()) # put epoch
            # order all txs by timestamps TODO check if txs have not already been included in a previous block?
            txs_ord=sorted(msg['content']['transactions'], key=lambda t: t['timestamp'])
            for tx in txs_ord:
                hh.update(tx['fingerprintL1'].encode())#put each tx L1 fingerprint
            b_hash=binascii.hexlify(hh.digest()).decode()#compute final hash
            
            if b_hash == msg['content']['current_hash']:
                if self._last_block_hash_stored != msg['content']['current_hash']:
                    # Save file locally using height as filename
                    data_path=self.NET_STORAGE_PATH+str(msg['content']['height'])
                    with open(data_path, 'w') as data_file:
                        data_file.write(json.dumps(msg['content']))
                    # Write to DB
                    db_query = { 'height': msg['content']['height'] }
                    db_values_toset = {'$set':{'height': msg['content']['height'],
                                               'current_hash': msg['content']['current_hash'],
                                               'previous_hash': msg['content']['previous_hash'],
                                               'epoch' : msg['content']['epoch'],
                                               'transactions': msg['content']['transactions']}}
                    self._updateDB('blocks', db_query, db_values_toset, False)
                    self._last_block_hash_stored = msg['content']['current_hash']
                    self.LOGGER.info("Block " +str(msg['content']['height'])+" is valid and has been stored locally and on DB.")
            else:
                self.LOGGER.info("Block " +str(msg['content']['current_hash'])+" seems invalid and has NOT been stored!")

        if (msg.get('type')=='GET_BLOCK'):
            # Check if Data are stored locally file content
            listofblocks = next(os.walk(self.NET_STORAGE_PATH), (None, None, []))[2]
            self.LOGGER.debug("Msg content is: "+str(msg['content']))
            if str(msg['content']) in listofblocks:
                # Read it
                with open(self.NET_STORAGE_PATH+str(msg['content']), 'r') as filedata:
                    msg['content']=json.load(filedata)
                # Send it back to client
                self._sends_back(msg, hdrs,'BLOCK_BACK')
            elif msg.get('trials') is None or msg.get('trials') < 3: # 'or' is lazy
                # Forward message to another potential node
                if msg.get('trials') is None:
                    msg['trials']=1
                else:
                    msg['trials']=msg['trials']+1
                sent=0
                for nk in self._nodeslist.keys():
                    if 'services' in self._nodeslist[nk] and sent == 0:
                        if 'net_storage' in self._nodeslist[nk]['services']:
                            if (self._nodeslist[nk]['services']['net_storage'] == 1):
                                if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                                    headers['dest_IP']=self._nodeslist[nk]['IP_address']
                                    self._msgs_to_send.append([msg, headers, self._nodeslist[nk]['IP_address'], self._nodelevel])
                                    sent=sent+1
                                    self.LOGGER.info("msg "+msg['uid']+" forwarded to node with net storage service on node "+self._nodeslist[nk]['IP_address'])
                                else:
                                    self.LOGGER.warning("One "+self._nodelevel+" node has no IP set! Impossible to forward block get msg "+msg['uid']+" to it! "+nk)
            else:# We have not found file after 3 trials, send back failure to client
                msg['content']='Net storage have not found any node with the requested block!'
                self._sends_back(msg, hdrs,'BLOCK_NOT_FOUND')
                
        if (msg.get('type')=='GET_BLOCKSLIST'):
            # Store received list of files
            msg['content'] = next(os.walk(self.NET_STORAGE_PATH), (None, None, []))[2]
            self._sends_back(msg, hdrs,'BLOCKSLIST')
                    
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
        
    def _ticking_actions(self):
        super()._ticking_actions()

        return
    
    # Generic method to get infos from AnuuTechDB
    def _delete_dataDB(self, collects, del_list):
        try:
            IP_sel=self._get_rand_nodeIP('net_storage', self._nodeslist)
            if len(IP_sel)<7:
                self.LOGGER.warning("No node with valid IP have been found at "+self._nodelevel+"! Impossible to delete data from DB!")
                return
            # delete data from DB
            db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
            with pymongo.MongoClient(db_url) as db_client:
                at_db = db_client['AnuuTechDB']
                res_col = at_db[collects]
                res_col.delete_many({'uid':{ '$in': del_list}})
        except:    
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to delete data from DB!!  %s' %str(e))

                    
    # Generic method to get infos from AnuuTechDB
    def _getDB_data(self, collects, db_query, db_filter):
        try:
            IP_sel=self._get_rand_nodeIP('net_storage', self._nodeslist)
            if len(IP_sel)<7:
                self.LOGGER.warning("No node with valid IP have been found at "+self._nodelevel+"! Impossible to get data from DB!")
                return []
            # get data from DB
            db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
            with pymongo.MongoClient(db_url) as db_client:
                at_db = db_client['AnuuTechDB']
                res_col = at_db[collects]
                reslist=list(res_col.find(db_query, db_filter))
            if reslist is None:
                self.LOGGER.warning("No valid results have been found from DB!")
                return []
            return reslist
        except:    
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to get data from DB!!  %s' %str(e))
            return []


    # Generic method to update infos on AnuuTechDB
    def _updateDB(self, collects, db_query, db_values_toset, manyflag ):
        try:
            IP_sel=self._get_rand_nodeIP('net_storage', self._nodeslist)
            if len(IP_sel)<7:
                self.LOGGER.warning("No node with valid IP have been found at "+self._nodelevel+"! Impossible to update data to DB!")
                return
            # update data to DB
            db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
            with pymongo.MongoClient(db_url) as db_client:
                at_db = db_client['AnuuTech_DB']
                col = at_db[collects]
                if db_values_toset is not None:
                    # Update/Insert values, using upsert = True
                    col.update_one(db_query, db_values_toset, True)
                    #self.LOGGER.debug(str(db_values_toset))
                elif manyflag:
                    # use insert many command
                    col.insert_many(db_query)
                else:
                    # use insert one command
                    col.insert_one(db_query)
                self.LOGGER.info("Values updated on DB, own IP = " + self._own_IP+ " on " +collects)
        except:    
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to updateDB!!  %s' %str(e))

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
