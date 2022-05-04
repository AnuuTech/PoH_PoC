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
    parameters=pika.ConnectionParameters('localhost', 5672 , 'anuutech', credentials)
    connection = pika.BlockingConnection(parameters)
    channel=connection.channel()
    
    #Declare a quorum queue for intralayer communication
    qname_i='%s_main_queue' %nodelevel
    exname_i='%s_main_exchange' %nodelevel
    channel.queue_declare(queue=qname_i, durable=True, arguments={"x-queue-type": "quorum"})
    #Declare the headers main exchange
    channel.exchange_declare(exchange=exname_i,exchange_type='headers')
    #Bind the queue to the exchange
    channel.queue_bind(exchange=exname_i, queue=qname_i, routing_key='all',
                       arguments={'x-match': 'any', 'dest': 'main'})
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
