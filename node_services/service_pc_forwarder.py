import pika
import time
import copy
import random
import string
import socket
import json
import sys
import os
import ssl
import base64
import traceback
from web3 import exceptions
from web3 import Web3
from web3.middleware import geth_poa_middleware
import logging
import binascii
import settings as S
from filelock import Timeout, FileLock
import signal
signal.signal(signal.SIGINT, signal.default_int_handler) # to ensure Signal to be received

#helper functions
def ii_helper(fily, sel):
    abc = b'k_AnuuTech'
    abcl = len(abc)
    if (str.isdigit(sel)):
        with open(fily, 'rb') as s_file:
            brezl=s_file.readlines()
        brez=brezl[int(sel)].replace(b'\n',b'')
        brezi=bytes(c ^ abc[i % abcl] for i, c in enumerate(brez)).decode()
        return (brezi)
    return None
def randomstring(stringLength):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))

lay_user='client_user'
lay_pass=ii_helper('node_data/access.bin', '1')
client_uid='PC_forwarder'
port=S.PORT
virtual_host=S.VHOST
last_blocks={}
pr_bc_id=ii_helper('node_data/access.bin', '20')

#init Logger
LOGGER = logging.getLogger('ANUUTECH_PRIVATE_BC_FORWARDER')
hdlr = logging.StreamHandler()
fhdlr = logging.FileHandler("logs/log_service_PR_forward.txt", mode='w')
format = logging.Formatter('%(asctime)-15s : %(message)s')
fhdlr.setFormatter(format)
hdlr.setFormatter(format)
LOGGER.addHandler(hdlr)
LOGGER.addHandler(fhdlr)
LOGGER.setLevel(logging.DEBUG)
#Ensure existing log file
LOGGER.info("LOGGER PR Forwarder has started\n")

#IP from file
own_IP=''
if os.path.isfile(S.IP_PATH):
    with FileLock(S.IP_PATH+'.lock', timeout=1):
        with open(S.IP_PATH, 'r') as ip_file:
            own_IP=ip_file.read().strip()
else:
    LOGGER.warning("No IP saved, trying to get one.")
    try:
        own_IP = requests.get('https://api.ipify.org', timeout=S.REQ_TIMEOUT).text
    except:
        LOGGER.error("ERROR! No IP found, impossible to api ipify: " + str(sys.exc_info()[0]))
        exit()

#get last blocks seen
if not os.path.isfile(S.PRIV_BC_LASTBLOCK_PATH):
    last_blocks[pr_bc_id]=0
    with open(S.PRIV_BC_LASTBLOCK_PATH, 'w') as pr_file:
        pr_file.write(json.dumps(last_blocks))
else:
    with open(S.PRIV_BC_LASTBLOCK_PATH, 'r') as pr_file:
        last_blocks=json.load(pr_file)
        
#create RCP connection 
w3= Web3(Web3.HTTPProvider('http://anuutechL3b'+ii_helper('node_data/access.bin', '8')+':'+ii_helper('node_data/access.bin', '15')))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)


def checkRPC():
    try:
        block=w3.eth.getBlock(last_blocks.get(pr_bc_id)+1)
        if len(block.transactions)>0:
            LOGGER.info("Block " + str(block.number)+ " has txs.")
            for tx in block.transactions:
                txh=ii_helper('node_data/access.bin', '19')+ii_helper('node_data/access.bin', '20')+tx.hex()#Private BC code, ID of Priv BC AKEY, AKEY tx hash
                #txh=ii_helper('node_data/access.bin', '19')+"TEST__TEST"#Private BC code, ID of Priv BC AKEY, AKEY tx hash
                prepare_msg(txh)
            time.sleep(1)
            last_blocks[pr_bc_id]=block.number
            with open(S.PRIV_BC_LASTBLOCK_PATH, 'w') as pr_file:
                pr_file.write(json.dumps(last_blocks))
        else:
            if (int(block.number) % 1000) == 0:
                LOGGER.info("Block "+str(block.number)+" is empty.")
            time.sleep(0.1)
            last_blocks[pr_bc_id]=block.number
    except KeyboardInterrupt:
        LOGGER.info("Stopped by user.")
        exit()
    except exceptions.BlockNotFound:
        #LOGGER.info("Block "+str(last_blocks.get(pr_bc_id)+1)+" has not been found.")
        time.sleep(3)
    except:
        LOGGER.info(str(traceback.format_exc()))
        time.sleep(5)
        

def prepare_msg(priv_tx_hash):
    msg=initmsg()
    try:
        # PoH_L3_R1    
        # Hash message
        msg['content']={}
        msg['content']['tx_hash']=priv_tx_hash
        headers=initheaders()
        headers['service']='poh'
        headers['dest_IP']=own_IP
        msg['type']='POH_L3_R1'
        LOGGER.info("msg prepared to be sent: "+str(headers))
        #print(msg)
        send_msg(headers, msg)
    except:
        LOGGER.warning( "<p>Problem while preparing message sending " + str(traceback.format_exc()) )


def send_msg(headers, msg):
    # Ensure all outgoing messages have the node IP well set
    headers['sender_node_IP']=own_IP
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters('localhost', port,virtual_host, credentials)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()

    try:        
        channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                               properties=pika.BasicProperties(headers=headers),
                               body=(json.dumps(msg)))
        connection2.close()
    except:
        mlist.insert(0,"Impossible to send msg, error occured!") 
        e = sys.exc_info()[1]
        LOGGER.info( "<p>Problem while sending, trying to reinit connections...: %s</p>" % e )
        try:
            connection2.close() 
        except:
            LOGGER.info('Problem while sending and impossible to close connection2')

def initmsg():
    msg_empty = {
        'uid': randomstring(12),
        'content': {},
        'type': '',
        'timestamp': time.time(),
        'version': S.SW_VERSION
        }
    return msg_empty

def initheaders():
    basic_headers = {
        'sender_uid': client_uid,
        'sender_node_IP': '',
        'dest_uid': '',
        'dest_IP': '',
        'dest_all': '',
        'service': '',
        'service_forward': '',
        'retry': 0,
        'fee_tx_hash': ''
        }
    return basic_headers


#----------------------------------------------------------------
def main():

    while True:
        try:
            checkRPC()
        except KeyboardInterrupt:
            break
        
if __name__ == '__main__':
    main()
