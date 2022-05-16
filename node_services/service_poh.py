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

        if (hdrs.get('type')=='POH_L3_R1' and hdrs.get('dest_uid') == self._uid):
            #time.sleep(0.1)
            #Create fingerprint
            tt=time.time()
            hh=SHA256.new(msg['content'].encode())
            hh.update(msg['content_hash'].encode())
            hh.update(str(tt).encode())
            signer = PKCS115_SigScheme(self._PRIVKEY)
            fingerprint = signer.sign(hh)

            # Prepare query in good format
            db_query = { "uid": msg['uid'], "content": msg['content'], "content_hash": msg['content_hash'],
                         "timestamp": tt, "node_uid": self._uid, "fingerprint": fingerprint }
            # Insert Tx on DB
            self._updateDB('transactions_pending', db_query, None)
            self.LOGGER.info("Tx sent to pending Txs on DB" +str(db_query))

            # Sends back to client
            hdrs['dest_uid']=hdrs.get('sender_uid')
            hdrs['dest_IP']=hdrs.get('sender_node_IP')
            hdrs['type']='POH_L3_R1_DONE'
            msgback=self._initmsg()
            msgback['uid']=msg['uid'] #keeps the same id, uid is the one set on DB for this tx
            msgback['content']='Tx successfully added to pending Txs, fingerprint is in content_hash'
            msgback['content_hash']=binascii.hexlify(fingerprint).decode()
            self.LOGGER.info("POH will send back "+str(msgback['uid'])+" " +str(hdrs))
            self._msgs_to_send.append([msgback, hdrs, hdrs['dest_IP'], 'L3'])

        elif (hdrs.get('type')=='POH_L3_R1'): # but not for current node --> forward
            IP_tosend=''
            if len(hdrs['dest_IP'])>6:
                IP_tosend=hdrs['dest_IP']
            else: # get from nodeslist
                for n in self._nodeslist:
                    if hdrs['dest_uid'] == n['uid'] and 'IP_address' in n:
                        IP_tosend=n['IP_address']

            self.LOGGER.info("PoH message forwarded to " +str(IP_tosend))
            self._msgs_to_send.append([msg, hdrs, IP_tosend, self._nodelevel])

        # Update poh stats
        if str(hdrs['sender_uid']) in list(self._poh_stats.keys()):
            self._poh_stats[hdrs['sender_uid']]=self._poh_stats[hdrs['sender_uid']]+1
        else:
            self._poh_stats[hdrs['sender_uid']]=1
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

        #write poh stats to file
        with open(self.POH_STAT_PATH, 'w') as pst_file:
            pst_file.write(json.dumps(self._poh_stats))

        self._stat_updateDB()        
        return

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
