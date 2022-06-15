#import class_service
from service_class import ReconnectingNodeConsumer
import settings as S
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
    _last_block_hash_stored=''
    _last_block_height_stored=0

    def _initnode(self):
        super()._initnode()

        #Ensure net storage directory exists
        if not os.path.exists(S.NET_STORAGE_PATH):
            os.makedirs(S.NET_STORAGE_PATH)
            # Store Genesis block
            data_path=S.NET_STORAGE_PATH+str('0')
            blocktemp={'height': 0, 'current_hash': S.GENESIS_HASH, 'previous_hash': '', 'epoch' : 0}
            with open(data_path, 'w') as data_file:
                data_file.write(json.dumps(blocktemp))
            # Create and store second block
            hh=SHA256.new(S.GENESIS_HASH.encode())#put previous block hash
            hh.update(str(1).encode()) # put current epoch
            b_hash2=binascii.hexlify(hh.digest()).decode()
            data_path=S.NET_STORAGE_PATH+str('1')
            blocktemp={'height': 1, 'current_hash': b_hash2,
                       'previous_hash': S.GENESIS_HASH, 'epoch' : 1}
            with open(data_path, 'w') as data_file:
                data_file.write(json.dumps(blocktemp))
        self.LOGGER.info("INITALISATION net storage service done")
 
    def _msg_process(self, msg, hdrs):

        if msg.get('type')=='SAVE_BLOCK' or msg.get('type')=='BLOCK_BACK':
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
                    data_path=S.NET_STORAGE_PATH+str(msg['content']['height'])
                    with open(data_path, 'w') as data_file:
                        data_file.write(json.dumps(msg['content']))
                    # Write to DB if new block
                    if msg.get('type')=='SAVE_BLOCK':
                        db_query = { 'height': msg['content']['height'] }
                        db_values_toset = {'$set':{'height': msg['content']['height'],
                                                   'current_hash': msg['content']['current_hash'],
                                                   'previous_hash': msg['content']['previous_hash'],
                                                   'epoch' : msg['content']['epoch'],
                                                   'transactions': msg['content']['transactions']}}
                        self._updateDB('blocks', db_query, db_values_toset, False)
                        self._last_block_hash_stored = msg['content']['current_hash']
                        self._last_block_height_stored = msg['content']['height']
                        self.LOGGER.info("New block " +str(msg['content']['height'])+" is valid and has been stored locally and on DB.")
                    else:
                        self.LOGGER.info("Block " +str(msg['content']['height'])+" is valid and has been stored locally.")
            else:
                self.LOGGER.info("Block " +str(msg['content']['current_hash'])+" seems invalid and has NOT been stored!")

        if (msg.get('type')=='GET_BLOCK'):
            # Check if Block data are stored locally
            listofblocks = next(os.walk(S.NET_STORAGE_PATH), (None, None, []))[2]
            self.LOGGER.debug("Msg content is: "+str(msg['content']))
            if str(msg['content']) in listofblocks:
                # Read it
                with open(S.NET_STORAGE_PATH+str(msg['content']), 'r') as filedata:
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
                                if 'IP_address' in self._nodeslist[nk]:
                                    if self._nodeslist[nk]['IP_address'] != self._own_IP:
                                        hdrs['dest_IP']=self._nodeslist[nk]['IP_address']
                                        self._msgs_to_send.append([msg, hdrs, self._nodeslist[nk]['IP_address'], self._nodelevel])
                                        sent=sent+1
                                        self.LOGGER.info("msg "+msg['uid']+" forwarded to node with net storage service on node "+hdrs['dest_IP'])
                                else:
                                    self.LOGGER.warning("One "+self._nodelevel+" node has no IP set! Impossible to forward block get msg "+msg['uid']+" to it! "+nk)
            else:# We have not found file after 3 trials, send back failure to client
                msg['content']='Net storage have not found any node with the requested block!'
                self._sends_back(msg, hdrs,'BLOCK_NOT_FOUND')
                
        if (msg.get('type')=='GET_BLOCKSLIST'):
            # Send list of blocks
            msg['content'] = next(os.walk(S.NET_STORAGE_PATH), (None, None, []))[2]
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
        self._msgs_to_send.append([msg, hdrs_cli, hdrs_cli['dest_IP'], 'L2'])
        
    def _ticking_actions(self):
        super()._ticking_actions()
        if self._nodelevel=='L2':
            self._update_info_on_DB()
            self._check_blocks_storage()

    def _update_info_on_DB(self):
        # Reformat
        allnodes={}
        allnodes.update(self._nodeslist)
        allnodes.update(self._nodeslist_upper)
        allnodes.update(self._nodeslist_lower)
        for ak in allnodes.keys():
            db_query = {'uid': ak}
            temp=allnodes[ak]
            temp['uid']=ak
            db_values_toset={ '$set' : temp}
            # Write to DB TODO find a way to update all nodes in one shot?
            self._updateDB('nodes', db_query, db_values_toset, False)
        self.LOGGER.info("Nodes info updated on DB.")

    def _check_blocks_storage(self):
        listofblocks = next(os.walk(S.NET_STORAGE_PATH), (None, None, []))[2]
        listofblocks.sort()
        allnbs=list(range(0,int(listofblocks[-1])))
        for b in allnbs:
            if str(b) not in listofblocks:
                # Request block to another L2 node
                # prepare the msg to be sent
                headers=self._initheaders()
                headers['service']='net_storage'
                msg=self._initmsg()
                msg['type']='GET_BLOCK'
                msg['content']=b
                #request from another L2 node with net storage
                IP_sel=self._get_rand_nodeIP('net_storage', self._nodeslist, self._own_IP)
                if len(IP_sel)>6:
                    headers['dest_IP']=IP_sel
                    self._msgs_to_send.append([msg, headers, IP_sel, 'L2'])
                    self.LOGGER.info("Net storage get missing block from : "+IP_sel)
                else:
                    self.LOGGER.warning("No other nodes with net storage service at L2 are available!")

    # Generic method to get infos from AnuuTechDB
    def _delete_dataDB(self, collects, del_list):
        try:
            IP_sel=self._get_rand_nodeIP('net_storage', self._nodeslist, '')
            if len(IP_sel)<7:
                self.LOGGER.warning("No node with valid IP have been found at "+self._nodelevel+"! Impossible to delete data from DB!")
                return
            # delete data from DB
            db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':28991/?authMechanism=DEFAULT&authSource=admin'
            with pymongo.MongoClient(db_url) as db_client:
                at_db = db_client['AnuuTech_DB']
                res_col = at_db[collects]
                res_col.delete_many({'uid':{ '$in': del_list}})
        except:    
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to delete data from DB!!  %s' %str(e))


    # Generic method to update infos on AnuuTech_DB on L3
    def _updateDB(self, collects, db_query, db_values_toset, manyflag ):
        try:
            IPs=self._get_nodesIPs('net_storage', self._nodeslist_upper)
            if len(IPs)==0:
                self.LOGGER.warning("No node with net storage have been found at L3! Impossible to update data to DB!")
                return
            for IP_sel in IPs:
                # update data to DB
                db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':28991/?authMechanism=DEFAULT&authSource=admin'
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
                    #self.LOGGER.info("Values updated on DB = " + IP_sel+ " on " +collects)
        except:    
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to updateDB!!  %s' %str(e))

#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2 and (sys.argv[1] == 'L2' or sys.argv[1] == 'L3') :
        nodelevel=sys.argv[1]
        # Create Instance and start the service
        consumer = ServiceRunning(nodelevel, 'net_storage')
        consumer.run()
    else:
        print("The 'net storage' service works on L2 or L3. Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
