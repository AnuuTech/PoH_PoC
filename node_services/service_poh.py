#import class_service
from service_class import ReconnectingNodeConsumer 
import sys
import os
import json
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
import binascii
import time

class ServiceRunning(ReconnectingNodeConsumer):
    POH_STAT_PATH='node_data/poh_stat.file'
    _poh_stats={}

    def _initnode(self):
        super()._initnode()
        #PoH stat updated from file
        if os.path.isfile(self.POH_STAT_PATH):
            with open(self.POH_STAT_PATH, 'r') as pst_file:
                self._poh_stats=json.load(pst_file)
        self.LOGGER.info("INITALISATION poh service done")
 
    def _msg_process(self, msg, hdrs):

        if (msg.get('type')=='POH_L3_R1' and (hdrs.get('dest_uid') == self._uid or
                                               hdrs.get('dest_IP') == self._own_IP)):
            #time.sleep(0.1)
            #Create fingerprint
            fingerprint = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], time.time())

            # Prepare query in good format
            db_query = { "uid": msg['uid'], "tx": msg['content']['tx'], "tx_hash": msg['content']['tx_hash'],
                         "timestamp": tt, "node_uid": self._uid, "fingerprint": fingerprint }
            # Insert Tx on DB
            self._updateDB('transactions_pending', db_query, None)
            self.LOGGER.info("Tx sent to pending Txs on DB" +str(db_query))

            # Sends back to client
            hdrs['dest_uid']=hdrs.get('sender_uid')
            hdrs['dest_IP']=hdrs.get('sender_node_IP')
            msgback=self._initmsg()
            msgback['uid']=msg['uid'] #keeps the same id, uid is the one set on DB for this tx
            msgback['type']='POH_L3_R1_DONE'
            msgback['content']['timestamp']=tt
            msgback['content']['tx']=msg['content']['tx']
            msgback['content']['tx_hash']=msg['content']['tx_hash']
            msgback['content']['fingerprint']=binascii.hexlify(fingerprint).decode()
            msgback['content']['signer_node']=self._uid
            self.LOGGER.info("POH R1 will send back "+str(msgback['uid'])+" " +str(hdrs))
            self._msgs_to_send.append([msgback, hdrs, hdrs['dest_IP'], 'L3'])

        elif (msg.get('type')=='POH_L3_R2' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # SECOND L3 NODE
            # first L3 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprint'], msg['content']['signer_node']):
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
                    snode_uid=list(nodes_ps.keys())[(sum(fingerprint_L3L2.encode()))%len(nodes_ps.keys())]
                    headers=initheaders()
                    headers['service']='poh'
                    headers['dest_uid']=snode_uid
                    msg['type']='POH_L2_R3'
                    msg['content']['fingerprint_L3L2']=fingerprint_L3L2
                    msg['content']['signer_node_L3L2']=self._uid
                    LOGGER.info("msg POH R3 prepared to be sent: "+str(headers))
                else:
                    LOGGER.warning("Cannot send PoH R3 msg, no node with service active found!")
            else:
                LOGGER.warning("POH R3 cancelled!")
                
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
                    snode_uid=list(nodes_ps.keys())[(sum(fingerprint2.encode()))%len(nodes_ps.keys())]
                    headers=initheaders()
                    headers['service']='poh'
                    headers['dest_uid']=snode_uid
                    msg['type']='POH_L2_R4'
                    msg['content']['fingerprint2']=fingerprint2
                    msg['content']['signer_node2']=self._uid
                    LOGGER.info("msg POH R4 prepared to be sent: "+str(headers))
                else:
                    LOGGER.warning("Cannot send PoH R4 msg, no node with service active found!")
            else:
                LOGGER.warning("POH R4 cancelled!")
                elif (msg.get('type')=='POH_L3_R2' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # SECOND L2 NODE
            # first L2 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprint2'], msg['content']['signer_node2']):
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
                    snode_uid=list(nodes_ps.keys())[(sum(fingerprint_L2L1.encode()))%len(nodes_ps.keys())]
                    headers=initheaders()
                    headers['service']='poh'
                    headers['dest_uid']=snode_uid
                    msg['type']='POH_L1_R5'
                    msg['content']['fingerprint_L2L1']=fingerprint_L2L1
                    msg['content']['signer_node_L2L1']=self._uid
                    LOGGER.info("msg POH R5 prepared to be sent: "+str(headers))
                else:
                    LOGGER.warning("Cannot send PoH R5 msg, no node with service active found!")
            else:
                LOGGER.warning("POH R5 cancelled!")
                
        elif (msg.get('type')=='POH_L2_R3' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # First L1 NODE
            # Second L2 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprint_L2L1'], msg['content']['signer_node_L2L1']):
                # sign the hash       
                fingerprint3 = self._do_signature(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'])
                # Select L2 node based on hash (sum of all characters), restricted to nodes with poh service
                nodes_ps=[]
                for n in self._nodeslist_lower:
                    if 'services' in n:
                        if 'poh' in n['services']:
                            if (n['services']['poh'] == 1):
                                nodes_ps.append(n)
                if len(nodes_ps) != 0:
                    snode_uid=list(nodes_ps.keys())[(sum(fingerprint2.encode()))%len(nodes_ps.keys())]
                    headers=initheaders()
                    headers['service']='poh'
                    headers['dest_uid']=snode_uid
                    msg['type']='POH_L1_R6'
                    msg['content']['fingerprint3']=fingerprint3
                    msg['content']['signer_node3']=self._uid
                    LOGGER.info("msg POH R6 prepared to be sent: "+str(headers))
                else:
                    LOGGER.warning("Cannot send PoH R6 msg, no node with service active found!")
            else:
                LOGGER.warning("POH R6 cancelled!")

        elif (msg.get('type')=='POH_L1_R6' and (hdrs.get('dest_uid') == self._uid or
                                                hdrs.get('dest_IP') == self._own_IP)):
            # Second L1 NODE
            # First L1 node signature check
            if self._signature_verif(msg['content']['tx'], msg['content']['tx_hash'], msg['content']['timestamp'],
                                     msg['content']['fingerprint3'], msg['content']['signer_node3']):
                # Prepare query in good format
                db_query = { "uid": msg['uid'], "tx": msg['content']['tx'], "tx_hash": msg['content']['tx_hash'], "timestamp": msg['content']['timestamp'],
                             "signer_nodeL3": msg['content']['signer_node'], "fingerprintL3": msg['content']['fingerprint'],
                             "signer_nodeL2": msg['content']['signer_node2'], "fingerprintL2": msg['content']['fingerprint2'],
                             "signer_nodeL1": msg['content']['signer_node3'], "fingerprintL1": msg['content']['fingerprint3']}
                # Insert Tx on DB
                self._updateDB('transactions_pending', db_query, None)
                self.LOGGER.info("Tx sent to pending Txs on DB" +str(db_query))
            else:
                LOGGER.warning("POH saving in DB cancelled!")

        elif (msg.get('type')=='POH_L3_R1' or msg.get('type')=='POH_L2_R3' or msg.get('type')=='POH_L1_R5'): # but not for current node --> forward to same level TODO lower levels?
            IP_tosend=''
            if len(hdrs['dest_IP'])>6:
                IP_tosend=hdrs['dest_IP']
            else: # get from nodeslist
                for n in self._nodeslist:
                    if hdrs['dest_uid'] == n['uid'] and 'IP_address' in n:
                        IP_tosend=n['IP_address']

            self.LOGGER.info("PoH R1 message forwarded to " +str(IP_tosend))
            self._msgs_to_send.append([msg, hdrs, IP_tosend, self._nodelevel])
            
        # Update poh stats
        if str(hdrs['sender_uid']) in list(self._poh_stats.keys()):
            self._poh_stats[hdrs['sender_uid']]=self._poh_stats[hdrs['sender_uid']]+1
        else:
            self._poh_stats[hdrs['sender_uid']]=1
        return True

    def _signature_verif(self, tx, tx_hash, timestamp, fingerprint, node_uid):
        # get pubkey from DB
        random.shuffle(defaultL3nodes)
        IP_DB=defaultL3nodes[0] # TODO get all net storage available nodes
        db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+IP_DB+':27017/?authMechanism=DEFAULT&authSource=admin'
        db_client = pymongo.MongoClient(db_url)
        at_db = db_client["AnuuTechDB"]
        nodes_col = at_db["nodes"]
        db_query = { "uid": node_uid }
        y=node_col.find_one(db_query)
        if y is None:
            LOGGER.info("Node " + str(node_uid)+" is not found in DB!")
        else:
            nodepubkey=RSA.importKey(y.get('pubkey'))
            #Verify fingerprint
            hh=SHA256.new(tx.encode())
            hh.update(tx_hash.encode())
            hh.update(str(timestamp).encode())
            verifier = PKCS115_SigScheme(nodepubkey)
            try:
                verifier.verify(hh, binascii.unhexlify(fingerprint.encode()))
                LOGGER.info("Msg " + str(msg['uid'])+" has been validly signed by "
                            +str(node_uid))
                return True
            except:
                LOGGER.info("Msg " + str(msg['uid'])+" has NOT BEEN VALIDLY signed by "
                            +str(node_uid))
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

        #do the consensus
        self._consensing()
        
        #write poh stats to file
        with open(self.POH_STAT_PATH, 'w') as pst_file:
            pst_file.write(json.dumps(self._poh_stats))

        self._stat_updateDB()        
        return

    def _consensing(self):
        # Check latest blocks on all L1 nodes
        nb_same_block
        nb_previous_block
        nb_block_diff=[] #ordered
        nb_majority=nb_tot_nodes/2+1
        if nb_block_diff[0] > nb_majority:
            # switch to chain [0]
        elif nb_block_diff[0] > nb_same_block+nb_previous_block: # ex: same: 25, 0: 30, 1: 10, prev: 3
            # switch to chain [0]
        else:
            # stay on current chain

        # Gets all pending txs of current epoch which are eligible
        # creates a new block hash with all 3 fingerprints of all eligible txs and the previous block hash
        # Puts new block into own copy of blockchain


    def _stat_updateDB(self):
        # Determine total sum of messages processed
        tot=0
        for cc in self._poh_stats.keys():
            tot=tot+self._poh_stats[cc]
        db_query = { "uid": self._uid }
        db_values_toset = {"$set":{"service_poh":{"nb_of_msg_processed": tot}}}
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
            consumer = ServiceRunning(nodelevel, 'poh')
            consumer.run()
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()
