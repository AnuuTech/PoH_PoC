# Source for pika part:
# https://github.com/pika/pika/blob/master/examples/asynchronous_consumer_example.py

import functools
import logging
import time
import pika
import os
import sys
import requests
import socket
import json
import string
import random
import pymongo
import urllib
from Crypto.PublicKey import RSA
from threading import Timer, Thread
from collections import Counter
import signal
signal.signal(signal.SIGINT, signal.default_int_handler) # to ensure Signal to be received

class NodeConsumer(object):
    """This is an example consumer that will handle unexpected interactions
    with RabbitMQ such as channel and connection closures.
    If RabbitMQ closes the connection, this class will stop and indicate
    that reconnection is necessary. You should look at the output, as
    there are limited reasons why the connection may be closed, which
    usually are tied to permission related issues or socket timeouts.
    If the channel is closed, it will indicate a problem with one of the
    commands that were issued and that should surface in the output as well.
    """

    def __init__(self, LOGGER, conn_parameters, nodelevel, consumer_method, service):
        """Create a new instance of the consumer class, passing in the PIKA connection parameters.
        :param pika.ConnectionParameters _conn_parameters: The PIKA connection parameters
        :param string nodelevel: Level of the node (L1, L2 or L3)
        """
        self.should_reconnect = False
        self.was_consuming = False
        self._connection = None
        self._channel = None
        self._closing = False
        self._consuming = False
        self._nodelevel =  nodelevel
        self._service = service

        self.LOGGER = LOGGER
        self._conn_parameters = conn_parameters
        self._consumer_method = consumer_method

        # In production, experiment with higher prefetch values
        # for higher consumer throughput
        self._prefetch_count = 1

    def connect(self):
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.
        :rtype: pika.SelectConnection
        """
        self.LOGGER.debug('Connecting to %s', self._conn_parameters)
        return pika.SelectConnection(
            parameters=self._conn_parameters,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed)

    def close_connection(self):
        self._consuming = False
        if self._connection.is_closing or self._connection.is_closed:
            self.LOGGER.debug('Connection is closing or already closed')
        else:
            self.LOGGER.debug('Closing connection')
            self._connection.close()

    def on_connection_open(self, _unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.
        :param pika.SelectConnection _unused_connection: The connection
        """
        self.LOGGER.debug('Connection opened')
        self.open_channel()

    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.
        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error
        """
        self.LOGGER.error('Connection open failed: %s', err)
        self.reconnect()

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.
        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.
        """
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self.LOGGER.warning('Connection closed, reconnect necessary: %s', reason)
            self.reconnect()

    def reconnect(self):
        """Will be invoked if the connection can't be opened or is
        closed. Indicates that a reconnect is necessary then stops the
        ioloop.
        """
        self.should_reconnect = True
        self.stop()

    def open_channel(self):
        """Open a new channel with RabbitMQ by issuing the Channel.Open RPC
        command. When RabbitMQ responds that the channel is open, the
        on_channel_open callback will be invoked by pika.
        """
        self.LOGGER.debug('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we'll declare the exchange to use.
        :param pika.channel.Channel channel: The channel object
        """
        self.LOGGER.debug('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.set_qos()
        
    def set_qos(self):
        """This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before RabbitMQ will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
        """
        self._channel.basic_qos(
            prefetch_count=self._prefetch_count, callback=self.on_basic_qos_ok)

    def on_basic_qos_ok(self, _unused_frame):
        """Invoked by pika when the Basic.QoS method has completed. At this
        point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.
        :param pika.frame.Method _unused_frame: The Basic.QosOk response frame
        """
        self.LOGGER.debug('QOS set to: %d', self._prefetch_count)
        self.start_consuming()

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.
        """
        self.LOGGER.debug('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reason):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.
        :param pika.channel.Channel: The closed channel
        :param Exception reason: why the channel was closed
        """
        self.LOGGER.warning('Channel %i was closed: %s', channel, reason)
        self.close_connection()

    def start_consuming(self):
        """This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if RabbitMQ
        cancels the consumer. It then issues the Basic.Consume RPC command
        which returns the consumer tag that is used to uniquely identify the
        consumer with RabbitMQ. We keep the value to use it when we want to
        cancel consuming. The on_message method is passed in as a callback pika
        will invoke when a message is fully received.
        """
        self.LOGGER.debug('Issuing consumer related RPC commands')
        self.add_on_cancel_callback()
        qname=self._nodelevel+'_'+self._service+'_queue'
        self._consumer_tag = self._channel.basic_consume(
            qname, self.on_message)
        self.was_consuming = True
        self._consuming = True

    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.
        """
        self.LOGGER.debug('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.
        :param pika.frame.Method method_frame: The Basic.Cancel frame
        """
        self.LOGGER.debug('Consumer was cancelled remotely, shutting down: %r',
                    method_frame)
        if self._channel:
            self._channel.close()

    def on_message(self, channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.
        :param pika.channel.Channel channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param bytes body: The message body
        """
        #self.LOGGER.debug('Received message # %s: %s', basic_deliver.delivery_tag, body)
                    #basic_deliver.delivery_tag, properties.headers, body)
        # MODIF FROM ORIGINAL
        if self._consumer_method(channel, basic_deliver, properties, body):
            self.acknowledge_message(basic_deliver.delivery_tag)
        else:
            #self.nacknowledge_message(basic_deliver.delivery_tag)
            self.acknowledge_message(basic_deliver.delivery_tag) # to avoid loop with msg with problems

    def acknowledge_message(self, delivery_tag):
        """Acknowledge the message delivery from RabbitMQ by sending a
        Basic.Ack RPC method for the delivery tag.
        :param int delivery_tag: The delivery tag from the Basic.Deliver frame
        """
        self.LOGGER.debug('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def nacknowledge_message(self, delivery_tag):
        """Nacknowledge the message delivery from RabbitMQ by sending a
        Basic.Nack RPC method for the delivery tag.
        :param int delivery_tag: The delivery tag from the Basic.Deliver frame
        """
        self.LOGGER.debug('Nacknowledging message %s', delivery_tag)
        self._channel.basic_nack(delivery_tag)

    def stop_consuming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.
        """
        if self._channel:
            self.LOGGER.debug('Sending a Basic.Cancel RPC command to RabbitMQ')
            cb = functools.partial(
                self.on_cancelok, userdata=self._consumer_tag)
            self._channel.basic_cancel(self._consumer_tag, cb)

    def on_cancelok(self, userdata):
        """This method is invoked by pika when RabbitMQ acknowledges the
        cancellation of a consumer. At this point we will close the channel.
        This will invoke the on_channel_closed method once the channel has been
        closed, which will in-turn close the connection.
        :param pika.frame.Method _unused_frame: The Basic.CancelOk frame
        :param str|unicode userdata: Extra user data (consumer tag)
        """
        self._consuming = False
        self.LOGGER.debug(
            'RabbitMQ acknowledged the cancellation of the consumer: %s',
            userdata)
        self.close_channel()

    def close_channel(self):
        """Call to close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.
        """
        self.LOGGER.debug('Closing the channel')
        self._channel.close()

    def run(self):
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the SelectConnection to operate.
        """
        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):
        """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
        will be invoked by pika, which will then closing the channel and
        connection. The IOLoop is started again because this method is invoked
        when CTRL-C is pressed raising a KeyboardInterrupt exception. This
        exception stops the IOLoop which needs to be running for pika to
        communicate with RabbitMQ. All of the commands issued prior to starting
        the IOLoop will be buffered but not processed.
        """
        if not self._closing:
            self._closing = True
            self.LOGGER.debug('Stopping')
            if self._consuming:
                self.stop_consuming()
                self._connection.ioloop.start()
            else:
                self._connection.ioloop.stop()
            self.LOGGER.debug('Stopped')


class ReconnectingNodeConsumer(object):
    """This is a consumer that will reconnect if the nested
    Consumer indicates that a reconnect is necessary.
    """

    SW_VERSION='0.0.3beta'
    VHOST='anuutech'
    REQ_TIMEOUT=5 #timeout for http requests
    NODE_TICK_INTERVAL=60.0
    MPORT=15672
    PORT=5672
    LOGGER = logging.getLogger('SERVICE_LOGGER')
    MAIN_PATH=''#Disabled for now os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    IP_PATH=MAIN_PATH+'node_data/ip.file'
    NODESLIST_PATH=MAIN_PATH+'node_data/nodeslist.file'
    NODESLIST_LOWER_PATH=MAIN_PATH+'node_data/nodeslist_lower.file'
    UID_PATH=MAIN_PATH+'node_data/node_uid.file'
    PS_PATH=MAIN_PATH+'node_data/ps_loc.file'
    SERVICES_PATH='node_services/services.conf'

    #helper functions
    def ii_helper(self, fily, sel):
        abc = b'k_AnuuTech'
        abcl = len(abc)
        with open(fily, 'rb') as s_file:
            brezl=s_file.readlines()
        brez=brezl[int(sel)].replace(b'\n',b'')
        brezi=bytes(c ^ abc[i % abcl] for i, c in enumerate(brez)).decode()
        return (brezi)
    
    def randomstring(self, stringLength):
        letters = string.ascii_letters
        return ''.join(random.choice(letters) for i in range(stringLength))
    
    def __init__(self, xargs,yargs):
        self._reconnect_delay = 0
        self._pikaconn_parameters = None
        self._nodeslist=[]
        self._nodeslist_lower=[]
        self._uid=''
        self._msgs_to_send = []
        self._first_init = True
        self._sending = False
        self._threadsend = None

        self._own_IP=''
        self._nodelevel = str(xargs)
        self._service = str(yargs)
        self._node_user='layer_local'
        self._np='pass_'
        self._db_pass=self.ii_helper('node_data/access.bin', '12')

        # Get Signature keys
        pubkey_path='node_pub.key'
        privkey_path='node_priv.key'
        if not os.path.isfile(pubkey_path) or not os.path.isfile(privkey_path):
            # issue keys
            private_key = RSA.generate(1024)
            public_key = private_key.publickey()
            self.LOGGER.info('No RSA keys found, new ones are created')
            with open (privkey_path, "wb") as prv_file:
                prv_file.write(private_key.exportKey('PEM','annu_seed-l'))
            with open (pubkey_path, "wb") as pub_file:
                pub_file.write(public_key.exportKey('PEM'))
        else:
            with open (privkey_path, "rb") as prv_file:
                private_key=RSA.importKey(prv_file.read(),'annu_seed-l')
            with open (pubkey_path, "rb") as pub_file:
                public_key=RSA.importKey(pub_file.read())
                self.LOGGER.debug('RSA keys sucessfully loaded.')
        self._PUBKEY=public_key
        self._PRIVKEY=private_key

    def run(self):
        #LOGGER init
        hdlr = logging.StreamHandler()
        fhdlr = logging.FileHandler("logs/log_"+self._service+".txt", mode='w')
        format = logging.Formatter('%(asctime)-15s %(levelname)s : %(message)s')
        fhdlr.setFormatter(format)
        hdlr.setFormatter(format)
        self.LOGGER.addHandler(hdlr)
        self.LOGGER.addHandler(fhdlr)
        self.LOGGER.setLevel(logging.DEBUG)
        #Ensure existing log file
        self.LOGGER.info("Service "+self._service +" has started\n")

        #update password of node
        with open(self.PS_PATH, 'r') as ps_file:
            self._np=self._np+ps_file.read()

        #node name read from uid
        if os.path.isfile(self.UID_PATH):
            with open(self.UID_PATH, 'r') as uid_file:
                self._uid=uid_file.read().strip()
      
        #start the regular ticking
        self._ticking() # will init a ticking dameon

        # Update consumer connection parameters
        credentials = pika.PlainCredentials(self._node_user, self._np)
        self._pikaconn_parameters = pika.ConnectionParameters('localhost', self.PORT, self.VHOST, credentials,
                                                              heartbeat=10)
        
        #First initialisation of node
        self._initnode()

        # Start sending_msg thread on a separate connection
        self._threadsend = Thread(target=self._sending_msg)
        self._threadsend.start()

        # Start the main thread-consuming
        self._consumer = NodeConsumer(self.LOGGER, self._pikaconn_parameters, self._nodelevel, self._node_consumer, self._service)
        while True:
            try:
                self._consumer.run()
            except KeyboardInterrupt:
                self._sending = False
                self._consumer.stop()
                break
            self._maybe_reconnect()

    def _maybe_reconnect(self):
        self._sending = False # Stop sending for now...
        self._threadsend.join()
        if self._consumer.should_reconnect:
            self._consumer.stop()
            reconnect_delay = self._get_reconnect_delay()
            self.LOGGER.info('Reconnecting after %d seconds', reconnect_delay)
            time.sleep(reconnect_delay)
            # Re-init node, redefine consumer and restart sending thread
            self._initnode()
            self._consumer = NodeConsumer(self.LOGGER, self._pikaconn_parameters, self._nodelevel, self._node_consumer, self._service)
            self._threadsend = Thread(target=self._sending_msg)
            self._threadsend.start()

    def _get_reconnect_delay(self):
        if self._consumer.was_consuming:
            self._reconnect_delay = 1 # TODO initially zero... set to zero thus?
        else:
            self._reconnect_delay += 1
        if self._reconnect_delay > 30:
            self._reconnect_delay = 30
        return self._reconnect_delay

    def _initnode(self):
        #IP from file
        if os.path.isfile(self.IP_PATH):
            with open(self.IP_PATH, 'r') as ip_file:
                self._own_IP=ip_file.read().strip()

        #nodelist read from file
        if os.path.isfile(self.NODESLIST_PATH):
            with open(self.NODESLIST_PATH, 'r') as nodes_file:
                self._nodeslist=json.load(nodes_file)

        #lower nodelist read from file
        if os.path.isfile(self.NODESLIST_LOWER_PATH):
            with open(self.NODESLIST_LOWER_PATH, 'r') as nodes_file:
                self._nodeslist_lower=json.load(nodes_file) 

        # Create service queue
        try:
            connection = pika.BlockingConnection(self._pikaconn_parameters)
            channel=connection.channel()
            qname_i=self._nodelevel+'_'+self._service+'_queue'
            exname_i=self._nodelevel+'_main_exchange'
            channel.queue_declare(queue=qname_i)
            #bind the queue to the exchange
            h_arguments=self._get_headers_arg()
            channel.queue_bind(exchange=exname_i, queue=qname_i, routing_key='all',
                           arguments=h_arguments)
            #Close the connection
            connection.close()
            
        except pika.exceptions.AMQPConnectionError as err:
            logmsg=str("Impossible to create the initial connection!".format(err))
            self.LOGGER.critical(logmsg)

        logmsg=("INITIALISATION of "+self._uid+" done, IP: " + self._own_IP+
                " number of layer nodes: "+str(len(self._nodeslist))+
                " number of lower layer nodes: "+str(len(self._nodeslist_lower)))
        self.LOGGER.info(logmsg)

    def _get_headers_arg(self):
        argum={'x-match': 'any', 'service': self._service}
        return argum

    def _ticking(self):
        if not self._first_init:
            self._ticking_actions()
        self._first_init = False

        t = Timer(self.NODE_TICK_INTERVAL, self._ticking)
        t.daemon=True
        t.start()

    def _ticking_actions(self):
        return

    # Consumer method
    def _node_consumer(self, ch, method, properties, body):
        try:
            msg=json.loads(body.decode("utf-8"))
            self.LOGGER.info("Received decode: " + str(msg))
            hdrs=properties.headers
            self.LOGGER.debug(hdrs)
            return (self._msg_process(msg, hdrs))
        except:
            e = sys.exc_info()[1]
            logmsg=str("<p>Problem while consuming: %s</p>" % e )
            self.LOGGER.error(logmsg)
            return False
        
    def _msg_process(self, msg, hdrs):
        self.LOGGER.info("Entered default method")
        return True
        
    def _initmsg(self):
        basic_msg = {
        "uid": self.randomstring(12),
        "content": "some client data",
        "content_hash": "used for HMES",
        "pubk": "empty"
        }
        return basic_msg

    def _initheaders(self):
        basic_headers = {
            'sender_uid': self._uid,
            'sender_node_IP': self._own_IP,
            'dest_uid': '',
            'dest_IP': '',
            'dest_all': '',
            'service': self._service,
            'type': '',
            'hop' : 0,
            'retry': 0
            }
        return basic_headers
                

    # Sending thread
    def _sending_msg(self):
        self._sending=True
        self.LOGGER.info("Starting sending_msg")
        
        while self._sending:
            if len(self._msgs_to_send)>0:
                msg, hdrs, IP, level =self._msgs_to_send.pop(0)
                self.LOGGER.debug(str(msg))
                self.LOGGER.debug(str(hdrs))
                # Define credentials and exchange name according to level
                nuser = str(level+'ext_node')
                np = self.ii_helper('node_data/access.bin', 4+int(level[1]))
                send_ex = str(level+'_main_exchange')
                # Call the sender method
                send_credentials = pika.PlainCredentials(nuser, np)
                self._sender(msg, hdrs, send_credentials, IP, send_ex, level)
            else:
                time.sleep(0.01) # prevent loop CPU usage


    # Sender method
    # TODO ensure delivery! https://github.com/pika/pika/blob/master/examples/confirmation.py
    def _sender(self, msg, hdrs, send_credentials, IP, send_ex, level):
        # creation of sending connection:
        try:
            parameters = pika.ConnectionParameters(IP, self.PORT, self.VHOST, send_credentials,
                                                   heartbeat=6)
            sendingconn = pika.BlockingConnection(parameters)
            sendingchan = sendingconn.channel()
            sendingchan.basic_publish(exchange=send_ex, routing_key='all',
                                      properties=pika.BasicProperties(headers=hdrs),
                                      body=(json.dumps(msg)))
            self.LOGGER.info(str("msg sent: " + hdrs.get('type')))
            sendingconn.close()
        except:
            try:
                sendingconn.close()
            except:
                pass
            e = sys.exc_info()[1]
            # Try to handle the error
            try:
                # check number of retries
                if hdrs['retry']>2:
                    logmsg=str("ERROR: msg "+msg['uid']+ " impossible to send error when create sending connection with 3 retries! %s" %str(e))
                    self.LOGGER.error(logmsg)
                # retry with a random new node
                else: 
                    logmsg=str("ERROR: msg "+msg['uid']+ " impossible to create connection! will retry... %s" %str(e))
                    self.LOGGER.error(logmsg)
                    hdrs['retry']=hdrs['retry']+1
                    # Get a node with same service
                    if level == self._nodelevel:
                        #nodes_s=[n for n in self._nodeslist if (n['services'][hdrs['service']] == 1)] Replaced by iteration loop to avoid errors
                        nodes_s=[]
                        for n in self._nodeslist:
                            if 'services' in n:
                                if hdrs['service'] in n['services']:
                                    if (n['services'][hdrs['service']] == 1):
                                        nodes_s.append(n)
                    else:
                        #nodes_s=[n for n in self._nodeslist_lower if (n['services'][hdrs['service']] == 1)]
                        for n in self._nodeslist_lower:
                            if 'services' in n:
                                if hdrs['service'] in n['services']:
                                    if (n['services'][hdrs['service']] == 1):
                                        nodes_s.append(n)
                        
                    random.shuffle(nodes_s)
                    if len(nodes_s) < 2:
                        self.LOGGER.error("No other node with service "+hdrs['service']+" is available, impossible to process msg "+msg['uid'])
                    else:
                        IP=nodes_s[0]['IP_address']
                        self.LOGGER.info("Msg "+msg['uid']+" retrying with "+hdrs['service']+" on IP: "+nodes_s[0]['IP_address'])
                        self._msgs_to_send.append([msg, hdrs, IP, level ])
            except:
                e = sys.exc_info()[1]
                self.LOGGER.critical('Impossible to send a message, message discarded! %s' %str(e))

    # Generic method to update infos on AnuuTechDB
    def _updateDB(self, collects, db_query, db_values_toset ):
        try:
            IP_sel=''
            # Get list of services on the nodes
            serv_list={}
            with open(self.SERVICES_PATH, 'r') as serv_file:
                serv_list=json.load(serv_file)
                self.LOGGER.info("List of services configured: " + str(serv_list))
            # Prepare connection to DB
            # Check if service is available on node
            if 'net_storage' in serv_list:
                if serv_list['net_storage'] == 1:
                    IP_sel='localhost' # use the local service
            if IP_sel == '':
                # Select a node from the existing list of nodes #TODO may also check on lower layer nodes!
                #nodes_ns=[n for n in self._nodeslist if n['services']['net_storage'] == 1] Replaced by iteration loop to avoid errors
                nodes_ns=[]
                for n in self._nodeslist:
                    if 'services' in n:
                        if 'net_storage' in n['services']:
                            if (n['services']['net_storage'] == 1):
                                nodes_ns.append(n)
                if len(nodes_ns) == 0:
                    self.LOGGER.warning("No node with net storage service is available, impossible to update own node entry in DB!!")
                else:           
                    random.shuffle(nodes_ns)
                    IP_sel=nodes_ns[0]['IP_address']
            if len(IP_sel)>0:
                db_url='mongodb://admin:' + urllib.parse.quote(self._db_pass) +'@'+IP_sel+':27017/?authMechanism=DEFAULT&authSource=admin'
                with pymongo.MongoClient(db_url) as db_client:
                    at_db = db_client["AnuuTechDB"]
                    col = at_db[collects]
                    if db_values_toset is not None:
                        # Update/Insert values, using upsert = True
                        col.update_one(db_query, db_values_toset, True)
                        self.LOGGER.debug(str(db_values_toset))
                    else:
                        # use insert command
                        col.insert_one(db_query)
                    self.LOGGER.info("Values updated on DB, own IP = " + self._own_IP)
        except:    
            e = sys.exc_info()[1]
            self.LOGGER.error('Impossible to updateDB!!  %s' %str(e))
