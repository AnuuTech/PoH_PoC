import pika
import sys

localuser='layer_local'
localpass='pass_'

#read pass of node
with open('ps_loc.file', 'r') as ps_file:
    localpass=localpass+ps_file.read()

def initCluster():
    #Connect
    credentials = pika.PlainCredentials(localuser,localpass)
    parameters=pika.ConnectionParameters('localhost', 5672 , 'anuutech', credentials, heartbeat=61)
    connection = pika.BlockingConnection(parameters)
    channel=connection.channel()
    
    #Declare a quorum queue for intralayer communication
    qname_i='%s_intralayer_queue' %nodelevel
    exname_i='%s_intralayer_exchange' %nodelevel
    channel.queue_declare(queue=qname_i, durable=True, arguments={"x-queue-type": "quorum"})
    #Declare the exchange
    channel.exchange_declare(exchange=exname_i,exchange_type='direct')
    #Bind the queue to the exchange
    channel.queue_bind(exchange=exname_i, queue=qname_i, routing_key='all')

    #Declare a quorum queue for extralayer communication (for L2 or L3)
    if nodelevel == 'L3':
        # Client incoming communication
        qname_c='L3_client_queue'
        exname_c='L3_client_exchange'
        channel.queue_declare(queue=qname_c, durable=True, arguments={"x-queue-type": "quorum"})
        channel.exchange_declare(exchange=exname_c,exchange_type='direct')
        channel.queue_bind(exchange=exname_c, queue=qname_c, routing_key='CHAT')
        channel.queue_bind(exchange=exname_c, queue=qname_i, routing_key='HMES')#Bind with L3intra queue
        # Layer3 - Layer2 communication
        qname_L3L2='L3_L2_queue'
        exname_L3L2='L3_L2_exchange'
        channel.queue_declare(queue=qname_L3L2, durable=True, arguments={"x-queue-type": "quorum"})
        channel.exchange_declare(exchange=exname_L3L2,exchange_type='direct')
        channel.queue_bind(exchange=exname_L3L2, queue=qname_L3L2, routing_key='toL2')
        channel.queue_bind(exchange=exname_L3L2, queue=qname_i, routing_key='toL3')#Bind with L3intra queue
    if nodelevel == 'L2':
        # Layer2 - Layer1 communication
        qname_L2L1='L2_L1_queue'
        exname_L2L1='L2_L1_exchange'
        channel.queue_declare(queue=qname_L2L1, durable=True, arguments={"x-queue-type": "quorum"})
        channel.exchange_declare(exchange=exname_L2L1,exchange_type='direct')
        channel.queue_bind(exchange=exname_L2L1, queue=qname_L2L1, routing_key='toL1')
        channel.queue_bind(exchange=exname_L2L1, queue=qname_i, routing_key='toL2')#Bind with L2intra queue
    
    #Close the connection
    connection.close()

#check level
if len(sys.argv) == 2:
    if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
        nodelevel=sys.argv[1]
        #Start the node!
        initCluster() # will init the cluster
    else:
        print("unknown parameter: %s" % sys.argv[1])
else:
    print("Script needs 1 parameter (L1, L2, L3). Please retry.")
