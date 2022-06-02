import pika
import time
import tkinter
import threading
import socket
import random
import string
import json
import sys
import pymongo
import urllib
import signal
signal.signal(signal.SIGINT, signal.default_int_handler) # to ensure Signal to be received

lay_user='client_user'
IPs=[] # IPs of all L3 nodes
defaultL3nodes=[]
port=5672
virtual_host='anuutech'
IP_sel=[]
sending=False
consuming=False
threads=[]
msgs_tosend=[]

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
db_pass=ii_helper('node_data/access.bin', '12')

#get hostname
hostname=socket.gethostname()

#check local/debug mode
if len(sys.argv) == 2:
    if sys.argv[1] == 'local':
        defaultL3nodes.append('192.168.1.71')

#get default L3nodes
defaultL3nodes_hosts=['at-clusterL3'+ii_helper('node_data/access.bin', '8'),
                      'at-clusterL3b'+ii_helper('node_data/access.bin', '8')]
for dgh in defaultL3nodes_hosts:
    try:
        defaultL3nodes.append(socket.gethostbyname(dgh))
        print('Defaultnode obtained: '+ socket.gethostbyname(dgh) )
    except:
        print("WARNING! Impossible to get one of the default node: " + dgh, sys.exc_info()[0])

if len(defaultL3nodes)==0:
    print("ERROR! Impossible to get any default node... exiting.")
    exit()

#timestamps
timest_in=time.time()
timest_out=time.time()
timest_i=1
timest_i2=1
i=0
i2=0
cur_timeout=1000
old_speed =1
old_speed2 =1

class App:

    def __init__(self, wind):
        global varGr, mlist, label_IR, label_OR, IPs, IP_sel
        frame = tkinter.Frame(wind)
        IPs=defaultL3nodes
        
        w2 = tkinter.Label(frame, text="Outgoing rate goal [/s] (0 for max):")
        w2.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd = (frame.register(self.callbackE))
        w = tkinter.Entry(frame, validate='all', validatecommand=(vcmd, '%P')) 
        w.insert(0,'1')
        w.pack(side = tkinter.TOP, anchor = tkinter.W)
 
        w7 = tkinter.Label(frame, text="Outgoing rate [/s]:")
        w7.pack(side = tkinter.TOP, anchor = tkinter.W)       

        label_OR = tkinter.StringVar()
        w6 = tkinter.Label(frame, textvariable=label_OR)
        w6.pack(side = tkinter.TOP, anchor = tkinter.W)
        
        w5 = tkinter.Label(frame, text="Last incoming rate [/s]:")
        w5.pack(side = tkinter.TOP, anchor = tkinter.W)
        
        label_IR = tkinter.StringVar()
        w4 = tkinter.Label(frame, textvariable=label_IR)
        w4.pack(side = tkinter.TOP, anchor = tkinter.W)

        mlist = tkinter.Listbox(frame, height=5, width=50)
        mlist.pack(side=tkinter.TOP, fill=tkinter.BOTH)

        w3 = tkinter.Label(frame, text="Select cluster node:")
        w3.pack(side = tkinter.TOP, anchor = tkinter.W)

        varGr = tkinter.StringVar()
        if len(sys.argv) == 2:
            if sys.argv[1] == 'local':
                IPs.insert(0,'192.168.1.71')
        for j in range(min(len(IPs),9)): # only up to 9 IPs shown
                b = tkinter.Radiobutton(frame, variable=varGr, text=IPs[j], value=j,
                                        command=self.ipsel)
                b.pack(anchor=tkinter.W)
        varGr.set(0)
        if len(IPs)==0:
            print("ERROR: no cluster nodes found...")
            exit()
        IP_sel = IPs[0] #TODO select best ping?
        
        self.varC1 = tkinter.BooleanVar()
        self.varC1.set(True)
        self.check = tkinter.Checkbutton(frame, text="CHAT", variable=self.varC1)
        self.check.pack()
        self.varC2 = tkinter.BooleanVar()
        self.varC2.set(False)
        self.check2 = tkinter.Checkbutton(frame, text="PoH", variable=self.varC2)
        self.check2.pack()

        w8 = tkinter.Label(frame, text="Client Name: "+client_uid)
        w8.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd2 = (frame.register(self.callbackE2))
##        w9 = tkinter.Entry(frame, validate='all', validatecommand=(vcmd2, '%P')) 
##        w9.insert(0,"321")
##        w9.pack(side = tkinter.TOP, anchor = tkinter.W)
        
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
                frame, text="Send Msg", command=send
                )
        self.send.pack(side = tkinter.LEFT)
        self.stopsend = tkinter.Button(
                frame, text="Stop Sending", command=stop_send
                )
        self.stopsend.pack(side = tkinter.LEFT)
        
        frame.pack()
        

    def quitting(self):
        global consuming, sending
        consuming=False
        sending=False
        time.sleep(1.5)
        cleanall()
        root.destroy()

    def ipsel(self):
        global IP_sel
        IP_sel = IPs[int(varGr.get())]
        selection = "You selected the ip " + str(IP_sel)
        print(selection)     

    def callbackE(self, P):
        if str.isdigit(P):
            #print ("msg " + str(P))
            self.speed = float(P)/10
            return True
        elif P == '':
            self.speed='10'
            return True
        else:
            return False

    def callbackE2(self, P):
        if str.isdigit(P):
            #print ("msg " + str(P))
            temp= str(P)
            self.Lserie=[]
            for c in temp:
                self.Lserie.append(c)
            return True
        else:
            return False           

                               
root = tkinter.Tk()
root.title("AnuuTech Client Stress Test v0.1.0beta")

def randomstring(stringLength):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))

def conn():
    global consuming
    if not consuming:
        t2 = threading.Thread(target=keepconnection)  
        t2.start()
        # threads.append(t2) since it's calling cleanall, it must not be part of threads.join

def disconn():
    global consuming, sending
    consuming=False
    sending=False
    cleanall()
    
    
def keepconnection():
    global consuming, connection, channel, IP_sel, threads
    # Start connection keep loop
    consuming=True
    while consuming:
        try:
            print("starting connection for consuming...")
            credentials = pika.PlainCredentials(lay_user,lay_pass)
            print(IP_sel)
            parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials, heartbeat=61)
            connection = pika.BlockingConnection(parameters)
            channel=connection.channel()
            channel.queue_declare(queue=client_uid, auto_delete=True)
            channel.queue_bind(exchange='L3_main_exchange', queue=client_uid, routing_key='all',
                               arguments={'x-match': 'any', 'dest_uid': client_uid, 'dest_all': 'clients'})

            channel.basic_qos(prefetch_count=10)           
            channel.basic_consume(queue=client_uid, on_message_callback=msgconsumer)
            tempstr="Connected to " + IP_sel
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
            sending=False
            consuming=False
            break
        except:
            e = sys.exc_info()[1]
            print( "<p>WARNING! Unidentified error, trying to reinit...: %s</p>" % e )
            cleanall()
            continue
        
def send():
    global threads, consuming
    if consuming:
        t = threading.Thread(target=sending_msg)  
        t.start()
        threads.append(t)
    else:
        mlist.insert(0,"Impossible to send msg, not connected!")

def stop_send():
    global sending
    sending=False
    mlist.insert(0,"Sending stopped.")

def msgconsumer(ch, method, properties, body):
    global i2, timest_in, timest_i2, old_speed2
    hdrs=properties.headers
    #msg=str(body,'utf-8') only works in Python 3
    msg= json.loads(body.decode('utf-8'))
    
    if app.varC1.get() and msg.get('type')=='CHAT':
        i2 += 1
        print("CHAT "+msg['uid']+" Received " + msg['content']['chat_msg'])
    elif (msg.get('type')=='POH_L3_R1_DONE' and hdrs.get('dest_uid')==client_uid):
        print("POH back" + msg['uid'])
        #send to a second node
        headers=initheaders()
        headers['service']='poh'
        headers['dest_uid']='L3Node_I4xn9A'
        msg['type']='POH_L3_R2'
        msgs_tosend.append([headers, msg])
    # Receiving speed calculation
    time_st_now=time.time()
    if (time_st_now >= timest_in + 0.1):
        cur_speed = (i2-timest_i2)/(time_st_now-timest_in)
        disp_speed = 0.3*cur_speed+0.7*old_speed2
        label_IR.set(str(disp_speed))
        old_speed2=disp_speed
        timest_i2=i2
        timest_in=time_st_now     
    ch.basic_ack(delivery_tag = method.delivery_tag)
    
def sending_msg():
    global connection, channel2, connection2, sending, IP_sel
    global i, timest_out, timest_i, cur_timeout, old_speed
    # get node uid from DB
    db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
    db_client = pymongo.MongoClient(db_url)
    at_db = db_client['AnuuTechDB']
    nodes_col = at_db['nodes']
    db_query = { 'IP_address': IP_sel}
    db_filter = {'uid':1, '_id':0}
    nodeuid=list(nodes_col.find_one(db_query, db_filter).values())[0]
    sending=True
    mlist.insert(0,"Start sending Msg.")
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials, heartbeat=51)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()
    msg=initmsg()
    headers=initheaders()
    tx=str('msg from ' + client_uid)
    ik=0
    while sending:
        try:
            isent=0
            #headers={'service': 'chat', 'dest_all': 'clients', 'type': 'CHAT', 'sender_uid': client_uid}
            if app.varC1.get():
                headers['service']= 'chat'
                headers['dest_all']= 'clients'
                msg['uid']= str(i)
                msg['type']= 'CHAT'
                msg['content']={'chat_msg': tx}
                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(headers=headers),body=(json.dumps(msg)))
                print("msg sent: CHAT " + msg['content']['chat_msg'] + " "+ msg['uid'])
                isent += 1
            elif app.varC2.get():
                msg['uid']= str(i)
                headers['service']= 'poh'
                msg['type']= 'POH_L3_R1'
                headers['dest_uid']= nodeuid
                headers['sender_node_IP']=IP_sel
                if 1 ==1:
                    msg['content']['tx_hash']='14c836ecd2dbcbd02c702f4fc4c19b8f5525e7fe93b77cd3723a08012d1eb589'
                    msg['content']['timestamp']=time.time()
                    #msg['content']['signer_nodeL3']='L3Node_gRKXrd'
                    #msg['content']['fingerprintL3']='5ee8048b54eb8025d86beeefcf58ca0c90867ad2205e102f90b47631e42a4683aeaaf54af155c5b541ada681961d808ea4416a13beb71b7fe8fc757faf9f778ee00a875ae88bc4ee30b81a07a08f59e7e05daf778529f63609b92b4e6887b35766d23a7dfb5e3b0f0573563b7f83ec7e7d06e30665c2871ee4ab12736b3a0098'
                else:
                    msg['content']['tx_hash']='fb831a4dda50b99d9d848cdbf386a1aefc2196fca4644b7b02ee4387873caac7'
                    msg['content']['timestamp']=1654192886.5420983
                    msg['content']['signer_nodeL3']='L3Node_I4xn9A'
                    msg['content']['fingerprintL3']='133996ca6b6f0ff538d9fe77489016565039eaa4df329153a127df8af34298406bf4e1d328d0562bdc47fffae1a57bcd1a61cb1d1f79000cc0c35febaa020b05631d10e99ad2864f0ab7d5b05d8b76c048669d06b39ea6c000eb0c66b2222a13baf698ed5f780268aa23848d17f34718b361d63c821c5c8bc3be70853794140b'
                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(headers=headers), body=(json.dumps(msg)))
                print("msg sent: PoH " + msg['uid'])
                isent += 1
                ik += 1
                while len(msgs_tosend)>0:
                    headers2, msg2=msgs_tosend.pop()
                    channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                           properties=pika.BasicProperties(headers=headers2), body=(json.dumps(msg2)))
                    print("msg sent: PoH--2 " + msg2['uid'])
                    #isent += 1
                
            if isent>0:
                # Real sending speed calculation
                if ( i%1 == 0):
                    time_st_now=time.time()
                    if (time_st_now >= timest_out + 0.1):
                        cur_speed = (i-timest_i)/(time_st_now-timest_out)
                        disp_speed = 0.3*cur_speed+0.7*old_speed
                        label_OR.set(str(disp_speed))
                        old_speed = disp_speed
                        if (app.speed != 0):
                            if(cur_speed > 1.1*app.speed):
                                cur_timeout=min(max(cur_timeout*1.09,1),10000)
                            if(cur_speed < 0.9*app.speed):
                                cur_timeout=min(max(cur_timeout*0.91,1),10000)               
                        timest_i=i
                        timest_out=time_st_now
                i += isent
                if (int(app.speed) != 1974):
                    time.sleep(cur_timeout/1000)
            else:
                connection2.sleep(0.1) # ensure heartbeat
        except:
            e = sys.exc_info()[1]
            print( "<p>Problem while sending, trying to reinit connections...: %s</p>" % e )
            try:
                connection.close() #try to reinit through keep_connection
            except:
                print('Problem while sending and impossible to stop consuming')
            break
    try:
        connection2.close()
    except:
        e = sys.exc_info()[1]
        print( "<p>Problem when closing sending connection: %s</p>" % e )

def initmsg():
    msg_empty = {
        'uid': '0',
        'content': {},
        'type': '',
        'timestamp':time.time()
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
        'retry': 0
        }
    return basic_headers
     
def cleanall():
    # clean all connections
    global connection, connection2, channel, threads
    print ("Cleaning all...")
    sending=False #stop sending
    time.sleep(1)
    
    # Clean close of connections
    try:
        channel.stop_consuming()
    except:
        e = sys.exc_info()[1]
        print( "<p>Error when stopping consuming: %s</p>" % e )
    try:
        # Wait for all to complete
        for thread in threads:
            thread.join()
        connection.close()
    except:
        e = sys.exc_info()[1]
        print( "<p>Problem when closing consumer connection: %s</p>" % e )
    try:
        mlist.insert(0,"Disconnected!")
    except:
        print("Disconnected!")

#MAIN CALL
#CLIENT uid
client_uid=str('client_'+randomstring(4))
#print(client_uid)
lay_pass=ii_helper('node_data/access.bin', '1')
app=App(root)
label_IR.set("NaN")
label_OR.set("NaN")
root.mainloop()
#below happened at closure from CTRL-C
consuming=False
sending=False
