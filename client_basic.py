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
import logging
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
lay_pass=ii_helper('access.bin', '1')
IPs=[] # IPs of all L3 nodes
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
        client_uid=uid_file.read()
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
defaultL3nodes_hosts=['at-clusterL3'+ii_helper('access.bin', '8'),
                      'at-clusterL3b'+ii_helper('access.bin', '8')]
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
        global varGr, mlist, name, IPs, chat_msg, dest_address
        frame = tkinter.Frame(wind)
        getL3nodesList()

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

        tempstr="Successfully got list of "+str(len(IPs))+" L3 nodes of AnuuTech Network!"
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
        global IP_sel
        IP_sel = IPs[int(varGr.get())]
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
    global connected, connection, channel, IPs, IP_sel
    # Start connection keep loop
    connected=True
    
    while connected:
        #select a random L3 node
        IP_sel=random.choice(IPs)
        try:
            LOGGER.info("starting connection for consuming with "+IP_sel)
            credentials = pika.PlainCredentials(lay_user,lay_pass)
            parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials)
            connection = pika.BlockingConnection(parameters)
            channel=connection.channel()
            channel.queue_declare(queue=client_uid, auto_delete=True)
            # TODO Add dest as a secretUID, not visible as a queue?
            channel.queue_bind(exchange='L3_main_exchange', queue=client_uid, routing_key='all',
                               arguments={'x-match': 'any', 'dest': client_uid, 'dest_all': 'clients'})

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
        except:
            e = sys.exc_info()[1]
            logmsg=( "<p>WARNING! Unidentified error, trying to reinit...: %s</p>" % e )
            LOGGER.info(logmsg)
            cleanall()
            continue
        


def msgconsumer(ch, method, properties, body):
    global name, contacts, msg_waiting
    hdrs=properties.headers
    LOGGER.info(hdrs)
    msg= json.loads(body.decode("utf-8"))
    LOGGER.info(msg)
    if hdrs.get('type')=='CHAT':
        LOGGER.info("AnuuChat Received " + msg['content'])
        if hdrs.get('sender')==client_uid and hdrs.get('dest_all')=='clients':
            mlist.insert(0,'AnuuChat: Own general message received back: "' + str(msg['content']+'"'))
        elif hdrs.get('dest')==client_uid:
            #Private message
            decrypted_msg = PRK.decrypt(base64.b64decode(msg['content'])).decode()
            xm="AnuuChat: Private encrypted message received from "+str(msg['sender_name'])+ ': "' + str(decrypted_msg+'"')
            mlist.insert(0,str(xm))
        else:
            #General message
            xm="AnuuChat: General message received from "+str(msg['sender_name'])+ ': "' + str(msg['content']+'"')
            mlist.insert(0,str(xm))
            
    elif hdrs.get('type')=='CHAT-PUK':
        xm="AnuuChat: Encryption request from "+str(msg['sender_name'])
        mlist.insert(0,str(xm))
        if hdrs.get('sender') is not None and msg.get('pubk') is not None:
            contacts[hdrs.get('sender')] = msg.get('pubk')
            LOGGER.debug('Updated contacts:' + str(contacts))
        if msg['content'] != 'Done' :
            # send a puk message
            msg=initmsg()
            msgtype=0
            msg['pubk']=public_key.exportKey('PEM').decode()
            msg['content']='Done'
            msg['sender_name']=name
            headers={'dest': hdrs.get('sender'), 'type': 'CHAT-PUK', 'sender': client_uid}
            send_msg(headers, msg, msgtype)

    elif hdrs.get('type')=='HMES' and hdrs.get('dest')==client_uid:
        LOGGER.info("HMES Received " + str(msg['content']))
        mlist.insert(0,"HMES: Message received back: "+str(msg['content']))

    ch.basic_ack(delivery_tag = method.delivery_tag)

    #Check if there are chat messages to send
    msg_handling=msg_waiting.copy()
    if len(msg_handling) >0:
        for item in msg_handling:
            if item[0]['dest'] in contacts.keys():
                msg_waiting.remove(item)
                #Encrypt and send
                enc_key=PKCS1_OAEP.new(RSA.importKey(contacts[item[0]['dest']].encode()))
                item[1]['content']= base64.b64encode(enc_key.encrypt(item[1]['content'].encode())).decode()
                send_msg(item[0],item[1],item[2])

def prepare_msg():
    global dest_address, name, msg_waiting, chat_msg
    msg=initmsg()
    msgtype=None
    try:
        # CHAT
        if int(varGr.get()) == 0:
            msgtype=0
            msg['sender_name']=name
            if len(dest_address) == 0:
                #General message
                headers={'dest_all': 'clients', 'type': 'CHAT', 'sender': client_uid}
                msg['content']=chat_msg
            else:
                #Private message
                headers={'dest': dest_address, 'type': 'CHAT', 'sender': client_uid}
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
                    headers={'dest': dest_address, 'type': 'CHAT-PUK', 'sender': client_uid}
                    msg['pubk']=public_key.exportKey('PEM').decode()
                    msg['content']= 'PUK attached'

            LOGGER.info("msg prepared to be sent: chat:" + str(msg['content']))
        # HMES    
        elif int(varGr.get()) >= 1:
            msgtype=1
            headers={'dest': 'main', 'type': 'HMES', 'sender': client_uid} #TODO should send here to only one node
            msg['content']= (str(client_uid)+' HMES hash')
            LOGGER.info("msg prepared to be sent: HMES "+client_uid)

    except:
        mlist.insert(0,"Impossible to prepare msg, error occured!")
        e = sys.exc_info()[1]
        LOGGER.info( "<p>Problem while preparing message sending " % e )
        
    send_msg(headers, msg, msgtype)


def send_msg(headers, msg, msgtype):
    global connected, dest_address, name
    if not connected:
        mlist.insert(0,"Impossible to send msg, not connected!") 
        return
    
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()

    try:        
        channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                               properties=pika.BasicProperties(headers=headers),
                               body=(json.dumps(msg)))
        if msgtype == 0:
            if headers.get('type')=='CHAT':
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
    "uid": '0',
    "initial_sender": client_uid,
    "final_receiver": "",
    "content": "some client data",
    "pubk": "empty",
    "metadata": "",
    "client_hash": "",
    "trusted_timestamp": "",
    "data_fingerprint": "",
    }
    return msg_empty
            
def getL3nodesList():
    global connection, connection2, channel, channel2, IPs
    timestamp_config=time.time()
    waiting=False
    altIPs=[]
    while len(IPs)==0:
        if (time.time()-timestamp_config > 15):
            LOGGER.info( "ERROR: impossible to get L3nodes list, timeout")
            break
        if waiting == False:
            try:
                # Random selection of a L3nodes node
                random.shuffle(defaultL3nodes)
                # Start connection
                credentials = pika.PlainCredentials(lay_user,lay_pass)
                parameters=pika.ConnectionParameters(defaultL3nodes[0], port,virtual_host, credentials)
                connection = pika.BlockingConnection(parameters)
                connection2 = pika.BlockingConnection(parameters)
                channel=connection.channel()
                channel.queue_declare(queue=client_uid, auto_delete=True)
                channel.queue_bind(exchange='L3_main_exchange', queue=client_uid, routing_key='all',
                               arguments={'x-match': 'any', 'dest': client_uid})
                t2 = threading.Thread(target=configconsumer)
                t2.start()
                threads.append(t2)

                channel2=connection2.channel()
                msg=initmsg()
                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(
                                           headers={'dest': 'main', 'type': 'getL3nodeslist', 'sender': client_uid}),
                                       body=(json.dumps(msg)))
                LOGGER.info("msg sent: get entrypoints list " + client_uid)
                LOGGER.info("L3nodes list request sent to " + defaultL3nodes[0])
                waiting = True
                time.sleep(2)
                # No error so far... we can add the current connected node in the list
                altIPs.append(defaultL3nodes[0])
            except:
                waiting=False
                e = sys.exc_info()[0]
                LOGGER.info( "Problem requesting Entry-points list, retrying: %s" % e )
                LOGGER.info(e)
                cleanall()
                
    for anode in altIPs:
        if anode not in IPs:
            IPs.append(anode)
    LOGGER.info( "List of Entry-points obtained: %s" %IPs )
    cleanall()

def configmsgconsumer(ch, method, properties, body):
    global IPs
    hdrs=properties.headers
    LOGGER.info(hdrs)
    if (hdrs.get('type')=='getL3nodeslist' and hdrs.get('sender') == client_uid):
        msg=json.loads(body.decode("utf-8"))
        temp=msg['content'].split(',')
        IPs=temp[1:len(temp)]
    ch.basic_ack(delivery_tag = method.delivery_tag)

def configconsumer():
    global channel
    channel.basic_consume(queue=client_uid, on_message_callback=configmsgconsumer)
    try:
        channel.start_consuming()
    except:
        e = sys.exc_info()[0]
        LOGGER.info( "<p>Problem while configconsuming: %s</p>" % e )
     
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

