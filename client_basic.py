import pika
import time
import tkinter
import threading
import socket
import random
import string
import json
import sys
import os
import ssl
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
import logging
import binascii
import pymongo
import urllib
import signal
signal.signal(signal.SIGINT, signal.default_int_handler) # to ensure Signal to be received

Title="AnuuTech Basic client V-0.1"

#helper function
def ii_helper(fily, sel):
    abc = b'k_AnuuTech'
    abcl = len(abc)
    if (str.isdigit(sel)):
        with open(fily, 'rb') as s_file:
            brezl=s_file.readlines()
        brez=brezl[int(sel)].replace(b'\n',b'')
        brezi=bytes(c ^ abc[i % abcl] for i, c in enumerate(brez)).decode()
        return (brezi)
    return null

lay_user='client_user'
lay_pass=ii_helper('node_data/access.bin', '1')
db_pass=ii_helper('node_data/access.bin', '12')
nodeslist={} # UIDs and IPs of all nodes with chat service
defaultL3nodes=[]
port=5672
virtual_host='anuutech'
IP_sel=[]
connected=False
threads=[]
msgtype=0
chat_msg="AnuuTech is coming!"
dest_address=''
client_uid_path='client_uid.file'
pubkey_path='atclient_pubkey.file'
privkey_path='atclient_privkey.file'
contacts={}
msg_waiting=[]



#get hostname
hostname=socket.gethostname()

#check local/debug mode
if len(sys.argv) == 2:
    if sys.argv[1] == 'local':
        defaultL3nodes.append('192.168.1.71')

#unique Client ID
def randomstring(stringLength):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))
if not os.path.isfile(client_uid_path):
    print(client_uid_path + " does not exist. Creating UID.")
    client_uid="client_"+randomstring(8)
    print("client UID has been defined: " + client_uid)
    with open(client_uid_path, 'w') as uid_file:
        uid_file.write(client_uid)
else:
    with open(client_uid_path, 'r') as uid_file:
        client_uid=uid_file.read().strip()
name='Mr No_Name'

#init Logger
LOGGER = logging.getLogger('ANUUTECH_EMULATOR_LOGGER')
hdlr = logging.StreamHandler()
logfilename='log_aclient_'+client_uid+'.txt'
fhdlr = logging.FileHandler(logfilename, mode='w')
format = logging.Formatter('%(asctime)-15s : %(message)s')
fhdlr.setFormatter(format)
hdlr.setFormatter(format)
LOGGER.addHandler(hdlr)
LOGGER.addHandler(fhdlr)
LOGGER.setLevel(logging.DEBUG)
LOGGER.info(Title)

#get RSA keys
if not os.path.isfile(pubkey_path) or not os.path.isfile(privkey_path):
    # issue keys
    private_key = RSA.generate(1024)
    public_key = private_key.publickey()
    LOGGER.info('No RSA keys found, new ones are created')
    with open (privkey_path, "wb") as prv_file:
        prv_file.write(private_key.exportKey('PEM','annu_seed-l'))
    with open (pubkey_path, "wb") as pub_file:
        pub_file.write(public_key.exportKey('PEM'))
else:
    with open (privkey_path, "rb") as prv_file:
        private_key=RSA.importKey(prv_file.read(),'annu_seed-l')
    with open (pubkey_path, "rb") as pub_file:
        public_key=RSA.importKey(pub_file.read())
        LOGGER.debug('RSA keys sucessfully loaded.')
PRK=PKCS1_OAEP.new(private_key)

#get default L3nodes
defaultL3nodes_hosts=['at-clusterL3'+ii_helper('node_data/access.bin', '8'),
                      'at-clusterL3b'+ii_helper('node_data/access.bin', '8')]
for dgh in defaultL3nodes_hosts:
    try:
        defaultL3nodes.append(socket.gethostbyname(dgh))
        LOGGER.info('Defaultnode obtained: '+ socket.gethostbyname(dgh) )
    except:
        LOGGER.info("WARNING! Impossible to get one of the default L3 node: " + dgh+ str(sys.exc_info()[0]))

if len(defaultL3nodes)==0:
    LOGGER.info("ERROR! Impossible to get any default L3 node... exiting.")
    exit()

class App:

    def __init__(self, wind):
        global varGr, mlist, name, nodeslist, chat_msg, dest_address, IPs, varGr31, IP_sel
        frame = tkinter.Frame(wind)
        getL3nodesList()
        IPs=list(nodeslist.values())

        w0 = tkinter.Label(frame, text="UNIQUE ADDRESS:")
        w0.pack(side = tkinter.TOP, anchor = tkinter.W)

        w0b = tkinter.Text(frame, height=1)
        w0b.insert(1.0, client_uid)
        w0b.pack(side = tkinter.TOP, anchor = tkinter.W)
        w0b.configure(bg=frame.cget('bg'), relief="flat")
        w0b.configure(state="disabled")
        
        w2 = tkinter.Label(frame, text="Your name to display:")
        w2.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd = (frame.register(self.callbackE))
        self.w = tkinter.Entry(frame, validate='key', validatecommand=(vcmd, '%P'), width=15) 
        self.w.insert(0,name)
        self.w.pack(side = tkinter.TOP, anchor = tkinter.W)
        
        w5 = tkinter.Label(frame, text="Information:")
        w5.pack(side = tkinter.TOP, anchor = tkinter.W)

        mlist = tkinter.Listbox(frame, height=5, width=100)
        mlist.pack(side=tkinter.TOP, fill=tkinter.BOTH)

        w3 = tkinter.Label(frame, text="Select message type:")
        w3.pack(side = tkinter.TOP, anchor = tkinter.W)

        varGr = tkinter.StringVar()
        b = tkinter.Radiobutton(frame, variable=varGr, text="AnuuChat message", value=0,
                                        command=self.mtype)
##        b.pack(anchor=tkinter.W)
##        b = tkinter.Radiobutton(frame, variable=varGr, text="TEST ping", value=1,
##                                        command=self.mtype)
##        b.pack(anchor=tkinter.W)
##        b = tkinter.Radiobutton(frame, variable=varGr, text="TEST ping", value=2,
##                                        command=self.mtype)
        b.pack(anchor=tkinter.W)
        b = tkinter.Radiobutton(frame, variable=varGr, text="HMES", value=3,
                                        command=self.mtype)
        b.pack(anchor=tkinter.W)

        varGr.set(0)

        w31 = tkinter.Label(frame, text="Select cluster node:")
        w31.pack(side = tkinter.TOP, anchor = tkinter.W)

        varGr31 = tkinter.StringVar()
        if len(sys.argv) == 2:
            if sys.argv[1] == 'local':
                IPs.insert(0,'192.168.1.71')
        for j in range(min(len(IPs),9)): # only up to 9 IPs shown
                b = tkinter.Radiobutton(frame, variable=varGr31, text=IPs[j], value=j,
                                        command=self.ipsel)
                b.pack(anchor=tkinter.W)
        varGr31.set(0)
        if len(IPs)==0:
            print("ERROR: no cluster nodes found...")
            exit()
        IP_sel = IPs[0] #TODO select best ping?
   
        w8 = tkinter.Label(frame, text="AnuuChat message to send:")
        w8.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd2 = (frame.register(self.callbackE2))
        w9 = tkinter.Entry(frame, validate='all', validatecommand=(vcmd2, '%P'), width=75) 
        w9.insert(0,chat_msg)
        w9.pack(side = tkinter.TOP, anchor = tkinter.W)

        w6 = tkinter.Label(frame, text="AnuuChat recipient's address (leave blank for all):")
        w6.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd3 = (frame.register(self.callbackE3))
        w7 = tkinter.Entry(frame, validate='all', validatecommand=(vcmd3, '%P'), width=15) 
        w7.insert(0,dest_address)
        w7.pack(side = tkinter.TOP, anchor = tkinter.W)
        
        self.button = tkinter.Button(
                frame, text="QUIT", command=self.quitting
                )
        self.button.pack(side = tkinter.RIGHT)
              
        self.conn = tkinter.Button(
                frame, text="Connect", command=conn
                )
        self.conn.pack(side = tkinter.LEFT)

        self.deconn = tkinter.Button(
                frame, text="Disconnect", command=disconn
                )
        self.deconn.pack(side = tkinter.LEFT)

        self.send = tkinter.Button(
                frame, text="Send Msg", command=prepare_msg
                )
        self.send.pack(side = tkinter.LEFT)

        
        frame.pack()

        tempstr="Current list of "+str(len(nodeslist))+" L3 nodes of AnuuTech Network."
        mlist.insert(0,tempstr)
        

    def quitting(self):
        global connected
        connected=False
        time.sleep(1.1)
        cleanall()
        root.destroy()

    def mtype(self):
        global msgtype
        msgtype = int(varGr.get())
        if msgtype==0:
            ts="CHAT"
        else:
            ts="HMES"
        selection = "You selected the message type: " + ts
        LOGGER.info(selection) 

    def ipsel(self):
        global IP_sel, IPs, varGr31
        IP_sel=IPs[int(varGr31.get())]
        selection = "You selected the ip " + str(IP_sel)
        print(selection)     

    def callbackE(self, P):
        global name
        P=str(P)
        if len(P) <15:
            name = P 
            return True
        else:
            mlist.insert(0,"Name must contain at max 15 characters!")
            return False

    def callbackE2(self, P):
        global chat_msg
        P=str(P)
        if len(P) < 75:
            #LOGGER.info ("msg " + str(P))
            chat_msg= str(P)
            return True
        else:
            LOGGER.debug("Msg too long!")
            return False
        
    def callbackE3(self, P):
        global dest_address
        P=str(P)
        if len(P) <20:
            dest_address = P
            return True
        else:
            return False        

                               
root = tkinter.Tk()
root.title(Title)

def conn():
    global connected
    if not connected:
        t2 = threading.Thread(target=keepconnection)  
        t2.start()
        mlist.insert(0,"Connecting...")
        
def disconn():
    global connected
    connected=False
    cleanall()
    
    
def keepconnection():
    global connected, connection, channel, IP_sel
    # Start connection keep loop
    connected=True
    
    while connected:
        try:
            LOGGER.info("starting connection for consuming with "+IP_sel)
            credentials = pika.PlainCredentials(lay_user,lay_pass)
            parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials)
            connection = pika.BlockingConnection(parameters)
            channel=connection.channel()
            channel.queue_declare(queue=client_uid, auto_delete=True)
            # TODO Add dest as a secretUID, not visible as a queue?
            channel.queue_bind(exchange='L3_main_exchange', queue=client_uid, routing_key='all',
                               arguments={'x-match': 'any', 'service': 'chat'})

            channel.basic_qos(prefetch_count=1)           
            channel.basic_consume(queue=client_uid, on_message_callback=msgconsumer)
            tempstr="Successfully connected to AnuuTech Network!"
            LOGGER.info("Successfully connected to " + IP_sel)
            mlist.insert(0,tempstr)
            channel.start_consuming()

        # Recovery attempt in case of server-initiated connection closure,
        # including when the node is stopped cleanly
        except pika.exceptions.ConnectionClosedByBroker:
            print("Connection was closed by broker, retrying...")
            cleanall()
            continue
        # Recovery on channel errors (this is not recommended by PIKa implementation...)
        except pika.exceptions.AMQPChannelError as err:
            print("WARNING! Caught a channel error: {}, retrying...".format(err))
            cleanall()
            continue
            #break
        # Recovery on all other connection errors
        except pika.exceptions.AMQPConnectionError:
            print("Connection was closed, retrying...")
            cleanall()
            continue
        except KeyboardInterrupt:
            connected=False
            break
        except FileNotFoundError:
            e = sys.exc_info()[1]
            logmsg=( "<p>WARNING! Unidentified error, trying to reinit...: %s</p>" % e )
            LOGGER.info(logmsg)
            cleanall()
            continue
        


def msgconsumer(ch, method, properties, body):
    global name, contacts, msg_waiting, IP_sel
    hdrs=properties.headers
    LOGGER.info(hdrs)
    msg= json.loads(body.decode("utf-8"))
    LOGGER.info(msg)
    if hdrs.get('type')=='chat':
        LOGGER.info("AnuuChat Received " + msg['content'])
        if hdrs.get('sender_uid')==client_uid and hdrs.get('dest_all')=='clients':
            mlist.insert(0,'AnuuChat: Own general message received back: "' + str(msg['content']+'"'))
        elif hdrs.get('dest_uid')==client_uid:
            #Private message
            decrypted_msg = PRK.decrypt(base64.b64decode(msg['content'])).decode()
            xm="AnuuChat: Private encrypted message received from "+str(msg['username'])+ ': "' + str(decrypted_msg+'"')
            mlist.insert(0,str(xm))
        elif hdrs.get('sender_uid').strip() != client_uid.strip():
            #General message
            xm="AnuuChat: General message received from "+str(msg['username'])+ ': "' + str(msg['content']+'"')
            mlist.insert(0,str(xm))
            
    elif hdrs.get('type')=='CHAT-PUK':
        xm="AnuuChat: Encryption request from "+str(msg['username'])
        mlist.insert(0,str(xm))
        if hdrs.get('sender_uid') is not None and msg.get('pubk') is not None:
            contacts[hdrs.get('sender_uid')] = msg.get('pubk')
            LOGGER.debug('Updated contacts:' + str(contacts))
        if msg['content'] != 'Done' :
            # send a puk message
            msg=initmsg()
            msgtype=0
            msg['pubk']=public_key.exportKey('PEM').decode()
            msg['content']='Done'
            msg['username']=name
            headers=initheaders()
            headers['service']='chat'
            headers['dest_uid']=hdrs.get('sender_uid')
            headers['type']='CHAT-PUK'
            send_msg(headers, msg, msgtype)

    elif hdrs.get('type')=='HMES' and hdrs.get('dest_uid')==client_uid:
        # get all infos from DB
        db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
        db_client = pymongo.MongoClient(db_url)
        at_db = db_client["AnuuTechDB"]
        tx_col = at_db["transactions_pending"]
        db_query = { "uid": msg['uid'] }
        x=tx_col.find_one(db_query)
        if x is None:
            LOGGER.info("HMES " + str(msg['uid'])+" received back but no input in DB exists!")
        else:
            # get node signer public key
            node_col=at_db["nodes"]
            db_query = { "uid": x.get('node_uid') }
            y=node_col.find_one(db_query)
            if y is None:
                LOGGER.info("Node " + str(x.get('node_uid'))+" is not found in DB!")
            else:
                nodepubkey=RSA.importKey(y.get('pubkey'))
                #Verify fingerprint
                hh=SHA256.new(x.get('content').encode())
                hh.update(x.get('content_hash').encode())
                hh.update(str(x.get('timestamp')).encode())
                verifier = PKCS115_SigScheme(nodepubkey)
                try:
                    verifier.verify(hh, x.get('fingerprint'))
                    LOGGER.info("Msg " + str(msg['uid'])+" has been validly signed by "
                                +str(x.get('node_uid')))
                except:
                    LOGGER.info("Msg " + str(msg['uid'])+" has NOT BEEN VALIDLY signed by "
                                +str(x.get('node_uid')))

        LOGGER.info("HMES Received " + str(msg['content']))
        mlist.insert(0,"HMES: Message received back: "+str(msg['content']))
        

    ch.basic_ack(delivery_tag = method.delivery_tag)

    #Check if there are chat messages to send
    msg_handling=msg_waiting.copy()
    if len(msg_handling) >0:
        for item in msg_handling:
            if item[0]['dest_uid'] in contacts.keys():
                msg_waiting.remove(item)
                #Encrypt and send
                enc_key=PKCS1_OAEP.new(RSA.importKey(contacts[item[0]['dest_uid']].encode()))
                item[1]['content']= base64.b64encode(enc_key.encrypt(item[1]['content'].encode())).decode()
                send_msg(item[0],item[1],item[2])

def prepare_msg():
    global dest_address, name, msg_waiting, chat_msg, nodeslist
    msg=initmsg()
    msgtype=None
    try:
        # CHAT
        if int(varGr.get()) == 0:
            msgtype=0
            msg['username']=name
            if len(dest_address) == 0:
                #General message
                headers=initheaders()
                headers['service']='chat'
                headers['dest_all']='clients'
                headers['type']='chat'
                msg['content']=chat_msg
            else:
                #Private message
                headers=initheaders()
                headers['service']='chat'
                headers['dest_uid']=dest_address
                headers['type']='chat'
                if dest_address in contacts.keys():
                    enc_key=PKCS1_OAEP.new(RSA.importKey(contacts[dest_address].encode()))
                    msg['content']= base64.b64encode(enc_key.encrypt(chat_msg.encode())).decode()
                else:
                    msg['content']=chat_msg
                    temp=[]
                    temp.append(headers.copy())
                    temp.append(msg.copy())
                    temp.append(0)
                    msg_waiting.append(temp)
                    headers['type']='CHAT-PUK'
                    msg['pubk']=public_key.exportKey('PEM').decode()
                    msg['content']= 'PUK attached'

            LOGGER.info("msg prepared to be sent: chat:" + str(msg['content']))
        # HMES    
        elif int(varGr.get()) >= 1:
            msgtype=1
            # Hash message
            msg['content']= chat_msg
            msg['content_hash']=binascii.hexlify((SHA256.new(chat_msg.encode())).digest()).decode()
            # Select L3 node based on hash (sum of all characters)
            node_uid=list(nodeslist.keys())[(sum(msg['content_hash'].encode()))%len(nodeslist.keys())]
            headers={'dest': node_uid, 'type': 'HMES', 'sender': client_uid}
            LOGGER.info("msg prepared to be sent: "+str(headers))

    except:
        mlist.insert(0,"Impossible to prepare msg, error occured!")
        e = sys.exc_info()[0]
        LOGGER.info( "<p>Problem while preparing message sending " % str(e) )
        
    send_msg(headers, msg, msgtype)


def send_msg(headers, msg, msgtype):
    global connected, dest_address, name, IP_sel
    if not connected:
        mlist.insert(0,"Impossible to send msg, not connected!") 
        return
    # Ensure all outgoing messages have the node IP well set
    headers['sender_node_IP']=IP_sel
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()

    try:        
        channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                               properties=pika.BasicProperties(headers=headers),
                               body=(json.dumps(msg)))
        if msgtype == 0:
            if headers.get('type')=='chat':
                mlist.insert(0,"AnuuChat: Message sent.")
            else:
                mlist.insert(0,"AnuuChat: Encryption request sent.")
        elif msgtype == 1:
            mlist.insert(0,"HMES: Message sent.")
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
    "uid": randomstring(12),
    "username": "",
    "content": "some client data",
    "content_hash": "used for HMES",
    "pubk": "empty"
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
        'type': '',
        'hop': 0,
        'retry': 0
        }
    return basic_headers


def getL3nodesList():
    global nodeslist, defaultL3nodes
    #print(defaultL3nodes)
    timestamp_config=time.time()
    waiting=False
    while len(nodeslist)==0:
        try:
            random.shuffle(defaultL3nodes)
            IP_sel=defaultL3nodes[0]
            # get all infos from DB
            db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
            db_client = pymongo.MongoClient(db_url)
            at_db = db_client["AnuuTechDB"]
            nodes_col = at_db["nodes"]
            db_query = { "level": 'L3'}
            db_filter = {"uid":1, "IP_address":1, "_id":0, "services":1}
            templist=list(nodes_col.find(db_query, db_filter).max_time_ms(5000))
            nodeslist={n['uid']:n['IP_address'] for n in templist }# if (n['services']['net_storage'] == 1}
        except:
            time.sleep(1)
            e = sys.exc_info()[1]
            LOGGER.info( "<p>Error while trying to get nodes from DB, retrying...: %s</p>" % e )

def cleanall():
    # clean all connections
    global connection, connection2, channel
    LOGGER.info ("Cleaning all...")
    time.sleep(1)
    
    # Clean close of connections
    try:
        channel.stop_consuming()
    except:
        e = sys.exc_info()[1]
        LOGGER.info( "<p>Error when stopping consuming: %s</p>" % e )
    try:
        connection.close()
    except:
        e = sys.exc_info()[1]
        LOGGER.info( "<p>Closing consumer connection: %s</p>" % e )
    try:
        connection2.close()
    except:
        LOGGER.info("connection2 was not open")
    try:
        mlist.insert(0,"Disconnected!")
    except:
        LOGGER.info("Disconnected!")

#MAIN CALL
app=App(root)
root.mainloop()
#below happened at closure from CTRL-C
connected=False

