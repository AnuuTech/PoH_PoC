#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import os
import json
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
import binascii
import time
from collections import Counter
import pymongo
import urllib

class ServiceRunning(ReconnectingNodeConsumer):
    POH_STAT_PATH='node_data/poh_stat.file'
    POH_BLOCKS_PATH='node_data/blocks.file'
    NODE_TICK_INTERVAL=10 #overriding the one of service_class
    ET=1653948000 # epoch trim (31.05.2022 in CET)
    _poh_stats={}
    _poh_blocks=[]
    _txs_to_delete=[]
    _own_last_hash=''
    _last_epoch=0


    def _initnode(self):
        super()._initnode()
        #Load blockchain
        if os.path.isfile(self.POH_BLOCKS_PATH):
            with open(self.POH_BLOCKS_PATH, 'r') as b_file:
                self._poh_blocks=json.load(b_file)
        else:
            # Genesis block
            height=1
            b_hash='120157110_AnnuTech_is_born_74312d646576'
            epoch=1653948000-self.ET # =0 
            # Create second block
            hh=SHA256.new(str(height+1).encode())#put new height
            hh.update(b_hash.encode()) #put previous block hash
            hh.update(str(epoch).encode()) #put current epoch
            b_hash2=binascii.hexlify(hh.digest()).decode()
            self._poh_blocks=[[height, b_hash, epoch],
                              [height+1, b_hash2, epoch+1]]
            
        #PoH stat updated from file
        if os.path.isfile(self.POH_STAT_PATH):
            with open(self.POH_STAT_PATH, 'r') as pst_file:
                self._poh_stats=json.load(pst_file)
        self.LOGGER.info("INITALISATION poh service done")
 
    def _msg_process(self, msg, hdrs):

        if (msg.get('type')=='POH_L3_R1' and (hdrs.get('dest_uid') == self._uid or
                                               hdrs.get('dest_IP') == self._own_IP)):
            tt=time.time()
            #Create fingerprint
            fingerprint = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], tt)

            # Prepare query in good format
            db_query = { 'uid': msg['uid'], 'tx': msg['content']['tx'], 'tx_hash': msg['content']['tx_hash'],
                         'timestamp': tt, 'signer_nodeL3': self._uid, 'fingerprintL3': fingerprint }
            # Insert Tx on DB
            self._updateDB('transactions', db_query, None)
            self.LOGGER.info("Tx sent to Txs for debug on DB" +str(db_query))

            # Sends back to client
            hdrs['dest_uid']=hdrs.get('sender_uid')
            hdrs['dest_IP']=hdrs.get('sender_node_IP')
            msgback=self._initmsg()
            msgback['uid']=msg['uid'] #keeps the same id, uid is the one set on DB for this tx
            msgback['type']='POH_L3_R1_DONE'
            msgback['content']['timestamp']=tt
            msgback['content']['tx']=msg['content']['tx']
            msgback['content']['tx_hash']=msg['content']['tx_hash']
            msgback['content']['fingerprintL3']=fingerprint
            msgback['content']['signer_nodeL3']=self._uid
            self.LOGGER.info("POH R1 will send back "+str(msgback['uid'])+" " +str(hdrs))
            self._msgs_to_send.append([msgback, hdrs, hdrs['dest_IP'], 'L3'])

        elif (msg.get('type')=='POH_L3_R2' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # SECOND L3 NODE
            # first L3 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprintL3'], msg['content']['signer_nodeL3']):
                # Create temp fingerprint     
                fingerprint_L3L2 = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for n in self._nodeslist_lower:
                    if 'services' in n:
                        if 'poh' in n['services']:
                            if (n['services']['poh'] == 1):
                                nodes_ps.append(n)
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint_L3L2.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp]['uid']
                    headers['dest_IP']=nodes_ps[sumfp]['IP_address']
                    msg['type']='POH_L2_R3'
                    msg['content']['fingerprint_L3L2']=fingerprint_L3L2
                    msg['content']['signer_node_L3L2']=self._uid
                    self.LOGGER.info("msg POH R3 prepared to be sent: "+str(headers))
                    self._msgs_to_send.append([msg, headers, headers['dest_IP'], 'L2'])
                else:
                    self.LOGGER.warning("Cannot send PoH R3 msg, no node with service active found!")
            else:
                self.LOGGER.warning("POH R3 cancelled!")
                
        elif (msg.get('type')=='POH_L2_R3' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # First L2 NODE
            # Second L3 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprint_L3L2'], msg['content']['signer_node_L3L2']):
                # sign the hash TODO first check if tx is eligible ???  
                fingerprint2 = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for n in self._nodeslist:
                    if 'services' in n:
                        if 'poh' in n['services']:
                            if (n['services']['poh'] == 1):
                                nodes_ps.append(n)
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint2.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp]['uid']
                    headers['dest_IP']=nodes_ps[sumfp]['IP_address']
                    msg['type']='POH_L2_R4'
                    msg['content']['fingerprintL2']=fingerprint2
                    msg['content']['signer_nodeL2']=self._uid
                    self.LOGGER.info("msg POH R4 prepared to be sent: "+str(headers))
                    self._msgs_to_send.append([msg, headers, headers['dest_IP'], 'L2'])
                else:
                    self.LOGGER.warning("Cannot send PoH R4 msg, no node with service active found!")
            else:
                self.LOGGER.warning("POH R4 cancelled!")

        elif (msg.get('type')=='POH_L2_R4' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # SECOND L2 NODE
            # first L2 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprintL2'], msg['content']['signer_nodeL2']):
                # Create temp fingerprint     
                fingerprint_L2L1 = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'])
                # Select L1 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for n in self._nodeslist_lower:
                    if 'services' in n:
                        if 'poh' in n['services']:
                            if (n['services']['poh'] == 1):
                                nodes_ps.append(n)
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint_L2L1.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp]['uid']
                    headers['dest_IP']=nodes_ps[sumfp]['IP_address']
                    msg['type']='POH_L1_R5'
                    msg['content']['fingerprint_L2L1']=fingerprint_L2L1
                    msg['content']['signer_node_L2L1']=self._uid
                    self.LOGGER.info("msg POH R5 prepared to be sent: "+str(headers))
                    self._msgs_to_send.append([msg, headers, headers['dest_IP'], 'L1'])
                else:
                    self.LOGGER.warning("Cannot send PoH R5 msg, no node with service active found!")
            else:
                self.LOGGER.warning("POH R5 cancelled!")
                
        elif (msg.get('type')=='POH_L1_R5' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # First L1 NODE
            # Second L2 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprint_L2L1'], msg['content']['signer_node_L2L1']):
                # sign the hash       
                fingerprint3 = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for n in self._nodeslist:
                    if 'services' in n:
                        if 'poh' in n['services']:
                            if (n['services']['poh'] == 1):
                                nodes_ps.append(n)
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint3.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp]['uid']
                    headers['dest_IP']=nodes_ps[sumfp]['IP_address']
                    msg['type']='POH_L1_R6'
                    msg['content']['fingerprintL1']=fingerprint3
                    msg['content']['signer_nodeL1']=self._uid
                    self.LOGGER.info("msg POH R6 prepared to be sent: "+str(headers))
                    self._msgs_to_send.append([msg, headers, headers['dest_IP'], 'L1'])
                else:
                    self.LOGGER.warning("Cannot send PoH R6 msg, no node with service active found!")
            else:
                self.LOGGER.warning("POH R6 cancelled!")

        elif (msg.get('type')=='POH_L1_R6' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # Second L1 NODE
            # First L1 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprintL1'], msg['content']['signer_nodeL1']):
                # Prepare query in good format
                db_query = { 'uid': msg['uid'], 'tx': msg['content']['tx'], 'tx_hash': msg['content']['tx_hash'], 'timestamp': msg['content']['timestamp'],
                             'signer_nodeL3': msg['content']['signer_nodeL3'], 'fingerprintL3': msg['content']['fingerprintL3'],
                             'signer_nodeL2': msg['content']['signer_nodeL2'], 'fingerprintL2': msg['content']['fingerprintL2'],
                             'signer_nodeL1': msg['content']['signer_nodeL1'], 'fingerprintL1': msg['content']['fingerprintL1']}
                # Insert Tx on DB
                self._updateDB('transactions_pending', db_query, None)
                self.LOGGER.info("Tx sent to pending Txs on DB" +str(db_query))
            else:
                self.LOGGER.warning("POH saving in DB cancelled!")

        # FORWARD PoH messages from client that are for another node
        elif msg.get('type')=='POH_L3_R1' or msg.get('type')=='POH_L3_R2':
            IP_tosend=''
            if len(hdrs['dest_IP'])>6:
                IP_tosend=hdrs['dest_IP']
            else: # get from nodeslist
                for n in self._nodeslist:
                    if hdrs['dest_uid'] == n['uid'] and 'IP_address' in n:
                        IP_tosend=n['IP_address']
            if IP_tosend == '':
                self.LOGGER.warning("Impossible to forward message to "+str(hdrs['dest_uid'])+". Msg " +str(msg.get('uid'))+ " will be lost!")
            else:
                self.LOGGER.info("PoH message forwarded to " +str(IP_tosend))
                self._msgs_to_send.append([msg, hdrs, IP_tosend, 'L3'])
            
        # Update poh stats
        if str(hdrs['sender_uid']) in list(self._poh_stats.keys()):
            self._poh_stats[hdrs['sender_uid']]=self._poh_stats[hdrs['sender_uid']]+1
        else:
            self._poh_stats[hdrs['sender_uid']]=1
        return True

    def _signature_verif(self, tx, tx_hash, timestamp, fingerprint, node_uid):
        try:
            nodepubkey=None
            # get pubkey from nodeslist
            for n in self._nodeslist:
                if 'uid' in n:
                    if n['uid'] == node_uid:
                        if 'pubkey' in n['uid']:
                            nodepubkey=RSA.importKey(n.get('pubkey').encode())
                            self.LOGGER.debug(str(node_uid)+" corresponding pubkey found "+str(n.get('pubkey')))

            # if no pubkey found, try to get pubkey from DB # TODO get all net storage available nodes
            if nodepubkey is None:
                db_query = { 'uid': node_uid }
                db_filter = {'_id':0}
                res=self._getDB_data('nodes', db_query, db_filter) 
                if len(res)==0:
                    self.LOGGER.info("Node " + str(node_uid)+" is not found in DB!")
                    return False
                nodepubkey=RSA.importKey(res[0].get('pubkey').encode())

            if nodepubkey is not None:
                #Verify fingerprint
                hh=SHA256.new(tx.encode())
                hh.update(tx_hash.encode())
                hh.update(str(timestamp).encode())
                verifier = PKCS115_SigScheme(nodepubkey)
                try:
                    verifier.verify(hh, binascii.unhexlify(fingerprint.encode()))
                    self.LOGGER.info("Tx " + str(tx)+" has been validly signed by "
                                +str(node_uid))
                    return True
                except:
                    self.LOGGER.info("Tx " + str(tx)+" has NOT BEEN VALIDLY signed by "
                                +str(node_uid))
                    return False
            else:
                self.LOGGER.info("Node " + str(node_uid)+" does not seem to have a pubkey!")
                return False
        except:
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to verify signature %s' %str(e))
            return False


    def _do_signature(self, tx, tx_hash, timestamp):
        #Create fingerprint
        hh=SHA256.new(tx.encode())
        hh.update(tx_hash.encode())
        hh.update(str(timestamp).encode())
        signer = PKCS115_SigScheme(self._PRIVKEY)
        return binascii.hexlify(signer.sign(hh)).decode()


    def _ticking_actions(self):
        super()._ticking_actions()

        if self._nodelevel == 'L1':
            self.LOGGER.debug("Current Epoch: "+str(divmod(time.time()-self.ET,60)[0]) + " and last block's epoch: "+str(self._poh_blocks[-1][2]))
            if divmod(time.time()-self.ET,60)[0] > self._poh_blocks[-1][2]:
                # new epoch just started, compute new block
                self._compute_new_block()
                # update blocks on DB
                self._blocks_updateDB()
                # check the blocks
                self._check_blocks()
            elif (time.time()-self.ET)/60 > self._poh_blocks[-1][2]+0.75: # >45 seconds after epoch starts
                # epoch is finishing, finalize and clean pending txs
                self._finalizing()
            else:
                # check the blocks
                self._check_blocks()            

        #save the blocks
        with open(self.POH_BLOCKS_PATH, 'w') as b_file:
            b_file.write(json.dumps(self._poh_blocks))
            
        #write poh stats to file
        with open(self.POH_STAT_PATH, 'w') as pst_file:
            pst_file.write(json.dumps(self._poh_stats))

        self._stat_updateDB()        
        return


    def _compute_new_block(self):
        # don't run if finalize has not been done
        if len(self._txs_to_delete)>0:
            return
        # determine epoch
        epoch=divmod(time.time()-self.ET, 60)[0]
        
        # get all pending txs from DB
        db_query = {}
        db_filter = {'_id':0}
        txres=self._getDB_data('transactions_pending', db_query, db_filter)
        if len(txres) == 0:
            self.LOGGER.warning("No txs have been found!")
            return
        self.LOGGER.info(str(len(txres))+" txs have been read from DB.")

        # order all txs by timestamps TODO check if txs have not already been included in a previous block?
        txs_pend=sorted(txres, key=lambda t: t['timestamp'])

        # check all txs with nodes public keys
        txs_valid=[]
        for tx in txs_pend:
            if divmod(tx['timestamp']-self.ET,60)[0] < epoch: # tx of current epoch are not taken into account yet
                if (self._signature_verif(tx['tx'], tx['tx_hash'], tx['timestamp'], tx['fingerprintL3'], tx['signer_nodeL3']) and
                    self._signature_verif(tx['tx'], tx['tx_hash'], tx['timestamp'], tx['fingerprintL2'], tx['signer_nodeL2']) and
                    self._signature_verif(tx['tx'], tx['tx_hash'], tx['timestamp'], tx['fingerprintL1'], tx['signer_nodeL1'])):
                    txs_valid.append(tx)
        self.LOGGER.info(str(len(txs_valid))+" txs have been validated.")
        
        # create new block hash
        if len(txs_valid)>0:
            new_height=self._poh_blocks[-1][0]+1 #previous height+1
            hh=SHA256.new(str(new_height).encode())# put new height
            hh.update(self._poh_blocks[-1][1].encode()) # put previous block hash
            hh.update(str(epoch).encode()) # put epoch

            for tx in txs_valid:
                hh.update(tx['tx_hash'].encode())#put each tx hash

            b_hash=binascii.hexlify(hh.digest()).decode()#compute final hash

            # Add new block!
            self._poh_blocks.append([new_height, b_hash, epoch])
            self.LOGGER.info("A new block has been added! " + str([new_height, b_hash, epoch]))

            # store info for later txs deletion
            self._txs_to_delete=txs_valid
            self._own_last_hash=b_hash
            self._last_epoch=epoch

        
    def _check_blocks(self):
        # get latest blocks from DB
        db_query = { 'level': 'L1'}
        db_filter = {'IP_address':1, 'uid':1, '_id':0, 'blocks':1}
        res=self._getDB_data('nodes', db_query, db_filter)
        if len(res) == 0:
            self.LOGGER.warning("No valid nodes have been found at L1 for checking blocks!")
            return
        blocks=[]
        for n in res:
            if 'blocks' in n:
                if 'current' in n['blocks'] and 'previous' in n['blocks'] and 'height' in n['blocks']:
                    blocks.append([n['blocks']['current'],n['blocks']['previous'], n['blocks']['height']])

        # sort by chains
        # get chains heights in a descending order
        chains={}# {current hash: [height occurence previous_hash]}
        heights=sorted(list(set([i[2] for i in blocks])), reverse= True) #list(set()) to remove duplicates
        self.LOGGER.debug("Checking blocks, heights: "+str(heights))
        ct=Counter(tuple(item) for item in blocks).most_common()
        # get all chains with different set of "current hash and height"
        for l in heights: # for all heights in a decreasing order
            for c in ct: # for all triplets current, previous, height
                if c[0][2]==l: # if height is the one we are looking at now
                    if c[0][0] not in chains.keys(): # if chain (current hash) is not already listed
                        chains[c[0][0]]=[l, c[1], c[0][1]] # create an entry into chains, with the number of occurence
                    else:
                        if chains[c[0][0]][0]!=l: # if chain already exists but height of chain is not the same
                            # keeps the chain height with the most occurences
                            if chains[c[0][0]][1] < c[1]:
                                chains[c[0][0]]=[l, c[1], c[0][1]]
                        else: # chain already exists with same height but different previous block
                            pass #keep the chain with the highest nb of occurence (which was already entered since blocks are considered in decreasing occurence order)

        self.LOGGER.debug("Checking blocks, chains: "+str(chains))
        # get nb of chains
        nb_chains=0
        for c in chains.keys():
            nb_chains=nb_chains+chains[c][1]

        # check which chain we belong to and compare occurence
        own_occ=0
        max_occ=0
        max_occ_chains=[]
        for c in chains.keys():
            if chains[c][1] > max_occ:
                max_occ=chains[c][1]
                max_occ_chains=[c]
            elif chains[c][1] == max_occ:
                max_occ_chains.append(c)
            if c == self._poh_blocks[-1][1] and chains[c][2] == self._poh_blocks[-2][1] and chains[c][0] == self._poh_blocks[-1][0]:
                own_occ= chains[c][1]

        # decide what chain to follow
        if own_occ == max_occ and self._poh_blocks[-1][0]>=chains[max_occ_chains[0]][0]: # same occurence and height is same or higher -->stay on chain
            self.LOGGER.info("Staying on best chain: " + str(self._poh_blocks[-1]))
        elif own_occ == max_occ and self._poh_blocks[-1][0]<chains[max_occ_chains[0]][0]: # same occurence but height is lower --> switch chain
            self._poh_blocks[-1][1]=max_occ_chains[0] # current hash
            self._poh_blocks[-2][1]=chains[max_occ_chains[0]][2] # previous hash
            self._poh_blocks[-1][0]=chains[max_occ_chains[0]][0] # current height
            self.LOGGER.info("Switching to highest chain: " + str(chains[max_occ_chains[0]]))
        elif max_occ > nb_chains/2: # there is a dominating chain and we are not on it:
            # Switch chain TODO privilege LONGEST chain if several existing? (already switching to HIGHEST)
            self._poh_blocks[-1][1]=max_occ_chains[0] # current hash
            self._poh_blocks[-2][1]=chains[max_occ_chains[0]][2] # previous hash
            self._poh_blocks[-1][0]=chains[max_occ_chains[0]][0] # current height
            self.LOGGER.info("Switching to dominating chain: " + str(chains[max_occ_chains[0]]))
            self._blocks_updateDB()            
        elif (time.time()-self.ET)/60 > self._poh_blocks[-1][2] + 1.5*self.NODE_TICK_INTERVAL: # all nodes should have had time to compute next block
            # Switch chain TODO privilege longest chain if several existing?
            self._poh_blocks[-1][1]=max_occ_chains[0]
            self._poh_blocks[-2][1]=chains[max_occ_chains[0]][2]
            self._poh_blocks[-1][0]=chains[max_occ_chains[0]][0]
            self.LOGGER.info("Switching to better chain: " + str(chains[max_occ_chains[0]]))
            self._blocks_updateDB()
        else:
            self.LOGGER.info("For now staying on current chain: " + str(self._poh_blocks[-1]))# for now stay on chain


    def _finalizing(self):
        # Only do for node with local net storage service
        #if 'net_storage' in self._nodeservices:
         #DEACTIVATED FOR NOW   if self._nodeservices['net_storage'] == 1:
        self.LOGGER.debug("Finalizing! " + str([len(self._txs_to_delete), self._own_last_hash]))
        # Check that our list of txs is the one of the winning block
        if len(self._txs_to_delete)>0 and self._own_last_hash == self._poh_blocks[-1][1]:
            db_queries=[]
            for tx in self._txs_to_delete:
                db_queries.append({ 'uid': tx['uid']})
            self._delete_dataDB('transactions_pending', db_queries) #, 'localhost') TODO force to use localhost?
            self.LOGGER.info("Node has deleted the pending txs")

            #Add block into DB
            db_query = { 'hash': self._poh_blocks[-1][1] }
            db_values_toset = {'$set':{'height': self._poh_blocks[-1][0],
                                       'previous_hash': self._poh_blocks[-2][1],
                                       'epoch' : self._last_epoch,
                                       'transactions': self._txs_to_delete}}
            self._updateDB('blocks', db_query, db_values_toset)

        # Reset info for deletion in any case
        self._own_last_hash == ''
        self._txs_to_delete = []
        self._last_epoch=0

        
    def _blocks_updateDB(self):
        db_query = { 'uid': self._uid }
        db_values_toset = {'$set':{'blocks':{'current': self._poh_blocks[-1][1], 'previous': self._poh_blocks[-2][1], 'height': self._poh_blocks[-1][0]}}}
        # Write to DB
        self._updateDB('nodes', db_query, db_values_toset)
        self.LOGGER.debug("Node blocks updated on DB, blocks = " + str(db_values_toset))      

        
    def _stat_updateDB(self):
        # Determine total sum of messages processed
        tot=0
        for cc in self._poh_stats.keys():
            tot=tot+self._poh_stats[cc]
        db_query = { 'uid': self._uid }
        db_values_toset = {'$set':{'service_poh':{'nb_of_msg_processed': tot}}}
        # Write to DB
        self._updateDB('nodes', db_query, db_values_toset)
        self.LOGGER.debug("Node stat updated on DB, stats = " + str(db_values_toset))

#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            nodelevel=sys.argv[1]

            # Create Instance and start the service
            consumer = ServiceRunning(nodelevel, 'poh')
            consumer.run()
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
