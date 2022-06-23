#import class_service
from service_class import ReconnectingNodeConsumer
import settings as S
import sys
import os
import json
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
import binascii
import time
from collections import Counter

class ServiceRunning(ReconnectingNodeConsumer):
    _poh_blocks=[] # all blocks of this node
    _nodes_blocks={} #latest block of each nodes
    _txs_received=[]
    _txs_to_validate=[]
    _txs_validated=[]
    _own_last_hash=''
    _last_epoch=0


    def _initnode(self):
        super()._initnode()
        #Load blockchain
        if os.path.isfile(S.POH_BLOCKS_PATH):
            with open(S.POH_BLOCKS_PATH, 'r') as b_file:
                self._poh_blocks=json.load(b_file)
        if len(self._poh_blocks)<2:
            # Genesis block
            height=0
            epoch=0
            # Create second block
            hh=SHA256.new(S.GENESIS_HASH.encode())#put previous block hash
            hh.update(str(1).encode()) #put current epoch
            b_hash2=binascii.hexlify(hh.digest()).decode()
            self._poh_blocks=[[height, S.GENESIS_HASH, epoch],
                              [height+1, b_hash2, epoch+1]]
            
        # also update own entry in nodes_blocks
        self._nodes_blocks[self._uid]={'current': self._poh_blocks[-1][1], 'previous': self._poh_blocks[-2][1], 'height': self._poh_blocks[-1][0]}

        self._node_tick_interval=5 #overriding the one of service_class
        self.LOGGER.info("INITALISATION poh service done")
 
    def _msg_process(self, msg, hdrs):

        if (msg.get('type')=='POH_L3_R1' and (hdrs.get('dest_uid') == self._uid or
                                               hdrs.get('dest_IP') == self._own_IP)):
            tt=time.time()
            #Create fingerprint
            fingerprint = self._do_signature(msg['content']['tx_hash'], tt)
            # Select second L3 node based on hash (sum of all characters), restricted to nodes with poh service
            nodes_ps=[]
            for nk in self._nodeslist.keys():
                if 'services' in self._nodeslist[nk]:
                    if 'poh' in self._nodeslist[nk]['services']:
                        if (self._nodeslist[nk]['services']['poh'] == 1):
                            nodes_ps.append([nk, self._nodeslist[nk]])
            if len(nodes_ps) != 0:
                headers=self._initheaders()
                headers['service']='poh'
                sumfp=(sum(fingerprint.encode()))%len(nodes_ps)
                headers['dest_uid']=nodes_ps[sumfp][0]
                headers['dest_IP']=nodes_ps[sumfp][1]['IP_address']
                msg['type']='POH_L3_R2'
                msg['content']['timestamp']=tt
                msg['content']['fingerprintL3']=fingerprint
                msg['content']['signer_nodeL3']=self._uid
                self.LOGGER.info("msg POH R2 prepared to be sent: "+str(headers))
                self._msgs_to_send.append([msg.copy(), headers.copy(), headers['dest_IP'], 'L3'])
                # Sends also back to client for information only!
                headers['dest_uid']=hdrs.get('sender_uid')
                headers['dest_IP']=hdrs.get('sender_node_IP')
                msg['type']='POH_L3_R1_DONE'
                self.LOGGER.info("POH R1 sending back to client, msg "+str(msg['uid'])+" " +str(headers))
                self._msgs_to_send.append([msg, headers, headers['dest_IP'], 'L3'])
            else:
                self.LOGGER.warning("Cannot send PoH R2 msg, no node with service active found!")

            

        elif (msg.get('type')=='POH_L3_R2' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # SECOND L3 NODE
            # first L3 node signature check
            if self._signature_verif(msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprintL3'], msg['content']['signer_nodeL3']):
                # Create temp fingerprint     
                fingerprint_L3L2 = self._do_signature(msg['content']['tx_hash'], msg['content']['fingerprintL3'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for nk in self._nodeslist_lower.keys():
                    if 'services' in self._nodeslist_lower[nk]:
                        if 'poh' in self._nodeslist_lower[nk]['services']:
                            if (self._nodeslist_lower[nk]['services']['poh'] == 1):
                                nodes_ps.append([nk, self._nodeslist_lower[nk]])
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint_L3L2.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp][0]
                    headers['dest_IP']=nodes_ps[sumfp][1]['IP_address']
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
            if self._signature_verif(msg['content']['tx_hash'], msg['content']['fingerprintL3'],
                                     msg['content']['fingerprint_L3L2'], msg['content']['signer_node_L3L2']):
                # sign the hash TODO first check if tx is eligible ???  
                fingerprint2 = self._do_signature(msg['content']['tx_hash'], msg['content']['fingerprintL3'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for nk in self._nodeslist.keys():
                    if 'services' in self._nodeslist[nk]:
                        if 'poh' in self._nodeslist[nk]['services']:
                            if (self._nodeslist[nk]['services']['poh'] == 1):
                                nodes_ps.append([nk, self._nodeslist[nk]])
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint2.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp][0]
                    headers['dest_IP']=nodes_ps[sumfp][1]['IP_address']
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
            if self._signature_verif(msg['content']['tx_hash'], msg['content']['fingerprintL3'],
                                     msg['content']['fingerprintL2'], msg['content']['signer_nodeL2']):
                # Create temp fingerprint     
                fingerprint_L2L1 = self._do_signature(msg['content']['tx_hash'], msg['content']['fingerprintL2'])
                # Select L1 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for nk in self._nodeslist_lower.keys():
                    if 'services' in self._nodeslist_lower[nk]:
                        if 'poh' in self._nodeslist_lower[nk]['services']:
                            if (self._nodeslist_lower[nk]['services']['poh'] == 1):
                                nodes_ps.append([nk, self._nodeslist_lower[nk]])
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint_L2L1.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp][0]
                    headers['dest_IP']=nodes_ps[sumfp][1]['IP_address']
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
            if self._signature_verif(msg['content']['tx_hash'], msg['content']['fingerprintL2'],
                                     msg['content']['fingerprint_L2L1'], msg['content']['signer_node_L2L1']):
                # sign the hash       
                fingerprint3 = self._do_signature(msg['content']['tx_hash'], msg['content']['fingerprintL2'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for nk in self._nodeslist.keys():
                    if 'services' in self._nodeslist[nk]:
                        if 'poh' in self._nodeslist[nk]['services']:
                            if (self._nodeslist[nk]['services']['poh'] == 1):
                                nodes_ps.append([nk, self._nodeslist[nk]])
                if len(nodes_ps) != 0:
                    headers=self._initheaders()
                    headers['service']='poh'
                    sumfp=(sum(fingerprint3.encode()))%len(nodes_ps)
                    headers['dest_uid']=nodes_ps[sumfp][0]
                    headers['dest_IP']=nodes_ps[sumfp][1]['IP_address']
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
            if self._signature_verif(msg['content']['tx_hash'], msg['content']['fingerprintL2'],
                                     msg['content']['fingerprintL1'], msg['content']['signer_nodeL1']):
                # Save Tx in good format
                tx_rec = { 'uid': msg['uid'], 'tx_hash': msg['content']['tx_hash'], 'timestamp': msg['content']['timestamp'],
                             'signer_nodeL3': msg['content']['signer_nodeL3'], 'fingerprintL3': msg['content']['fingerprintL3'],
                             'signer_nodeL2': msg['content']['signer_nodeL2'], 'fingerprintL2': msg['content']['fingerprintL2'],
                             'signer_nodeL1': msg['content']['signer_nodeL1'], 'fingerprintL1': msg['content']['fingerprintL1']}
                # Store Tx in received list
                self._txs_received.append(tx_rec)
                self.LOGGER.info("Tx is stored in recevied txs: " +str(msg['uid']))
            else:
                self.LOGGER.warning("POH storing in Tx received cancelled!")

        # FORWARD PoH messages from client that are for another node
        elif msg.get('type')=='POH_L3_R1' or msg.get('type')=='POH_L3_R2':
            IP_tosend=''
            if len(hdrs['dest_IP'])>6:
                IP_tosend=hdrs['dest_IP']
            else: # get from nodeslist
                for nk in self._nodeslist.keys():
                    if hdrs['dest_uid'] == nk and 'IP_address' in self._nodeslist[nk]:
                        IP_tosend=self._nodeslist[nk]['IP_address']
            if IP_tosend == '':
                self.LOGGER.warning("Impossible to forward message to "+str(hdrs['dest_uid'])+". Msg " +str(msg.get('uid'))+ " will be lost!")
            else:
                self.LOGGER.info("PoH message forwarded to " +str(IP_tosend))
                self._msgs_to_send.append([msg, hdrs, IP_tosend, 'L3'])

        # RECEIVING TXS collected by other L1 node
        elif msg.get('type')=='POH_TXS' and self._nodelevel == 'L1':
            if len(msg['content'])>0:
                for el in msg['content']:
                    if 'tx_hash' in el: #quick verif that it's a tx
                        self._txs_to_validate.append(el)
            self.LOGGER.info("PoH TXS receiving " +str(len(msg['content'])-1) + " txs.")

        # RECEIVING LATEST BLOCKS of other L1 node
        elif msg.get('type')=='POH_LATEST_BLOCKS' and self._nodelevel == 'L1':
            self._nodes_blocks[msg['content']['node_uid']]=msg['content']['blocks']
            self.LOGGER.info("PoH latest blocks received from node " +str(msg['content']['node_uid']))

        # RECEIVING GET BLOCKCHAIN REQUEST from other L1 node
        elif (msg.get('type')=='GET_BLOCKCHAIN') and self._nodelevel == 'L1':
            # Check if hash is corresponding to current or previous one
            if (msg['content'] == self._poh_blocks[-1][1] or  msg['content'] == self._poh_blocks[-2][1]):
                # Send it back
                # prepare the msg to be sent
                headers=self._initheaders()
                headers['service']=self._service
                headers['dest_uid']=hdrs.get('sender_uid')
                headers['dest_IP']=hdrs.get('sender_node_IP')
                msg=self._initmsg()
                msg['type']='BLOCKCHAIN_BACK'
                msg['content']=self._poh_blocks
                self._msgs_to_send.append([msg, headers, headers['dest_IP'], self._nodelevel])
            elif msg.get('trials') is None or msg.get('trials') < 3: # 'or' is lazy
                # Forward message to another potential node
                if msg.get('trials') is None:
                    msg['trials']=1
                else:
                    msg['trials']=msg['trials']+1
                sent=0
                for nk in self._nodeslist.keys():
                    if 'services' in self._nodeslist[nk] and sent == 0:
                        if 'poh' in self._nodeslist[nk]['services']:
                            if (self._nodeslist[nk]['services']['poh'] == 1):
                                if 'IP_address' in self._nodeslist[nk]:
                                    if self._nodeslist[nk]['IP_address'] != self._own_IP:
                                        hdrs['dest_IP']=self._nodeslist[nk]['IP_address']
                                        self._msgs_to_send.append([msg, hdrs, self._nodeslist[nk]['IP_address'], self._nodelevel])
                                        sent=sent+1
                                        self.LOGGER.info("msg "+msg['uid']+" forwarded request to node with poh service on node "+hdrs['dest_IP'])
                                else:
                                    self.LOGGER.warning("One "+self._nodelevel+" node has no IP set! Impossible to forward block get msg "+msg['uid']+" to it! "+nk)
            else:# We have not found file after 3 trials
                self.LOGGER.info("PoH have not found any node with the requested blockchain! " +str(msg['content']))

        # RECEIVING BLOCKCHAIN from other L1 node
        elif msg.get('type')=='BLOCKCHAIN_BACK' and self._nodelevel == 'L1':
            # Check if our last block is corresponding to the received blockchain one
            if (msg['content'][-1][1] == self._poh_blocks[-1][1] and msg['content'][-2][1] == self._poh_blocks[-2][1] and
                msg['content'][-1][0] == self._poh_blocks[-1][0] and msg['content'][-1][2] == self._poh_blocks[-1][2]) :
                if self._verif_blockchain(msg['content']):
                    self._poh_blocks = msg['content']
                    self.LOGGER.info("PoH blockchain has been replaced by new one with height: " + str(msg['content'][-1][0]))
                else:
                    self.LOGGER.info("PoH blockchain received is invalid!")
            else:
                self.LOGGER.info("PoH blockchain received is not corresponding!")

        return True

    def _signature_verif(self, tx_hash, input2, fingerprint, node_uid):
        try:
            nodepubkey=None
            nodesalllist={}
            nodesalllist.update(self._nodeslist)
            nodesalllist.update(self._nodeslist_lower)
            nodesalllist.update(self._nodeslist_upper)
            # get pubkey from nodeslist
            for nk in nodesalllist.keys():
                if nk == node_uid:
                    if 'pubkey' in nodesalllist[nk]:
                        nodepubkey=RSA.importKey(nodesalllist[nk]['pubkey'].encode())
                        #self.LOGGER.debug(str(node_uid)+" corresponding pubkey found!")
            if nodepubkey is not None:
                #Verify fingerprint
                hh=SHA256.new(tx_hash.encode())
                hh.update(str(input2).encode())
                verifier = PKCS115_SigScheme(nodepubkey)
                try:
                    verifier.verify(hh, binascii.unhexlify(fingerprint.encode()))
                    self.LOGGER.info("Tx " + str(tx_hash)+" has been validly signed by "
                                +str(node_uid))
                    return True
                except:
                    self.LOGGER.info("Tx " + str(tx_hash)+" has NOT BEEN VALIDLY signed by "
                                +str(node_uid))
                    return False
            else:
                self.LOGGER.info("Node " + str(node_uid)+" does not seem to have a pubkey!")
                return False
        except:
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to verify signature %s' %str(e))
            return False


    def _do_signature(self, tx_hash, input2):
        #Create fingerprint
        hh=SHA256.new(tx_hash.encode())
        hh.update(str(input2).encode())
        signer = PKCS115_SigScheme(self._privkey)
        return binascii.hexlify(signer.sign(hh)).decode()


    def _ticking_actions(self):
        super()._ticking_actions()

        time_in_epoch=divmod(time.time()-S.E_TRIM,60)[1]
        if self._nodelevel == 'L1':
            self.LOGGER.debug("Current Epoch: "+str(divmod(time.time()-S.E_TRIM,60)[0]) + " and last block's epoch: "+str(self._poh_blocks[-1][2]))
            if  time_in_epoch > 0 and time_in_epoch <= 10: # between 0 and 10 seconds after epoch start, share all received txs
                self._share_all_pending_txs()
            elif  time_in_epoch > 15 and time_in_epoch <= 25: # between 15 to 25 seconds after epoch start, to let time for txs to reach all L1
                # a new epoch started, compute new block
                self._compute_new_block()
            elif time_in_epoch > 30 and time_in_epoch <= 50: # between >30 and <50 seconds after new epoch, to let time for blocks to reach all L1
                # check the chain vs others
                self._check_latest_blocks()
            elif time_in_epoch > 50: # >50 seconds after epoch starts
                # epoch is finishing, finalize and clean pending txs
                self._finalizing()

        if time_in_epoch>0 and time_in_epoch <= 6: #every minute 
            if self._nodelevel == 'L1':
                # share the latest blocks
                self._share_latest_blocks() #TODO not sure it is useful (when no txs come?)
                # check blockchain
                self._check_blockchain()
                # save the blocks on disk
                with open(S.POH_BLOCKS_PATH, 'w') as b_file:
                    b_file.write(json.dumps(self._poh_blocks))       
        return


    def _share_all_pending_txs(self):
        # emptying the txs_received safely, in case new txs are currently received 
        temp_all=[]
        for i in range(0, len(self._txs_received)):
            temp_all.append(self._txs_received.pop(0))
        if len(temp_all)==0:
            return

        self._txs_to_validate.extend(temp_all)
        
        # prepare the msg to be sent with the txs received
        headers=self._initheaders()
        headers['service']='poh'
        msg=self._initmsg()
        msg['type']='POH_TXS'
        msg['content']=temp_all

        #send to all L1 nodes with PoH
        j=0
        for nk in self._nodeslist.keys():
            if 'services' in self._nodeslist[nk]:
                if 'poh' in self._nodeslist[nk]['services']:
                    if (self._nodeslist[nk]['services']['poh'] == 1):
                        if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                            headers['dest_IP']=self._nodeslist[nk]['IP_address']
                            self._msgs_to_send.append([msg, headers, self._nodeslist[nk]['IP_address'], 'L1'])
                            j=j+1
        self.LOGGER.info("POH txs shared with : "+str(j)+" L1 nodes.")
          

    def _compute_new_block(self):
        # don't run if finalize has not been done or no txs have come
        if self._last_epoch>0 or len(self._txs_to_validate)==0:
            return
        # determine epoch
        epoch=divmod(time.time()-S.E_TRIM, 60)[0]

        # order all txs by timestamps TODO check if txs have not already been included in a previous block?
        print(self._txs_to_validate)
        txs_pend=sorted(self._txs_to_validate, key=lambda t: t['timestamp'])
        self._txs_to_validate=[]

        # check all txs with nodes public keys
        txs_valid=[]
        for tx in txs_pend:
            if isinstance(tx['timestamp'], float) and divmod(tx['timestamp']-S.E_TRIM,60)[0] < epoch: # tx of current epoch are not taken into account yet
                if (#self._signature_verif(tx['tx_hash'], tx['timestamp'], tx['fingerprintL3'], tx['signer_nodeL3']) and NO ACCESS TO PUBKEY OF L3 node at L1 level
                    self._signature_verif(tx['tx_hash'], tx['fingerprintL3'], tx['fingerprintL2'], tx['signer_nodeL2']) and
                    self._signature_verif(tx['tx_hash'], tx['fingerprintL2'], tx['fingerprintL1'], tx['signer_nodeL1'])):
                    txs_valid.append(tx)
            else:
                self._txs_to_validate.append(tx)
                self.LOGGER.info(str(tx)+  " is from the next epoch, readded for next one!")
        self.LOGGER.info(str(len(txs_valid))+" txs have been validated.")
        
        # create new block hash
        if len(txs_valid)>0:
            new_height=self._poh_blocks[-1][0]+1 #previous height+1
            hh=SHA256.new(self._poh_blocks[-1][1].encode())# put previous block hash
            hh.update(str(epoch).encode()) # put epoch

            for tx in txs_valid:
                hh.update(tx['fingerprintL1'].encode())#put each tx L1 fingerprint

            b_hash=binascii.hexlify(hh.digest()).decode()#compute final hash

            # Add new block!
            self._poh_blocks.append([new_height, b_hash, epoch])
            self.LOGGER.info("A new block has been locally added! " + str([new_height, b_hash, epoch]))
            # also update own entry in nodes_blocks
            self._nodes_blocks[self._uid]={'current': self._poh_blocks[-1][1], 'previous': self._poh_blocks[-2][1], 'height': self._poh_blocks[-1][0]}

            # share latest blocks with all L1 nodes with PoH
            self._share_latest_blocks()

            # store info for later txs deletion
            self._txs_validated=txs_valid
            self._own_last_hash=b_hash
            self._last_epoch=epoch


    def _share_latest_blocks(self):

        # prepare the msg to be sent
        headers=self._initheaders()
        headers['service']='poh'
        msg=self._initmsg()
        msg['type']='POH_LATEST_BLOCKS'
        msg['content']['node_uid']=self._uid
        msg['content']['blocks']=self._nodes_blocks[self._uid]

        #send to all L1 nodes with PoH
        j=0
        for nk in self._nodeslist.keys():
            if 'services' in self._nodeslist[nk]:
                if 'poh' in self._nodeslist[nk]['services']:
                    if (self._nodeslist[nk]['services']['poh'] == 1):
                        if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                            headers['dest_IP']=self._nodeslist[nk]['IP_address']
                            self._msgs_to_send.append([msg, headers, self._nodeslist[nk]['IP_address'], 'L1'])
                            j=j+1
        self.LOGGER.info("POH last blocks shared with : "+str(j)+" L1 nodes.")

        
    def _check_latest_blocks(self):
        # determine epoch
        epoch=divmod(time.time()-S.E_TRIM, 60)[0]
        
        blocks=[]
        for nk in self._nodes_blocks.keys():
            if 'current' in self._nodes_blocks[nk] and 'previous' in self._nodes_blocks[nk] and 'height' in self._nodes_blocks[nk]:
                blocks.append([self._nodes_blocks[nk]['current'], self._nodes_blocks[nk]['previous'], self._nodes_blocks[nk]['height']])
                    
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

        if nb_chains==0:
            return # node has probably still not received all other nodes info

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
            self._switch_chain(chains, max_occ_chains, epoch)
            self._share_latest_blocks()
            self.LOGGER.info("Switching to highest chain: " + str(chains[max_occ_chains[0]]))
        elif max_occ > nb_chains/2: # there is a dominating chain and we are not on it:
            # Switch chain TODO privilege LONGEST chain if several existing? (already switching to HIGHEST)
            self._switch_chain(chains, max_occ_chains, epoch)
            self._share_latest_blocks()
            self.LOGGER.info("Switching to dominating chain: " + str(chains[max_occ_chains[0]]))         
        elif divmod(time.time()-S.E_TRIM,60)[1] > 40: # all nodes should have had time to compute next block
            # Switch chain TODO privilege longest chain if several existing?
            self._switch_chain(chains, max_occ_chains, epoch)
            self._share_latest_blocks()
            self.LOGGER.info("Switching to better chain: " + str(chains[max_occ_chains[0]]))
        else:
            self.LOGGER.info("For now staying on current chain: " + str(self._poh_blocks[-1]))# for now stay on chain


    def _finalizing(self):
        self.LOGGER.debug("Finalizing! " + str([len(self._txs_validated), self._own_last_hash]))
        # Check that our list of txs is the one of the winning block TODO if not winning block check which txs from txs_to_delete have not been added to blocks!
        if len(self._txs_validated)>0 and self._own_last_hash == self._poh_blocks[-1][1]:
            # prepare the msg to be sent
            headers=self._initheaders()
            headers['service']='net_storage'
            msg=self._initmsg()
            msg['type']='SAVE_BLOCK'
            msg['content']={'height': self._poh_blocks[-1][0],
                            'current_hash': self._poh_blocks[-1][1],
                            'previous_hash': self._poh_blocks[-2][1],
                            'epoch' : self._last_epoch,
                            'transactions': self._txs_validated}
            j=0
            # Send to all L2 nodes with net_storage service
            for nk in self._nodeslist_upper.keys():
                if 'services' in self._nodeslist_upper[nk]:
                    if 'net_storage' in self._nodeslist_upper[nk]['services']:
                        if (self._nodeslist_upper[nk]['services']['net_storage'] == 1):
                            if 'IP_address' in self._nodeslist_upper[nk]:
                                headers['dest_uid']=nk
                                headers['dest_IP']=self._nodeslist_upper[nk]['IP_address']
                                self._msgs_to_send.append([msg, headers, headers['dest_IP'], 'L2'])
                                j=j+1
            if j>0:
                self.LOGGER.info("Block has been saved in " +str(j)+" L2 nodes.")
            else:
                self.LOGGER.warning("No L2 node with net_storage service have been found!")

        # Reset info for deletion in any case
        self._own_last_hash == ''
        self._txs_validated = [] #TODO only if winning block
        self._last_epoch=0

        
    def _switch_chain(self, chains, max_occ_chains, epoch):
        # update last blocks
        self._poh_blocks[-1][1]=max_occ_chains[0]
        self._poh_blocks[-2][1]=chains[max_occ_chains[0]][2]
        self._poh_blocks[-1][0]=chains[max_occ_chains[0]][0]
        self._poh_blocks[-1][2]=epoch # current epoch
        self._nodes_blocks[self._uid]={'current': self._poh_blocks[-1][1], 'previous': self._poh_blocks[-2][1], 'height': self._poh_blocks[-1][0]}
        self._send_get_blockchain()


    def _send_get_blockchain(self):
        # Request blockchain to another L1 node
        # prepare the msg to be sent
        headers=self._initheaders()
        headers['service']=self._service
        msg=self._initmsg()
        msg['type']='GET_BLOCKCHAIN'
        msg['content']=self._poh_blocks[-1][1] # put last hash to only get compatible blockchain
        #request from another L1 node with poh service
        IP_sel=self._get_rand_nodeIP(self._service, self._nodeslist, self._own_IP)
        if len(IP_sel)>6:
            headers['dest_IP']=IP_sel
            self._msgs_to_send.append([msg, headers, IP_sel, 'L1'])
            self.LOGGER.info("PoH get blockchain from : "+IP_sel)
        else:
            self.LOGGER.warning("No other nodes with PoH service at L1 are available, no blockchain obtained!")


    def _check_blockchain(self):
        if self._verif_blockchain(self._poh_blocks):
            self.LOGGER.info("PoH, Blockchain verified.")
        else:
            self._send_get_blockchain()
            self.LOGGER.info("PoH, Blockchain invalid, trying to get a correct one.")


    def _verif_blockchain(self, v_poh_blocks):
        no_error = True
        for j in range(0,len(v_poh_blocks)-1):
            # check height
            if(v_poh_blocks[j+1][0]!=v_poh_blocks[j][0]+1):
                self.LOGGER.debug("Blockchain Height error at " +str(j)+ " "+str(v_poh_blocks[j+1][0]) +" vs "+ str(v_poh_blocks[j][0]))
                no_error = False
            # check epoch
            if(v_poh_blocks[j+1][2]<=v_poh_blocks[j][2]):
                self.LOGGER.debug("Blockchain Epoch error at " +str(j)+ ' '+str(v_poh_blocks[j+1][2]) +" vs "+ str(v_poh_blocks[j][2]))
                no_error = False
            # check hash
            if(v_poh_blocks[j+1][1]==v_poh_blocks[j][1]):
                self.LOGGER.debug("Blockchain duplicate hash: "+v_poh_blocks[j][1])
                no_error = False
        return no_error


#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2 and (sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3') :
        nodelevel=sys.argv[1]
        # Create Instance and start the service
        consumer = ServiceRunning(nodelevel, 'poh')
        consumer.run()
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
