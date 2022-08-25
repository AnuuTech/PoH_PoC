import pika
import time
import tkinter
from tkinter import filedialog
from tkinter import ttk
import threading
import copy
import socket
import random
import string
import json
import sys
import os
import ssl
import base64
import traceback
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
import logging
import binascii
import pymongo
import urllib
sys.path.insert(0, './node_services')
import settings as S
import signal
signal.signal(signal.SIGINT, signal.default_int_handler) # to ensure Signal to be received

Title="AnuuTech Basic client V-"+S.SW_VERSION

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
    return None

lay_user='client_user'
lay_pass=ii_helper('node_data/accessClient.bin', '0')
db_pass=ii_helper('node_data/accessClient.bin', '1')
nodeslist={} # UIDs and IPs of all nodes with chat service
defaultL3nodes=[]
port=S.PORT
virtual_host=S.VHOST
IP_sel=[]
connected=False
threads=[]
msgtype=0
chat_msg="AnuuTech is coming!"
datapath=''
dest_address=''
client_uid_path='client_uid.file'
pubkey_path='atclient_pubkey.file'
privkey_path='atclient_privkey.file'
account_path='atclient_account.file'
contacts={}
chat_msg_waiting=[]
file_hash=''
tx_sent={} # msg UID + hash + verified
contract=None

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
    with open (privkey_path, 'wb') as prv_file:
        prv_file.write(private_key.exportKey('PEM','annu_seed-l'))
    with open (pubkey_path, 'wb') as pub_file:
        pub_file.write(public_key.exportKey('PEM'))
else:
    with open (privkey_path, 'rb') as prv_file:
        private_key=RSA.importKey(prv_file.read(),'annu_seed-l')
    with open (pubkey_path, 'rb') as pub_file:
        public_key=RSA.importKey(pub_file.read())
        LOGGER.debug('RSA keys sucessfully loaded.')
PRK=PKCS1_OAEP.new(private_key)

#get account 
if not os.path.isfile(account_path):
    # create account
    acct=Account.create("This is it!")
    acct_enc=Account.encrypt(acct.privateKey, ii_helper('node_data/accessClient.bin', '3'))
    LOGGER.info('No AKEY account found, new one has been created')
    with open (account_path, 'w') as a_file:
        a_file.write(json.dumps(acct_enc))
else:
    with open (account_path, 'r') as a_file:
        acct=Account.from_key(Account.decrypt(json.load(a_file), ii_helper('node_data/accessClient.bin', '3')))
        LOGGER.debug('AKEY account sucessfully loaded.')

#get default L3nodes
defaultL3nodes_hosts=['anuutechL3'+ii_helper('node_data/accessClient.bin', '2'), 
                      'anuutechL3'+ii_helper('node_data/accessClient.bin', '7')]
for dgh in defaultL3nodes_hosts:
    try:
        defaultL3nodes.append(socket.gethostbyname(dgh))
        LOGGER.info('Defaultnode obtained: '+ socket.gethostbyname(dgh) )
    except:
        LOGGER.info("WARNING! Impossible to get one of the default L3 node: " + dgh+ str(sys.exc_info()[0]))

if len(defaultL3nodes)==0:
    LOGGER.info("ERROR! Impossible to get any default L3 node... exiting.")
    exit()

#create RCP connection 
w3= Web3(Web3.HTTPProvider('http://anuutechL3b'+ii_helper('node_data/accessClient.bin', '2')+':'+ii_helper('node_data/accessClient.bin', '5')))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

class App:

    def __init__(self, wind):
        global rbutt, varGr, mlist, pathh, hashh, name, nodeslist, w_bal, contract, w_amount_send, w_addr_send
        global chat_msg, dest_address, IPs, varGr31, IP_sel, nodeslist_chat, nodeslist_poh, nodeslist_ds
        
        #global frame
        gframe = tkinter.Frame(wind, width=200)
        gframe.grid(column=0)
        gframe.configure(bg='grey10')
        
##        wframe.columnconfigure(index=0, weight=2)
##        wframe.columnconfigure(index=1, weight=2)
##        wframe.columnconfigure(index=2, weight=2)
##        wframe.rowconfigure(index=0, weight=2)
##        wframe.rowconfigure(index=1, weight=2)
##        wframe.rowconfigure(index=2, weight=2)

        
        wframe1 = tkinter.Frame(gframe, width=100)
        wframe1.grid(row=0, column=0, padx=10, pady=10)
        wframe1.configure(bg='grey10')

        #address
        w_addr_l = tkinter.Label(wframe1, text="AKEY own address:", fg='white', bg='grey10')
        w_addr_l.grid(row=0, column=0, padx=10, sticky="w")
        w_addr = tkinter.Text(wframe1, height=1, width=50)
        w_addr.insert(1.0, acct.address)
        w_addr.grid(row=1, column=0, padx=10)
        w_addr.configure(state='disabled')

        #balance
        w_bal_l = tkinter.Label(wframe1, text="Balance [AKEY]:", fg='white', bg='grey10')
        w_bal_l.grid(row=0, column=1, padx=15, sticky="w")
        w_bal = tkinter.Text(wframe1, height=1, width=15, padx=10)
        w_bal.insert(1.0, 'N/A')
        w_bal.grid(row=1, column=1, padx=15)
        w_bal.configure(state='disabled')
        w_bal_but =tkinter.Button(
                wframe1, text="Update Balance", command=get_balance, fg='white', bg='black'
                )
        w_bal_but.grid(row=2, column=1)

        #to send
        vcmdad = (wframe1.register(self.callbackaddr))
        w_addr_send = tkinter.Entry(wframe1, validate='key', validatecommand=(vcmdad, '%P'), width=50, bg='grey88') 
        w_addr_send.insert(0,"Enter recipient address")
        w_addr_send.grid(row=0, column=2, padx=10)
        vcmdam = (wframe1.register(self.callbackamount))
        w_amount_send = tkinter.Entry(wframe1, validate='key', validatecommand=(vcmdam, '%P'), width=15, bg='grey88') 
        w_amount_send.insert(0,"Enter amount")
        w_amount_send.grid(row=1, column=2, padx=10, sticky="w")
        w_send_but =tkinter.Button(
                wframe1, text="Send AKEY", command=send_to, fg='white', bg='black'
                )
        w_send_but.grid(row=2, column=2)


        # Separator
        #sep=tkinter.Separator(gframe, 
        sepframe= ttk.Separator(gframe, orient='horizontal')
        sepframe.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        # Rest of the frame
        frame = tkinter.Frame(gframe)
        frame.grid(row=2, column=0, padx=10, pady=10)
        
        getL3nodesList()
        IPs=list(nodeslist.values())
        #print(nodeslist_poh)
        frame.configure(bg='grey10')

        w0 = tkinter.Label(frame, text="UNIQUE ADDRESS:", fg='white', bg='grey10')
        w0.pack(side = tkinter.TOP, anchor = tkinter.W)

        w0b = tkinter.Text(frame, height=1, fg='white', bg='grey10')
        w0b.insert(1.0, client_uid)
        w0b.pack(side = tkinter.TOP, anchor = tkinter.W)
        w0b.configure(bg=frame.cget('bg'), relief='flat')
        w0b.configure(state='disabled')
        
        w2 = tkinter.Label(frame, text="Your name to display:", fg='white', bg='grey10')
        w2.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd = (frame.register(self.callbackE))
        self.w = tkinter.Entry(frame, validate='key', validatecommand=(vcmd, '%P'), width=15, bg='grey88') 
        self.w.insert(0,name)
        self.w.pack(side = tkinter.TOP, anchor = tkinter.W)
        
        w5 = tkinter.Label(frame, text="Information:", fg='white', bg='grey10')
        w5.pack(side = tkinter.TOP, anchor = tkinter.W)

        mlist = tkinter.Listbox(frame, height=10, width=150, bg='grey88')
        mlist.pack(side=tkinter.TOP, fill=tkinter.BOTH)

        wl3 = tkinter.Label(frame, text="Select message type:", fg='white', bg='grey10')
        wl3.pack(side = tkinter.TOP, anchor = tkinter.W)

        varGr = tkinter.StringVar()
        b = tkinter.Radiobutton(frame, variable=varGr, text="AnuuChat message", value=0,
                                        command=self.mtype, fg='white', bg='grey10',selectcolor='#222222')
##        b.pack(anchor=tkinter.W)
##        b = tkinter.Radiobutton(frame, variable=varGr, text="TEST ping", value=2,
##                                        command=self.mtype)
        b.pack(anchor=tkinter.W)
        b = tkinter.Radiobutton(frame, variable=varGr, text="PoH", value=3,
                                        command=self.mtype, fg='white', bg='grey10',selectcolor='#222222')

        b.pack(anchor=tkinter.W)
        b = tkinter.Radiobutton(frame, variable=varGr, text="Data Storage", value=4,
                                        command=self.mtype, fg='white', bg='grey10',selectcolor='#222222')
        
        b.pack(anchor=tkinter.W)

        varGr.set(0)

        pathh = tkinter.Entry(frame, bg='grey88')
        pathh.pack(side=tkinter.TOP, expand=True, padx=20)

        self.openfile = tkinter.Button(
            frame, text="Select File", command=openFile, fg='white', bg='black'
            )
        self.openfile.pack(side = tkinter.TOP)

        hashh = tkinter.Entry(frame, bg='grey88')
        hashh.pack(side=tkinter.TOP, expand=True, padx=20)

        w23 = tkinter.Label(frame, text="hash of file to retrieve (leave empty to store selected file)", fg='white', bg='grey10')
        w23.pack(side = tkinter.TOP)
        
        w31 = tkinter.Label(frame, text="Select node:", fg='white', bg='grey10')
        w31.pack(side = tkinter.TOP, anchor = tkinter.W)

        varGr31 = tkinter.StringVar()
        if len(sys.argv) == 2:
            if sys.argv[1] == 'local':
                IPs.insert(0,'192.168.1.71')
        rbutt={}
        for j in range(min(len(IPs),9)): # only up to 9 IPs shown
                rbutt[IPs[j]] = tkinter.Radiobutton(frame, variable=varGr31, text=IPs[j], value=IPs[j],
                                        command=self.ipsel, fg='white', bg='grey10',selectcolor='#222222')
                rbutt[IPs[j]].pack(anchor=tkinter.W)


        if len(IPs)==0:
            print("ERROR: no nodes found...")
            exit()
        # pre-select one IP
        self.mtype() # disable IPs radio button without the default chat service


        #IP_sel = IPs[0] #TODO select best ping?
   
        w8 = tkinter.Label(frame, text="AnuuChat message to send:", fg='white', bg='grey10')
        w8.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd2 = (frame.register(self.callbackE2))
        w9 = tkinter.Entry(frame, validate='all', validatecommand=(vcmd2, '%P'), width=75, bg='grey88') 
        w9.insert(0,chat_msg)
        w9.pack(side = tkinter.TOP, anchor = tkinter.W)

        w6 = tkinter.Label(frame, text="AnuuChat recipient's address (leave blank for all):", fg='white', bg='grey10')
        w6.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd3 = (frame.register(self.callbackE3))
        w7 = tkinter.Entry(frame, validate='all', validatecommand=(vcmd3, '%P'), width=15, bg='grey88') 
        w7.insert(0,dest_address)
        w7.pack(side = tkinter.TOP, anchor = tkinter.W)
        
        self.button = tkinter.Button(
                frame, text="QUIT", command=self.quitting, fg='white', bg='black'
                )
        self.button.pack(side = tkinter.RIGHT)
              
        self.conn = tkinter.Button(
                frame, text="Connect", command=conn, fg='white', bg='black'
                )
        self.conn.pack(side = tkinter.LEFT)

        self.deconn = tkinter.Button(
                frame, text="Disconnect", command=disconn, fg='white', bg='black'
                )
        self.deconn.pack(side = tkinter.LEFT)

        self.send = tkinter.Button(
                frame, text="Send Msg", command=prepare_msg, fg='white', bg='black'
                )
        self.send.pack(side = tkinter.LEFT)

        tempstr="Current list of "+str(len(nodeslist))+" Layer-3 nodes of AnuuTech Network."
        mlist.insert(0,tempstr)
        contract=w3.eth.contract(address=ii_helper('node_data/accessClient.bin', '6'),abi=S.ABI)
        get_balance()

    def callbackaddr(self, P):
        return True

    def callbackamount(self, P):
        try:
            float(P)
            return True
        except:
            return False

    def quitting(self):
        global connected
        connected=False
        time.sleep(1.1)
        cleanall()
        root.destroy()

    def mtype(self):
        global msgtype, nodeslist, nodeslist_chat, nodeslist_poh, nodeslist_ds
        msgtype = int(varGr.get())
        if msgtype==0:
            ts='CHAT'
            for ip in nodeslist.values():
                if ip not in nodeslist_chat.values():
                    rbutt[ip]['state'] = 'disabled'
                else:
                    rbutt[ip]['state'] = 'normal'
            varGr31.set(list(nodeslist_chat.values())[0]) # select first IP with service activated
        elif msgtype==3:
            ts='PoH'
            for ip in nodeslist.values():
                if ip not in nodeslist_poh.values():
                    rbutt[ip]['state'] = 'disabled'
                else:
                    rbutt[ip]['state'] = 'normal'
            varGr31.set(list(nodeslist_poh.values())[0]) # select first IP with service activated
        elif msgtype==4:
            ts='Data Storage'
            for ip in nodeslist.values():
                if ip not in nodeslist_ds.values():
                    rbutt[ip]['state'] = 'disabled'
                else:
                    rbutt[ip]['state'] = 'normal'
            varGr31.set(list(nodeslist_ds.values())[0]) # select first IP with service activated
        selection = "You selected the message type: " + ts
        LOGGER.info(selection)
        self.ipsel() # to update IP selected
        
    def ipsel(self):
        global IP_sel, IPs, varGr31
        IP_sel=varGr31.get()
        selection = "You selected the ip " + str(IP_sel)
        disconn()
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
root.configure(bg='grey10')


def send_to():
    global w_amount_send, w_addr_send
    if float(w_amount_send.get())==0:
        mlist.insert(0,"Amount to send is zero...")
        return
    elif not w3.isAddress(w_addr_send.get()):
        mlist.insert(0,"Address to send to is invalid!")
    else:
        #get nonce
        nonce = w3.eth.getTransactionCount(acct.address)
        #build tx dictionary
        tx = {
            'nonce': nonce,
            'chainId': w3.toHex(int(ii_helper('node_data/accessClient.bin', '4'))),
            'to': w_addr_send.get(),
            'value': w3.toWei(float(w_amount_send.get()),'ether'),
            'gas': 21000,
            'gasPrice': w3.toWei('1000', 'wei')
            }
        #sign the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, acct.privateKey)
        #send transaction
        tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction)
        mlist.insert(0,"Hash of tx is: "+str(w3.toHex(tx_hash)))
    return

def get_balance():
    global acct, w_bal
    bal=w3.eth.getBalance(acct.address)
    LOGGER.info("Balance of " + str(acct.address) + " = " +str(bal) + " AKEY")
    w_bal.configure(state='normal')
    w_bal.delete(1.0, 'end')
    w_bal.insert(1.0, w3.fromWei(bal,'ether'))
    w_bal.configure(state='disabled')
    return
    
def conn():
    global connected
    if not connected:
        t2 = threading.Thread(target=keepconnection)  
        t2.start()

        t3= threading.Thread(target=readDB)
        t3.start()
        mlist.insert(0,"Connecting...")

def disconn():
    global connected
    connected=False
    cleanall()

def openFile():
    tf = filedialog.askopenfilename(
        initialdir=os.getcwd(), 
        title="Select file" 
        #filetypes=(("Text Files", "*.txt"),)
        )
    pathh.delete(0,'end')
    pathh.insert(0, tf)

def readDB():
    global connected, tx_sent
    db_url='mongodb://explorer:' + urllib.parse.quote(db_pass) +'@'+defaultL3nodes[0]+':28991/?authMechanism=DEFAULT&authSource=admin'
    with pymongo.MongoClient(db_url) as db_client:
        at_db = db_client['AnuuTech_DB']
        while connected:
            if (int(varGr.get()) == 3 and len(tx_sent)>0):
                LOGGER.debug("DB checking "+str(len(tx_sent)))
                col = at_db['blocks']
                resl=col.find_one(sort=[("height", -1)])
                tx_s=tx_sent.copy()
                if 'transactions' in resl:
                    for txid in tx_s.keys():
                        t=[el for el in resl['transactions'] if el['uid']==txid]
                        if len(t)>0:
                            mlist.insert(0,"Msg "+str(txid)+ " is now fully validated and added to the masterhash blockchain!")
                            LOGGER.info("Msg "+str(txid)+ " is now fully validated and added to the masterhash blockchain!")
                            tx_sent.pop(txid)
            time.sleep(2)

    
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
                               arguments={'x-match': 'any', 'dest_uid': client_uid,'dest_all': 'clients'})

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
    global name, contacts, chat_msg_waiting, IP_sel, nodeslist_poh, defaultL3nodes
    global file_hash, hashh
    hdrs=properties.headers
    LOGGER.info(hdrs)
    msg= json.loads(body.decode('utf-8'))
    LOGGER.info(msg)
    if msg.get('type')=='CHAT':
        #LOGGER.info("AnuuChat Received " + msg['uid'])
        if hdrs.get('sender_uid')==client_uid and hdrs.get('dest_all')=='clients':
            mlist.insert(0,'AnuuChat: Own general message received back: "' + str(msg['content'].get('chat_msg'))+'"')
        elif hdrs.get('dest_uid')==client_uid:
            #Private message
            decrypted_msg = json.loads(PRK.decrypt(base64.b64decode(msg['content'].encode())).decode())
            xm="AnuuChat: Private encrypted message received from "+str(decrypted_msg.get('username'))+ ': "' + str(decrypted_msg.get('chat_msg'))+'"'
            mlist.insert(0,str(xm))
        elif hdrs.get('sender_uid').strip() != client_uid.strip() and int(varGr.get()) == 0: # to avoid receiving general messages while using other services
            #General message
            xm="AnuuChat: General message received from "+str(msg['content'].get('username'))+ ': "' + str(msg['content'].get('chat_msg'))+'"'
            mlist.insert(0,str(xm))
            
    elif msg.get('type')=='CHAT-PUK' and hdrs.get('dest_uid')==client_uid:
        xm="AnuuChat: Encryption request from "+str(msg['content'].get('username'))
        mlist.insert(0,str(xm))
        if hdrs.get('sender_uid') is not None and msg['content'].get('pubk') is not None:
            contacts[hdrs.get('sender_uid')] = msg['content'].get('pubk')
            LOGGER.debug('Updated contacts:' + str(contacts))
        if hdrs.get('dest_uid')==client_uid and msg['content'].get('chat_msg') != 'Done' :
            # send a puk message
            msg=initmsg()
            msgtype=0
            msg['content']['pubk']=public_key.exportKey('PEM').decode()
            msg['content']['chat_msg']='Done'
            msg['content']['username']=name
            msg['type']='CHAT-PUK'
            headers=initheaders()
            headers['service']='chat'
            headers['dest_uid']=hdrs.get('sender_uid')
            send_msg(headers, msg, msgtype)

    elif (msg.get('type')=='POH_L3_R1_DONE' and hdrs.get('dest_uid')==client_uid):
        # Check that it is one of our own msg
        own_msg= False
        if msg['uid'] in tx_sent.keys():
            if tx_sent[msg['uid']]['hash'] == msg['content']['tx_hash']:
                own_msg=True
                LOGGER.info("PoH R1 Received back: " + str(msg['uid']))
                mlist.insert(0,"PoH R1 received back: "+str(msg['uid']))
        if not own_msg:
            LOGGER.info("PoH R1 Received IS NOT OUR OWN MSG!")
            mlist.insert(0,"PoH R1 Received IS NOT OUR OWN MSG!")
##        else: 
##            # OPTIONAL LOCAL CHECK Deactivated for now, "transactions" collections do not exist anymore
##            # get all infos from DB
##            random.shuffle(defaultL3nodes)
##            IP_DB=defaultL3nodes[0] # TODO get all net storage available nodes
##            db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+IP_DB+':27017/?authMechanism=DEFAULT&authSource=admin'
##            db_client = pymongo.MongoClient(db_url)
##            at_db = db_client['AnuuTechDB']
##            tx_col = at_db['transactions']
##            db_query = { 'uid': msg['uid'] }
##            x=tx_col.find_one(db_query)
##            if x is None:
##                LOGGER.info("PoH R1 " + str(msg['uid'])+" received back but no input in DB exists!")
##            else:
##                # get node signer public key
##                node_col=at_db['nodes']
##                db_query = { 'uid': x.get('signer_nodeL3') }
##                y=node_col.find_one(db_query)
##                if y is None:
##                    LOGGER.info("Node " + str(x.get('signer_nodeL3'))+" is not found in DB!")
##                else:
##                    nodepubkey=RSA.importKey(y.get('pubkey').encode())
##                    #Verify fingerprint
##                    hh=SHA256.new(x.get('tx_hash').encode())
##                    hh.update(str(x.get('timestamp')).encode())
##                    verifier = PKCS115_SigScheme(nodepubkey)
##                    try:
##                        verifier.verify(hh, binascii.unhexlify(x.get('fingerprintL3').encode()))
##                        LOGGER.info("Msg " + str(msg['uid'])+" has been validly signed by "
##                                    +str(x.get('signer_nodeL3')))
##                        mlist.insert(0,"Msg " + str(msg['uid'])+" has been validly signed by "
##                                    +str(x.get('signer_nodeL3')))
##                    except:
##                        LOGGER.info("Msg " + str(msg['uid'])+" has NOT BEEN VALIDLY signed by "
##                                    +str(x.get('signer_nodeL3')))
##                        mlist.insert(0,"Msg " + str(msg['uid'])+" has NOT BEEN VALIDLY signed by "
##                                    +str(x.get('signer_nodeL3')))
            #send to a second node
            # Select L3 node based on hash (sum of all characters), restricted to nodes with poh service
##            if len(nodeslist_poh) != 0:
##                node_uid=list(nodeslist_poh.keys())[(sum(msg['content']['fingerprintL3'].encode()))%len(nodeslist_poh.keys())]
##                headers=initheaders()
##                headers['service']='poh'
##                headers['dest_uid']=node_uid
##                msg['type']='POH_L3_R2'
##                msgtype=3
##                send_msg(headers, msg, msgtype)
##                LOGGER.info("msg POH R2 prepared to be sent: "+str(headers))
##            else:
##                LOGGER.info("Cannot send PoH R2 msg, no node with service active found!")
##                mlist.insert(0,"Cannot send PoH R2 msg, no node with service active found!")
        
    elif (msg.get('type')=='DATA_SAVED' and hdrs.get('dest_uid')==client_uid):
        if hashh.get() == '':
            file_hash=msg['content']
            hashh.delete(0,'end')
            hashh.insert(0, msg['content'])
            mlist.insert(0,"Data storage: confirmation of file successfully stored on: "+hdrs['sender_uid'])
        else:
            if file_hash==msg['content']:
                mlist.insert(0,"Data storage: confirmation of file successfully stored on: "+hdrs['sender_uid'])
            else:
                file_hash=msg['content']
                hashh.delete(0,'end')
                hashh.insert(0, msg['content'])
                mlist.insert(0,"Data storage: A new file has been sucessfully stored on: "+hdrs['sender_uid'])

    elif (msg.get('type')=='DATA_LOADED' and hdrs.get('dest_uid')==client_uid):
        fileloaded=msg['content']['file']
        mlist.insert(0,"Data storage: file retrieved from: "+hdrs['sender_uid'])
        with open ("RETRIEVED_"+msg['content']['filename'], 'wb') as h_file:
            h_file.write(base64.b64decode(fileloaded))

    elif (msg.get('type')=='DATA_NOT_FOUND' and hdrs.get('dest_uid')==client_uid):
        msgh=msg['content']
        mlist.insert(0, msgh)
    
    elif (msg.get('type')=='FEE_ERROR' and hdrs.get('dest_uid')==client_uid):
        msgh=msg['content']
        mlist.insert(0, msgh)
        
    ch.basic_ack(delivery_tag = method.delivery_tag)

    #Check if there are chat messages to send
    msg_handling=chat_msg_waiting.copy()
    if len(msg_handling) >0:
        for item in msg_handling:
            if item[0]['dest_uid'] in contacts.keys():
                chat_msg_waiting.remove(item)
                #Encrypt
                enc_key=PKCS1_OAEP.new(RSA.importKey(contacts[item[0]['dest_uid']].encode()))
                item[1]['content']= base64.b64encode(enc_key.encrypt(json.dumps(item[1]['content']).encode())).decode()
                #Pay fee and send
                fee=S.FEE_CHAT
                fee_addr=ii_helper('node_data/accessClient.bin', '9')
                txfee_hash=send_fee(msghash(item[1]), fee_addr, fee)
                item[0]['fee_tx_hash']=txfee_hash
                send_msg(item[0],item[1],item[2])

def prepare_msg():
    global dest_address, name, chat_msg_waiting, chat_msg, nodeslist, nodeslist_chat
    global nodeslist_poh, nodeslist_ds, pathh, hashh
    msg=initmsg()
    msgtype=None
    fee=0
    fee_addr=''
    try:
        # CHAT
        if int(varGr.get()) == 0:
            msgtype=0
            msgcontent={}
            msgcontent['username']=name
            msgcontent['chat_msg']=chat_msg
            msg['type']='CHAT'
            msg['content']=msgcontent
            if len(dest_address) == 0:
                #General message
                headers=initheaders()
                headers['service']='chat'
                headers['dest_all']='clients'
                fee=S.FEE_CHAT
                fee_addr=ii_helper('node_data/accessClient.bin', '9')
            else:
                #Private message
                headers=initheaders()
                headers['service']='chat'
                headers['dest_uid']=dest_address
                if dest_address in contacts.keys():
                    fee=S.FEE_CHAT
                    fee_addr=ii_helper('node_data/accessClient.bin', '9')
                    enc_key=PKCS1_OAEP.new(RSA.importKey(contacts[dest_address].encode()))
                    msg['content']= base64.b64encode(enc_key.encrypt(json.dumps(msgcontent).encode())).decode()
                else:
                    temp=[]
                    temp.append(headers.copy())
                    temp.append(copy.deepcopy(msg)) # deepcopy is needed since another dict is inside...!!!
                    temp.append(0)
                    chat_msg_waiting.append(temp)
                    msg['type']='CHAT-PUK'
                    msg['content']['pubk']=public_key.exportKey('PEM').decode()
                    msg['content']['chat_msg']= 'PUK attached'

            LOGGER.info("msg prepared to be sent: chat:" + str(msg['content']))
        # PoH_L3_R1    
        elif int(varGr.get()) == 3:
            msgtype=3
            # Hash message
            msg['content']={}
            msg['content']['tx_hash']=binascii.hexlify((SHA256.new(chat_msg.encode())).digest()).decode()
            fee=S.FEE_POH
            fee_addr=ii_helper('node_data/accessClient.bin', '8')
            # Select L3 node based on hash (sum of all characters), restricted to nodes with poh service
            if len(nodeslist_poh) != 0:
                node_uid=list(nodeslist_poh.keys())[(sum(msg['content']['tx_hash'].encode()))%len(nodeslist_poh.keys())]
                headers=initheaders()
                headers['service']='poh'
                headers['dest_uid']=node_uid
                msg['type']='POH_L3_R1'
                LOGGER.info("msg prepared to be sent: "+str(headers))
                tx_sent[msg['uid']]={'hash': msg['content']['tx_hash'], 'verified':0}
            else:
                LOGGER.info("Cannot send PoH msg, no node with service active found!")
                mlist.insert(0,"Cannot send PoH msg, no node with service active found!")
        # DATA STORAGE   
        elif int(varGr.get()) == 4:
            msgtype=4
            headers=initheaders()
            headers['service']='net_maintenance'
            headers['service_forward']='data_storage'
            if len(pathh.get())<2 and len(hashh.get())<10:
                mlist.insert(0,"No file selected!")
                return
            elif len(hashh.get())<10: #sending file
                with open (pathh.get(), 'rb') as tfile:
                    tempfile=tfile.read()
                msg['type']='SAVE_DATA'
                msg['content']['file']= base64.b64encode(tempfile).decode()
                msg['content']['filename']=os.path.split(pathh.get())[1]
                fee=S.FEE_DATASTORAGE
                fee_addr=ii_helper('node_data/accessClient.bin', '10')
                LOGGER.info("File saving prepared to be sent: "+str(headers))
            else: #getting file back
                msg['type']='GET_DATA'
                msg['content']= hashh.get()
                LOGGER.info("File loading prepared to be sent: "+str(headers))

        if not fee == 0:
            #check if balance is enough
            bal=w3.fromWei(w3.eth.getBalance(acct.address),'ether')
            if (fee > float(bal) - 0.0001):
                ballow=("Not enough balance : "+str(bal) + " (fee is "+str(fee)+")")
                LOGGER.warning(ballow)
                mlist.insert(0,ballow)
                return
            txfee_hash=send_fee(msghash(msg), fee_addr, fee)
            headers['fee_tx_hash']=txfee_hash
            
        send_msg(headers, msg, msgtype)
    except:
        mlist.insert(0,"Impossible to prepare msg, error occured!")
        #e = sys.exc_info()
        LOGGER.info( "<p>Problem while preparing message sending " + str(traceback.format_exc()) )

def send_fee(msgh, fee_addr, fee):
    txn_hash=''
    print(msgh + fee_addr)
    try:
        #get nonce
        nonce = w3.eth.getTransactionCount(acct.address)
        #prepare tx
        txn = contract.functions.callTransfer(w3.toChecksumAddress(fee_addr), msgh,'').buildTransaction({
          'chainId': int(ii_helper('node_data/accessClient.bin', '4')),
          'gas': 500000,
          'value': w3.toWei(fee,'ether'),
          'gasPrice': w3.toWei('1000', 'wei'),
          'nonce': nonce
        })
        LOGGER.info("Fee tx prepared: "+str(txn))
        signed_txn = w3.eth.account.sign_transaction(txn, acct.privateKey)
        #send transaction
        txn_hash=w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        mlist.insert(0,"Fee tx sent: "+str(w3.toHex(txn_hash)))
        rec=w3.eth.waitForTransactionReceipt(txn_hash,timeout=5)
        LOGGER.info("Fee tx confirmed: "+str(rec))
        mlist.insert(0,"Fee tx confirmed in block: "+str(rec['blockNumber']))
    except:
        e = sys.exc_info()
        LOGGER.info("<p>Problem while sending fee tx: " + str(traceback.format_exc()) )
    return txn_hash

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
            if msg.get('type')=='CHAT':
                mlist.insert(0,"AnuuChat: Message sent.")
            else:
                mlist.insert(0,"AnuuChat: Encryption request sent.")
        elif msgtype == 3:
            mlist.insert(0,"PoH: Message sent.")
        elif msgtype == 4:
            mlist.insert(0,"Data storage: Message sent.")
        connection2.close()
    except:
        mlist.insert(0,"Impossible to send msg, error occured!") 
        e = sys.exc_info()[1]
        LOGGER.info( "<p>Problem while sending, trying to reinit connections...: %s</p>" % e )
        try:
            connection2.close() 
        except:
            LOGGER.info('Problem while sending and impossible to close connection2')

def msghash(msg):
    hh=SHA256.new(msg['uid'].encode())
    hh.update(str(msg['content']).encode())
    hh.update(msg['type'].encode())
    hh.update(str(msg['timestamp']).encode())
    return binascii.hexlify(hh.digest()).decode()

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


def getL3nodesList():
    global nodeslist, nodeslist_chat, nodeslist_poh, nodeslist_ds, defaultL3nodes
    #print(defaultL3nodes)
    timestamp_config=time.time()
    waiting=False
    while len(nodeslist)==0:
        try:
            random.shuffle(defaultL3nodes)
            IP_sel=defaultL3nodes[0]
            # get all infos from DB
            db_url='mongodb://explorer:' + urllib.parse.quote(db_pass) +'@'+IP_sel+':28991/?authMechanism=DEFAULT&authSource=admin'
            db_client = pymongo.MongoClient(db_url)
            at_db = db_client['AnuuTech_DB']
            nodes_col = at_db['nodes']
            db_query = { 'level': 'L3'}
            db_filter = {'uid':1, 'IP_address':1, '_id':0, 'services':1}
            templist=list(nodes_col.find(db_query, db_filter))
            nodeslist={n['uid']:n['IP_address'] for n in templist }# if (n['services']['net_storage'] == 1}
            nodeslist_chat={n['uid']:n['IP_address'] for n in templist if n['services']['chat'] == 1}
            nodeslist_poh={n['uid']:n['IP_address'] for n in templist if n['services']['poh'] == 1}
            nodeslist_ds={n['uid']:n['IP_address'] for n in templist if n['services']['net_maintenance'] == 1}
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

