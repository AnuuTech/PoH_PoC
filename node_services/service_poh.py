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
import random
from collections import Counter
from tools_blockchain import check_block

class ServiceRunning(ReconnectingNodeConsumer):
    _light_bc=[] # all blocks of this node (without txs) [height, hash, epoch]
    _nodes_blocks={} # last blocks of each nodes { node_uid: { height : block, height-1 : block-1, ...}
    _block_candidates={} # block candidate from each node: { node_uid : block }
    _txs_received=[] # txs that have been directly received by node
    _txs_to_validate=[] # all txs, received directly and shared from other nodes, that have to be validated
    _own_last_hash=''
    _current_epoch=0
    _sharing_done = False
    _invalidBC = True # at start do not participate to consensus until catching up

    def _initnode(self):
        super()._initnode()
        #Load blockchain
        if os.path.isfile(S.POH_BLOCKS_PATH):
            with open(S.POH_BLOCKS_PATH, 'r') as b_file:
                self._light_bc=json.load(b_file)
        if len(self._light_bc)<2:
            # Genesis block
            height=0
            epoch=0
            # Create second block
            hh=SHA256.new(S.GENESIS_HASH.encode())#put previous block hash
            hh.update(str(1).encode()) #put current epoch
            b_hash2=binascii.hexlify(hh.digest()).decode()
            self._light_bc=[[height, S.GENESIS_HASH, epoch],
                              [height+1, b_hash2, epoch+1]]

        #Fill in nodes_blocks (two last blocks)
        self._nodes_blocks[self._uid]=[]
        self._nodes_blocks[self._uid].append({'height': self._light_bc[-2][0],
                                              'current_hash': self._light_bc[-2][1],
                                              'epoch': self._light_bc[-2][2]})
        self._nodes_blocks[self._uid].append({'height': self._light_bc[-1][0],
                                              'current_hash': self._light_bc[-1][1],
                                              'epoch': self._light_bc[-1][2],
                                              'previous_hash': self._light_bc[-2][1]})

        self._node_tick_interval=5 #overriding the one of service_class
        self.LOGGER.info("INITALISATION poh service done")
 
    def _msg_process(self, msg, hdrs):

        if (msg.get('type')=='POH_L3_R1' and (hdrs.get('dest_uid') == self._uid or
                                               hdrs.get('dest_IP') == self._own_IP)):
            # First CHECK FEE is paid and correct
            if msg['content']['tx_hash'].startswith(self.ii_helper('node_data/access.bin', '19')): # private blockchain hash
                msg['content']['tx_hash']=S.PRIV_BC_PRECODE+msg['content']['tx_hash'][10:]
            elif not self._check_fee(msg, hdrs, S.FEE_POH, self.ii_helper('node_data/access.bin', '16')):
                # Message is thus not processed
                return True
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
                # Select L1 node based on hash (sum of all characters), restricted to nodes with poh service
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
                self.LOGGER.info("Tx is stored in received txs: " +str(msg['uid']))
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
            if IP_tosend == '': # TODO implement a workaround when this happens
                self.LOGGER.warning("Impossible to forward message to "+str(hdrs['dest_uid'])+". Msg " +str(msg.get('uid'))+ " will be lost!")
            else:
                self.LOGGER.info("PoH message forwarded to " +str(IP_tosend))
                self._msgs_to_send.append([msg, hdrs, IP_tosend, 'L3'])

        # RECEIVING LAST BLOCKS AND TXS collected by other L1 node 
        elif msg.get('type')=='POH_TXS_BLOCKS' and self._nodelevel == 'L1':
            if 'transactions' in msg['content'] and len(msg['content']['transactions'])>0:
                for el in msg['content']['transactions']:
                    if 'tx_hash' in el: #quick verif that it's a tx
                        self._txs_to_validate.append(el)
                self.LOGGER.info("PoH TXS receiving " +str(len(msg['content']['transactions'])) + " txs.")
            if 'blocks' in msg['content'] and 'node_uid' in msg['content']:
                self._nodes_blocks[msg['content']['node_uid']]=msg['content']['blocks']
                self.LOGGER.info("PoH latest blocks received from node " +str(msg['content']['node_uid']))
            
        # RECEIVING BLOCK CANDIDATE of other L1 node
        elif msg.get('type')=='POH_BLOCK_CANDIDATE' and self._nodelevel == 'L1':
            if 'node_uid' in msg['content'] and 'block' in msg['content']: 
                self._block_candidates[msg['content']['node_uid']]=msg['content']['block']
                self.LOGGER.info("PoH block candidate received from node " +str(msg['content']['node_uid']))

        # RECEIVING GET BLOCKCHAIN REQUEST from other L1 node
        elif (msg.get('type')=='GET_BLOCKCHAIN') and self._nodelevel == 'L1':
            # Check if hash is corresponding to current or previous one
            if (not self._invalidBC and (msg['content'] == self._light_bc[-1][1] or  msg['content'] == self._light_bc[-2][1])):
                # Send it back
                # prepare the msg to be sent
                headers=self._initheaders()
                headers['service']=self._service
                headers['dest_uid']=hdrs.get('sender_uid')
                headers['dest_IP']=hdrs.get('sender_node_IP')
                msg=self._initmsg()
                msg['type']='BLOCKCHAIN_BACK'
                msg['content']=self._light_bc
                self._msgs_to_send.append([msg, headers, headers['dest_IP'], self._nodelevel])
            elif msg.get('trials') is None or msg.get('trials') < 3: # 'or' is lazy
                # Forward message to another potential node
                if msg.get('trials') is None:
                    msg['trials']=1
                else:
                    msg['trials']=msg['trials']+1
                sent=0
                ns_keys=list(self._nodeslist.keys())
                random.shuffle(ns_keys)
                for nk in ns_keys:
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
            if self._verif_blockchain(msg['content']):
                self._light_bc = msg['content']
                self.__invalidBC = False # back to normal
                self.LOGGER.info("PoH blockchain has been replaced by new one with height: " + str(msg['content'][-1][0]))
            else:
                self.LOGGER.info("PoH blockchain received is invalid!")

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
            self.LOGGER.debug("Current Epoch: "+str(divmod(time.time()-S.E_TRIM,60)[0]) + " and last block's epoch: "+str(self._light_bc[-1][2]))
            if  time_in_epoch > 0 and time_in_epoch <= 7.5: # between 0 and 7.5 seconds after epoch start, share all received txs and last blocks
                self._share_pending_txs_and_blocks()
                # check blockchain
                self._check_blockchain()
                # save the blocks on disk if not invalid
                if not self._invalidBC:
                    with open(S.POH_BLOCKS_PATH, 'w') as b_file:
                        b_file.write(json.dumps(self._light_bc))  
            elif  time_in_epoch > 24 and time_in_epoch <= 36: # between 27.5 to 35 seconds after epoch start, to let time for txs to reach all L1
                # a new epoch started, compute new block
                self._check_latest_blocks()
                self._compute_new_block()
            elif time_in_epoch > 52.5: # >50 seconds after epoch starts
                # epoch is finishing, finalize and clean pending txs
                self._finalizing()


    def _share_pending_txs_and_blocks(self):
        # do it once per epoch
        if self._sharing_done:
            return
        # emptying the txs_received safely, in case new txs are currently received 
        temp_all=[]
        for i in range(0, len(self._txs_received)):
            temp_all.append(self._txs_received.pop(0))
##        if len(temp_all)==0: For now always send to have last blocks updated
##            return

        self._txs_to_validate.extend(temp_all)
        
        # prepare the msg to be sent with the txs received and last blocks
        headers=self._initheaders()
        headers['service']='poh' 
        msg=self._initmsg()
        msg['type']='POH_TXS_BLOCKS'
        msg['content']['transactions']=temp_all
        msg['content']['node_uid']=self._uid
        if not self._invalidBC: # we don't want to share our blocks if BC is invalid
            msg['content']['blocks']=self._nodes_blocks[self._uid]

        #send to all L1 nodes with PoH
        j=0
        for nk in self._nodeslist.keys():
            if 'services' in self._nodeslist[nk]:
                if 'poh' in self._nodeslist[nk]['services']:
                    if (self._nodeslist[nk]['services']['poh'] == 1):
                        if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                            headers['dest_IP']=self._nodeslist[nk]['IP_address']
                            self._msgs_to_send.append([msg, headers.copy(), self._nodeslist[nk]['IP_address'], 'L1'])
                            #self.LOGGER.info(str(self._msgs_to_send[-1]))
                            j=j+1
        self._sharing_done = True
        self.LOGGER.info("POH " + str(len(temp_all))+" txs + last blocks shared with : "+str(j)+" L1 nodes.")

        
    def _check_latest_blocks(self):
        # determine epoch
        epoch=divmod(time.time()-S.E_TRIM, 60)[0]
        self._current_epoch=epoch
        
        blocks=[]
        for nk in self._nodes_blocks.keys():
            if len(self._nodes_blocks[nk])>0 and 'current_hash' in self._nodes_blocks[nk][-1] and 'previous_hash' in self._nodes_blocks[nk][-1] and 'height' in self._nodes_blocks[nk][-1]:
                blocks.append([self._nodes_blocks[nk][-1]['current_hash'], self._nodes_blocks[nk][-1]['previous_hash'], self._nodes_blocks[nk][-1]['height']])
                    
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
            if c == self._light_bc[-1][1] and chains[c][2] == self._light_bc[-2][1] and chains[c][0] == self._light_bc[-1][0]:
                own_occ= chains[c][1]

        # decide what chain to follow
        if own_occ == max_occ and self._light_bc[-1][0]>=chains[max_occ_chains[0]][0]: # same occurence and height is same or higher -->stay on chain
            self.LOGGER.info("Staying on best chain: " + str(self._light_bc[-1]))
        elif own_occ == max_occ and self._light_bc[-1][0]<chains[max_occ_chains[0]][0]: # same occurence but height is lower --> switch chain
            self._update_chain([chains[max_occ_chains[0]][0], max_occ_chains[0], chains[max_occ_chains[0]][2]]) #([height, current_hash, previous_hash])
            #self._share_latest_blocks()
            self.LOGGER.info("Switching to highest chain: " + str(chains[max_occ_chains[0]]))
        elif max_occ > nb_chains/2: # there is a dominating chain and we are not on it:
            # Switch chain TODO privilege LONGEST chain if several existing? (already switching to HIGHEST)
            self._update_chain([chains[max_occ_chains[0]][0], max_occ_chains[0], chains[max_occ_chains[0]][2]]) #([height, current_hash, previous_hash])
            #self._share_latest_blocks()
            self.LOGGER.info("Switching to dominating chain: " + str(chains[max_occ_chains[0]]))         
        elif divmod(time.time()-S.E_TRIM,60)[1] > 30: # all nodes should have had time to compute next block
            # Switch chain TODO privilege longest chain if several existing?
            self._update_chain([chains[max_occ_chains[0]][0], max_occ_chains[0], chains[max_occ_chains[0]][2]]) #([height, current_hash, previous_hash])
            #self._share_latest_blocks()
            self.LOGGER.info("Switching to better chain: " + str(chains[max_occ_chains[0]]))
        else:
            self.LOGGER.info("For now staying on current chain: " + str(self._light_bc[-1]))# for now stay on chain


    def _compute_new_block(self):
        # don't run if finalize has not been done or no txs have come or BC is not correct
        if len(self._own_last_hash) >0 or len(self._txs_to_validate)==0 or self._invalidBC:
            return

        epoch=self._current_epoch

        # order all txs by timestamps TODO check if txs have not already been included in a previous block?
        #print(self._txs_to_validate)
        txs_pend=sorted(self._txs_to_validate, key=lambda t: t['timestamp'])
        self._txs_to_validate=[]

        # check all txs with nodes public keys
        txs_valid=[]
        for tx in txs_pend:
            if not isinstance(tx['timestamp'], float) or divmod(tx['timestamp']-S.E_TRIM,60)[0] < epoch-S.POH_MAX_TX_AGE:
                self.LOGGER.info(str(tx)+  " is invalid or too old and thus discarded!")
            elif divmod(tx['timestamp']-S.E_TRIM,60)[0] < epoch: # tx of current epoch are not taken into account yet
                if (#self._signature_verif(tx['tx_hash'], tx['timestamp'], tx['fingerprintL3'], tx['signer_nodeL3']) and NO ACCESS TO PUBKEY OF L3 node at L1 level
                    self._signature_verif(tx['tx_hash'], tx['fingerprintL3'], tx['fingerprintL2'], tx['signer_nodeL2']) and
                    self._signature_verif(tx['tx_hash'], tx['fingerprintL2'], tx['fingerprintL1'], tx['signer_nodeL1'])):
                    txs_valid.append(tx)
                else:
                    self.LOGGER.info(str(tx)+  " is invalid and thus discarded!")
            else:
                self._txs_to_validate.append(tx)
                self.LOGGER.info(str(tx)+  " is from the next epoch, readded for next one!")
        self.LOGGER.info(str(len(txs_valid))+" txs have been validated.")
        
        # create new block hash
        if len(txs_valid)>0:
            new_height=self._light_bc[-1][0]+1 #previous height+1
            hh=SHA256.new(self._light_bc[-1][1].encode())# put previous block hash
            hh.update(str(epoch).encode()) # put epoch

            for tx in txs_valid:
                hh.update(tx['fingerprintL1'].encode())#put each tx L1 fingerprint

            b_hash=binascii.hexlify(hh.digest()).decode()#compute final hash

            # Add new block candidate !
            self._block_candidates[self._uid]={'height': new_height,
                                               'current_hash': b_hash,
                                               'previous_hash': self._light_bc[-1][1],
                                               'epoch' : epoch,
                                               'transactions': txs_valid}
            
            # share latest blocks with all L1 nodes with PoH
            self._share_block_candidate()

            # store info for later txs deletion
            self._own_last_hash=b_hash


    def _share_block_candidate(self):
        # don't share if invalid blockchain
        if self._invalidBC:
            return
        # prepare the msg to be sent
        headers=self._initheaders()
        headers['service']='poh'
        msg=self._initmsg()
        msg['type']='POH_BLOCK_CANDIDATE'
        msg['content']['node_uid']=self._uid
        msg['content']['block']=self._block_candidates[self._uid]

        #send to all L1 nodes with PoH
        j=0
        for nk in self._nodeslist.keys():
            if 'services' in self._nodeslist[nk]:
                if 'poh' in self._nodeslist[nk]['services']:
                    if (self._nodeslist[nk]['services']['poh'] == 1):
                        if 'IP_address' in self._nodeslist[nk] and self._nodeslist[nk]['IP_address'] != self._own_IP:
                            headers['dest_IP']=self._nodeslist[nk]['IP_address']
                            self._msgs_to_send.append([msg, headers.copy(), self._nodeslist[nk]['IP_address'], 'L1'])
                            j=j+1
        self.LOGGER.info("POH Block candidate shared with "+str(j)+" L1 nodes.")

        
    def _finalizing(self):
        self._sharing_done = False # Reset anyway now
        # only finalize if BC is valid and not already finalized
        if self._invalidBC or len(self._own_last_hash)==0:
            return      
        self.LOGGER.debug("Finalizing! " + str(self._own_last_hash))
        winning_block={}
        # Compare candidate blocks by ordering them per number of transactions
        blo_nb=[]
        for nk in self._block_candidates.keys():
            if ('height' in self._block_candidates[nk] and 'current_hash' in self._block_candidates[nk] and 'previous_hash' in self._block_candidates[nk] and
                'epoch' in self._block_candidates[nk] and 'transactions' in self._block_candidates[nk]):
                blo_nb.append([nk, self._block_candidates[nk]['height'], self._block_candidates[nk]['current_hash'], self._block_candidates[nk]['previous_hash'],
                        self._block_candidates[nk]['epoch'], len(self._block_candidates[nk]['transactions'])])
        sorted_blo_nb = sorted(blo_nb, key=lambda x: (x[5], x[2]), reverse=True) # Ordered by decreasing nb of txs then by hash
        self.LOGGER.debug("Block candidates ordered: "+str(sorted_blo_nb))
        # Check that block is valid
        blo_is_valid=False
        for j in range(0, len(sorted_blo_nb)):
            # check corresponding previous hash, valid epoch and correct height
            if sorted_blo_nb[j][3] != self._light_bc[-1][1] or sorted_blo_nb[j][4] != self._current_epoch or sorted_blo_nb[j][1] != self._light_bc[-1][0]+1 :
                self.LOGGER.info("Block is invalidly composed, trying next block candidate. "+str(sorted_blo_nb[j]))
                continue #go to next possible block
            # check all txs
            sign_are_valid=True
            for tx in self._block_candidates[sorted_blo_nb[j][0]]['transactions']:
                if (not isinstance(tx['timestamp'], float) or not
                    self._signature_verif(tx['tx_hash'], tx['fingerprintL3'], tx['fingerprintL2'], tx['signer_nodeL2']) or not
                    self._signature_verif(tx['tx_hash'], tx['fingerprintL2'], tx['fingerprintL1'], tx['signer_nodeL1'])):
                    # invalid signature
                    sign_are_valid=False
                    self.LOGGER.info(str(tx['tx_hash'])+  " some signature is invalid, trying next block candidate.")
                    break
            # check hash is correct
            if sign_are_valid and check_block(self._block_candidates[sorted_blo_nb[j][0]]):
                blo_is_valid=True
                winning_block=self._block_candidates[sorted_blo_nb[j][0]]
                break
            else:
                self.LOGGER.info("Block "+str(sorted_blo_nb[j][2])+" is invalid, trying next block candidate.")

        if blo_is_valid:
            # Add new block!
            self._light_bc.append([winning_block['height'], winning_block['current_hash'], winning_block['epoch']])
            self.LOGGER.info("A new block with " +str(len(winning_block['transactions'])) + " txs has been locally added! " + str([winning_block['height'], winning_block['current_hash'], winning_block['epoch']]))
            # also update own entry in nodes_blocks
            self._nodes_blocks[self._uid].append(winning_block)

            # Check if and which txs of our own list have been added in the new block
            if winning_block['current_hash']!=self._block_candidates[self._uid]['current_hash']:
                # our block candidate is not the winning one, check txs to re-add
                added_txs_hashes=[el['tx_hash'] for el in winning_block['transactions']]
                itx=0
                for tx in self._block_candidates[self._uid]['transactions']:
                    if tx['tx_hash'] not in added_txs_hashes:
                        #tx has not been added, re-add
                        self._txs_to_validate.append(tx)
                        itx=itx+1
                self.LOGGER.info(str(itx)+" txs have been readded for next block.")
        
        # Send new block to L2 to be saved
        if blo_is_valid:
            # prepare the msg to be sent
            headers=self._initheaders()
            headers['service']='net_storage'
            msg=self._initmsg()
            msg['type']='SAVE_BLOCK'
            msg['content']=winning_block
            j=0
            # Send to all L2 nodes with net_storage service
            for nk in self._nodeslist_upper.keys():
                if 'services' in self._nodeslist_upper[nk]:
                    if 'net_storage' in self._nodeslist_upper[nk]['services']:
                        if (self._nodeslist_upper[nk]['services']['net_storage'] == 1):
                            if 'IP_address' in self._nodeslist_upper[nk]:
                                headers['dest_uid']=nk
                                headers['dest_IP']=self._nodeslist_upper[nk]['IP_address']
                                self._msgs_to_send.append([msg, headers.copy(), headers['dest_IP'], 'L2'])
                                j=j+1
            if j>0:
                self.LOGGER.info("Block has been saved in " +str(j)+" L2 nodes.")
            else:
                self.LOGGER.warning("No L2 node with net_storage service have been found!")
        else:
            self.LOGGER.info("No valid new block has been found.")


        # Reset values in any case
        self._own_last_hash = ''
        self._block_candidates = {}
        
        
    def _update_chain(self, best_chain):
        #best_chain=[height, current_hash, previous_hash]

        # find a node with the corresponding chain
        found=False
        for nk in self._nodes_blocks.keys():
            if (len(self._nodes_blocks[nk])>1 and
                'current_hash' in self._nodes_blocks[nk][-1] and 'previous_hash' in self._nodes_blocks[nk][-1] and
                'height' in self._nodes_blocks[nk][-1] and 'epoch' in self._nodes_blocks[nk][-1] and
                'current_hash' in self._nodes_blocks[nk][-2] and
                'height' in self._nodes_blocks[nk][-2] and 'epoch' in self._nodes_blocks[nk][-2]):
                #self.LOGGER.debug("UPDATECHAIN DEBUG0: " +str(best_chain)) 
                #self.LOGGER.debug("UPDATECHAIN DEBUG1: "+str(self._nodes_blocks[nk]))
                # Check all corresponding + valid consecutive blocks
                if (self._nodes_blocks[nk][-1]['current_hash']==best_chain[1] and 
                    self._nodes_blocks[nk][-1]['previous_hash']==best_chain[2] and
                    self._nodes_blocks[nk][-1]['height']==best_chain[0] and
                    self._nodes_blocks[nk][-2]['current_hash']==self._nodes_blocks[nk][-1]['previous_hash'] and
                    self._nodes_blocks[nk][-2]['height']+1==self._nodes_blocks[nk][-1]['height'] and
                    self._nodes_blocks[nk][-2]['epoch']<self._nodes_blocks[nk][-1]['epoch']):
                    found=True
                    break

        if found:
            # update last blocks
            self._nodes_blocks[self._uid]=self._nodes_blocks[nk].copy()
            # update light bc (two last blocks)
            self._light_bc[-1][0]=self._nodes_blocks[nk][-1]['height']
            self._light_bc[-1][1]=self._nodes_blocks[nk][-1]['current_hash']
            self._light_bc[-1][2]=self._nodes_blocks[nk][-1]['epoch']
            self._light_bc[-2][0]=self._nodes_blocks[nk][-2]['height']
            self._light_bc[-2][1]=self._nodes_blocks[nk][-2]['current_hash']
            self._light_bc[-2][2]=self._nodes_blocks[nk][-2]['epoch']
            self.LOGGER.info("Switched to new blockchain with latest hash: "+str(best_chain[1]))
            # check blockchain
            self._check_blockchain()
                
        else:
            self.LOGGER.warning("No corresponding valid blockchain found with latest hash: "+str(best_chain[1]))


    def _send_get_blockchain(self):
        # Request blockchain to another L1 node
        # prepare the msg to be sent
        headers=self._initheaders()
        headers['service']=self._service
        msg=self._initmsg()
        msg['type']='GET_BLOCKCHAIN'
        msg['content']=self._light_bc[-1][1] # put last hash to only get compatible blockchain
        #request from another L1 node with poh service
        IP_sel=self._get_rand_nodeIP(self._service, self._nodeslist, self._own_IP)
        if len(IP_sel)>6:
            headers['dest_IP']=IP_sel
            self._msgs_to_send.append([msg, headers, IP_sel, 'L1'])
            self.LOGGER.info("PoH getting blockchain from : "+IP_sel)
        else:
            self.LOGGER.warning("No other nodes with PoH service at L1 are available, no blockchain obtained!")


    def _check_blockchain(self):
        # limit size of node_blocks
        for nk in self._nodes_blocks.keys(): # Could be done only for self_uid
            if len(self._nodes_blocks[nk]) > S.POH_MAX_TX_AGE:
                self._nodes_blocks[nk].pop(0)
                self.LOGGER.debug(str(len(self._nodes_blocks[nk]))+ " blocks are currently stored for "+nk)
        # check chain
        if self._verif_blockchain(self._light_bc):
            self._invalidBC = False
            self.LOGGER.info("PoH, Blockchain verified.")
        else:
            self._invalidBC = True
            self._send_get_blockchain()
            self.LOGGER.info("PoH, Light blockchain invalid, trying to get a correct one.")


    def _verif_blockchain(self, v_light_bc):
        no_error = True
        for j in range(0,len(v_light_bc)-1):
            # check height
            if(v_light_bc[j+1][0]!=v_light_bc[j][0]+1):
                self.LOGGER.debug("Blockchain Height error at " +str(j)+ " "+str(v_light_bc[j+1][0]) +" vs "+ str(v_light_bc[j][0]))
                no_error = False
            # check epoch
            if(v_light_bc[j+1][2]<=v_light_bc[j][2]):
                self.LOGGER.debug("Blockchain Epoch error at " +str(j)+ ' '+str(v_light_bc[j+1][2]) +" vs "+ str(v_light_bc[j][2]))
                no_error = False
            # check hash
            if(v_light_bc[j+1][1]==v_light_bc[j][1]):
                self.LOGGER.debug("Blockchain duplicate hash: "+v_light_bc[j][1])
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
