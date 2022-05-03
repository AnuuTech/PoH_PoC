import pika
import time
import tkinter
import threading
import socket
import random
import string
import json
import sys
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

#get hostname
hostname=socket.gethostname()

#check local/debug mode
if len(sys.argv) == 2:
    if sys.argv[1] == 'local':
        defaultL3nodes.append('192.168.1.71')

#get default L3nodes
defaultL3nodes_hosts=['at-clusterL3'+ii_helper('access.bin', '8'),
                      'at-clusterL3b'+ii_helper('access.bin', '8')]
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
        IPs=defaultL3nodes #getL3nodesList()
        
        w2 = tkinter.Label(frame, text="Outgoing rate goal [/s] (0 for max):")
        w2.pack(side = tkinter.TOP, anchor = tkinter.W)
       
        vcmd = (frame.register(self.callbackE))
        w = tkinter.Entry(frame, validate='all', validatecommand=(vcmd, '%P')) 
        w.insert(0,"1")
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
        self.check2 = tkinter.Checkbutton(frame, text="HMES", variable=self.varC2)
        self.check2.pack()

        w8 = tkinter.Label(frame, text="Client Name: "+Client_ID)
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
            self.speed = P 
            return True
        elif P == "":
            self.speed="10"
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
root.title("AnuuTech Msg emulator")

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
            #channel.queue_declare(queue=queue_name, durable=True, arguments={"x-queue-type": "quorum"})
            #channel.queue_bind(exchange='laylocal_exchange', queue=queue_name, routing_key='all')

            channel.basic_qos(prefetch_count=100)           
            channel.basic_consume(queue=queue_name, on_message_callback=msgconsumer)
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
    #msg=str(body,'utf-8') only works in Python 3
    msg= json.loads(body.decode("utf-8"))
    #print(msg)
    if app.varC1.get() and msg['type']=='CHAT':
        i2 += 1
        print("CHAT "+msg['uid']+" Received " + msg['content'])
    if msg['type']=='HMES' and msg['initial_sender']==queue_name:
        i2 += 1
        print("HMES "+msg['uid']+" Received " + str(msg['tasks_done']))
    # Receiving speed calculation
    time_st_now=time.time()
    if (time_st_now >= timest_in + 0.1):
        cur_speed = (i2-timest_i2)/(time_st_now-timest_in)
        disp_speed = 0.3*cur_speed+0.7*old_speed2
        label_IR.set(str(int(disp_speed)))
        old_speed2=disp_speed
        timest_i2=i2
        timest_in=time_st_now     
    ch.basic_ack(delivery_tag = method.delivery_tag)
    
def sending_msg():
    global connection, channel2, connection2, sending
    global i, timest_out, timest_i, cur_timeout, old_speed
    sending=True
    mlist.insert(0,"Start sending Msg.")
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials, heartbeat=51)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()
    msg=initmsg()
    while sending:
        try:
            isent=0
            
            if app.varC1.get():
                msg['uid']= str(i)
                msg['type']='CHAT'
                msg['content']="msg from " + Client_ID
                channel2.basic_publish(exchange='L3_client_exchange', routing_key='CHAT', body=(json.dumps(msg)))
                print("msg sent: " + msg['type']+ msg['content'] + " "+ msg['uid'])
                isent += 1
            if app.varC2.get():
                msg['uid']= str(i)
                msg['type']='HMES'
                msg['content']="hash msg from " + Client_ID
                channel2.basic_publish(exchange='L3_client_exchange', routing_key='HMES', body=(json.dumps(msg)))
                print("msg sent: " + msg['type']+ msg['content'] + " "+ msg['uid'])
                isent += 1
            if isent>0:
                # Real sending speed calculation
                if ( i%1 == 0):
                    time_st_now=time.time()
                    if (time_st_now >= timest_out + 0.1):
                        cur_speed = (i-timest_i)/(time_st_now-timest_out)
                        disp_speed = 0.3*cur_speed+0.7*old_speed
                        label_OR.set(str(int(disp_speed)))
                        old_speed = disp_speed
                        if (int(app.speed) != 0):
                            if(cur_speed > 1.1*int(app.speed)):
                                cur_timeout=min(max(cur_timeout*1.09,1),1000)
                            if(cur_speed < 0.9*int(app.speed)):
                                cur_timeout=min(max(cur_timeout*0.91,1),1000)               
                        timest_i=i
                        timest_out=time_st_now
                i += isent
                if (int(app.speed) != 1974):
                    time.sleep(int(cur_timeout)/1000)
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
    "uid": '0',
    "initial_sender": Client_ID,
    "final_receiver": "",
    "type": "",
    "content": ""
    }
    return msg_empty
            
def getL3nodesList():
    global connection, connection2, channel, channel2, IPs, threads
    timestamp_config=time.time()
    waiting=False
    while len(IPs)==0:
        if (time.time()-timestamp_config > 30):
            print( "ERROR: impossible to get L3nodes list, timeout")
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
                channel.queue_declare(queue=queue_name, auto_delete=True)
                channel.queue_bind(exchange='laylocal_exchange', queue=queue_name, routing_key='all')
                t2 = threading.Thread(target=configconsumer)
                t2.start()
                threads.append(t2)
                
                channel2=connection2.channel()
                msg=initmsg()
                msg['uid']= '-1'
                msg['type']='getnodeslist'
                msg['content']="config msg from " + hostname
                channel2.basic_publish(exchange='', routing_key='laylocal_client_Tx', body=(json.dumps(msg)))
                print("msg sent: " + msg['type']+ msg['content'] + " "+ msg['uid'])
                print("L3nodes list request sent to " + defaultL3nodes[0])
                waiting = True
                time.sleep(2)
            except FileNotFoundError:
                waiting=False
                e = sys.exc_info()[0]
                print( "Problem requesting L3nodes list, retrying: %s" % e )
                print(e)
                cleanall()
                

    print( "List of L3nodes obtained: %s" %IPs )
    cleanall()

def configmsgconsumer(ch, method, properties, body):
    global IPs
    msg=json.loads(body.decode("utf-8"))
    if (msg['type']=='getnodeslist' and msg['final_receiver']==queue_name):
        temp=msg['content'].split(',')
        IPs=temp[1:len(temp)]
    ch.basic_ack(delivery_tag = method.delivery_tag)

def configconsumer():
    global channel
    channel.basic_consume(queue=queue_name, on_message_callback=configmsgconsumer)
    try:
        channel.start_consuming()
    except:
        e = sys.exc_info()[0]
        print( "<p>Problem while configconsuming: %s</p>" % e )
     
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
#CLIENT ID
Client_ID=str(hostname+randomstring(4))
#print(Client_ID)
queue_name="L3_client_queue"
lay_pass=ii_helper('access.bin', '1')
app=App(root)
label_IR.set("NaN")
label_OR.set("NaN")
root.mainloop()
#below happened at closure from CTRL-C
consuming=False
sending=False
