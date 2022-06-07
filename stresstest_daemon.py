import pika
import time
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
nodeslist={} # UIDs and IPs of all nodes 
port=5672
virtual_host='anuutech'
IP_sel=[]
sending=False
consuming=False
threads=[]
msgs_tosend=[]
lay_pass=''

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
    return null
def randomstring(stringLength):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))

db_pass=ii_helper('node_data/access.bin', '12')
lay_pass=ii_helper('node_data/access.bin', '1')

client_uid=str('client_'+randomstring(4))
print(client_uid)

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
            print("Connected to " + str(IP_sel))
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
    t = threading.Thread(target=sending_msg)  
    t.start()

def msgconsumer(ch, method, properties, body):
    global nodeslist_poh
    hdrs=properties.headers
    msg= json.loads(body.decode('utf-8'))
    #print(msg)
    if msg.get('type')=='CHAT':
        print("CHAT "+msg['uid']+" Received " + msg['content']['chat_msg'])
    elif (msg.get('type')=='DATA_LOADED' and hdrs.get('dest_uid')==client_uid):
        print("File has been retrieved: "+msg['uid'])
    elif (msg.get('type')=='POH_L3_R1_DONE' and hdrs.get('dest_uid')==client_uid):
        print("POH back" + msg['uid'])
        #send to a second node
        node_uid2=list(nodeslist_poh.keys())[(sum(msg['content']['fingerprintL3'].encode()))%len(nodeslist_poh.keys())]
        headers=initheaders()
        headers['service']='poh'
        headers['dest_uid']=node_uid2
        msg['type']='POH_L3_R2'
        msgs_tosend.append([headers, msg])  
    ch.basic_ack(delivery_tag = method.delivery_tag)
    
def sending_msg():
    global connection, channel2, connection2, sending, IP_sel, msg_per_sec
    
    # get node uid from DB
    db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+defaultL3nodes[0]+':27017/?authMechanism=DEFAULT&authSource=admin'
    db_client = pymongo.MongoClient(db_url)
    at_db = db_client['AnuuTechDB']
    nodes_col = at_db['nodes']
    db_query = { 'IP_address': IP_sel}
    db_filter = {'uid':1, '_id':0}
    nodeuid=list(nodes_col.find_one(db_query, db_filter).values())[0]
    sending=True
    print("Start sending Msg.")
    credentials = pika.PlainCredentials(lay_user,lay_pass)
    parameters=pika.ConnectionParameters(IP_sel, port,virtual_host, credentials, heartbeat=51)
    connection2 = pika.BlockingConnection(parameters)
    channel2 = connection2.channel()
    i=0
    while sending:
        msg=initmsg()
        headers=initheaders()
        # Ensure all outgoing messages have the node IP well set
        headers['sender_node_IP']=IP_sel
        tx=str('msg from ' + client_uid+ " "+randomstring(12))
        msg['uid']= str(i)
        try:
            randomtype=random.choice([0, 1, 2])
            if randomtype== 0:
                headers['service']= 'chat'
                headers['dest_all']= 'clients'
                msg['type']= 'CHAT'
                msg['content']={'chat_msg': tx}
                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(headers=headers),body=(json.dumps(msg)))
                print("msg sent: CHAT " + msg['content']['chat_msg'] + " "+ msg['uid'])
                
            elif randomtype == 1:
                headers['service']= 'poh'
                headers['dest_uid']= nodeuid
                headers['sender_node_IP']=IP_sel
                msg['type']= 'POH_L3_R1'
                msg['content']['tx_hash']=randomstring(64)
                msg['content']['timestamp']=time.time()

                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(headers=headers), body=(json.dumps(msg)))
                print("msg sent: PoH " + msg['uid'])

            else:
                headers['service']='data_storage'
                msg['type']='GET_DATA'
                msg['content']= '188071675d5b19b30a49bfe5c2d776cc716a4cad2855ad7feadf02f7841e4069'
                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(headers=headers), body=(json.dumps(msg)))
                print("msg sent: Data Storage " + msg['uid'])

                
            while len(msgs_tosend)>0:
                headers2, msg2=msgs_tosend.pop()
                channel2.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                       properties=pika.BasicProperties(headers=headers2), body=(json.dumps(msg2)))
                print("   (msg sent: PoH--2 " + msg2['uid']+")")

            i=i+1
            time.sleep(1/msg_per_sec)
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

def getL3nodesList():
    global nodeslist, nodeslist_chat, nodeslist_poh, defaultL3nodes
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
            at_db = db_client['AnuuTechDB']
            nodes_col = at_db['nodes']
            db_query = { 'level': 'L3'}
            db_filter = {'uid':1, 'IP_address':1, '_id':0, 'services':1}
            templist=list(nodes_col.find(db_query, db_filter))
            nodeslist={n['uid']:n['IP_address'] for n in templist }# if (n['services']['net_storage'] == 1}
            nodeslist_chat={n['uid']:n['IP_address'] for n in templist if n['services']['chat'] == 1}
            nodeslist_poh={n['uid']:n['IP_address'] for n in templist if n['services']['poh'] == 1}
        except:
            time.sleep(1)
            e = sys.exc_info()[1]
            LOGGER.info( "<p>Error while trying to get nodes from DB, retrying...: %s</p>" % e )


def cleanall():
    # clean all connections
    global connection, connection2, channel
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
        connection.close()
    except:
        e = sys.exc_info()[1]
        print( "<p>Problem when closing consumer connection: %s</p>" % e )
    print("Disconnected!")
        
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



#MAIN CALL
#----------------------------------------------------------------
def main():
    global msg_per_sec, sending, consuming, IP_sel, defaultL3nodes
    # Check arguments
    print (len(sys.argv))
    if len(sys.argv) == 3 and float(sys.argv[1])>0 and float(sys.argv[1])<100 :
        msg_per_sec=float(sys.argv[1])
        IP_ind=int(sys.argv[2])
        # get all nodes
        getL3nodesList()
        IP_sel=defaultL3nodes[IP_ind]
        # start 
        send()#start thread sending
        keepconnection()#start thread consuming
    else:
        print("Script needs 1 float parameter and 1 integer: nb of messages per second (betwen 0 and 100) and index of node to use. Please retry.")
        exit()

    #below happened at closure from CTRL-C
    disconn()
    
        
if __name__ == '__main__':
    main()
