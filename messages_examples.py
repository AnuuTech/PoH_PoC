# Examples of RabbitMQ messages to interact with AnuuTech network
# Both headers and message are necessary 

import pika
import time
import random
import json
import base64

IP_sel='192.168.1.99' # L3 node IP, with considered service running (see explorer)
client_uid='client_VBxErUiA' # client uid must start with 'client_' and be completed with 8 random character

def prepare_msg(rd):

    ### Broadcast chat message
    if rd == 0:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': '',
            'dest_IP': '',
            'dest_all': 'clients',
            'service': 'chat',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': {'username': 'MyNickName', 'chat_msg': 'Hello!'},
            'type': 'CHAT',
            'timestamp': time.time()
            }
        
    ### Private chat message 
    elif rd == 1:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': 'client_UvLAlWPZ', # recipient's client uid
            'dest_IP': '',
            'dest_all': '',
            'service': 'chat',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': {'username': 'MyNickName', 'chat_msg': 'Hello!'}, # should be encrypted: base64.b64encode(enc_key.encrypt(json.dumps(msg['content']).encode())).decode()
            'type': 'CHAT',
            'timestamp': time.time()
            }

    ### Encryption request for private chat
    elif rd == 2:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': 'client_UvLAlWPZ', # recipient's client uid
            'dest_IP': '',
            'dest_all': '',
            'service': 'chat',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': {'username': 'MyNickName', 'chat_msg': 'PUK attached', 'pubk': pubkey}, # pubkey should be public_key.exportKey('PEM').decode()
            'type': 'CHAT-PUK',
            'timestamp': time.time()
            }

    ### Encryption request ANSWER
    elif rd == 3:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': 'client_UvLAlWPZ', # recipient's client uid
            'dest_IP': '',
            'dest_all': '',
            'service': 'chat',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': {'username': 'MyNickName', 'chat_msg': 'Done', 'pubk': pubkey}, # pubkey should be public_key.exportKey('PEM').decode()
            'type': 'CHAT-PUK',
            'timestamp': time.time()
            }

    ### Proof-of-Hash initial request (PoH_L3_R1)
    elif rd == 4:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': 'L3Node_hSKXzf', # selected Layer 3 node uid 
            'dest_IP': '',
            'dest_all': '',
            'service': 'poh',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': {'tx_hash': '334d016f755cd6dc58c53a86e183882f8ec14f52fb05345887c8a5edd42c87b7'}, # binascii.hexlify((SHA256.new('Hello!'.encode())).digest()).decode()
            'type': 'POH_L3_R1',
            'timestamp': time.time()
            }

    ### Data storage - data sending
    elif rd == 6:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': '',
            'dest_IP': '',
            'dest_all': '',
            'service': 'data_storage',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': base64.b64encode(b'Hello!').decode(), # b'Hello!' = file read() with 'rb'
            'type': 'SAVE_DATA',
            'timestamp': time.time()
            }

    ### Data storage - get back data
    elif rd == 7:
        # headers
        headers = {
            'sender_uid': client_uid,
            'sender_node_IP': IP_sel,
            'dest_uid': '',
            'dest_IP': '',
            'dest_all': '',
            'service': 'data_storage',
            'retry': 0
            }

        # message
        msg={
            'uid': str(random.randrange(0,9999999)),
            'content': '188071675d5b19b30a49bfe5c2d776cc716a4cad2855ad7feadf02f7841e4069', # hash received back from 'SAVE_DATA' request
            'type': 'GET_DATA',
            'timestamp': time.time()
            }
    return [headers, msg]
        
#Basic send RabbitMQ msg implementation
def send_msg(headers, msg):
    lay_user='client_user'
    lay_pass='test_passwd' # to be replaced by L3 node client_user password
    port=5672
    virtual_host='anuutech'
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters(IP_sel, port, virtual_host, credentials)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()      
    channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                           properties=pika.BasicProperties(headers=headers),
                           body=(json.dumps(msg))) 
    connection2.close() 


# DEMO
#send a PoH initial message
hdrs, msg = prepare_msg(0)
send_msg(hdrs, msg)
