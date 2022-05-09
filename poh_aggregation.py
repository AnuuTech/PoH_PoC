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
from threading import Timer, Thread
from collections import Counter
from Crypto.PublicKey import RSA
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
import binascii
import pymongo
import urllib
import signal
signal.signal(signal.SIGINT, signal.default_int_handler) # to ensure Signal to be received

#helper function
def ii_helper(fily, sel):
    abc = b'k_AnuuTech'
    abcl = len(abc)
    with open(fily, 'rb') as s_file:
        brezl=s_file.readlines()
    brez=brezl[int(sel)].replace(b'\n',b'')
    brezi=bytes(c ^ abc[i % abcl] for i, c in enumerate(brez)).decode()
    return (brezi)

LOGGER = logging.getLogger('POH_AGGREGATION_LOGGER')

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

    def __init__(self, conn_parameters, nodelevel, consumer_method):
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
        LOGGER.debug('Connecting to %s', self._conn_parameters)
        return pika.SelectConnection(
            parameters=self._conn_parameters,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed)

    def close_connection(self):
        self._consuming = False
        if self._connection.is_closing or self._connection.is_closed:
            LOGGER.debug('Connection is closing or already closed')
        else:
            LOGGER.debug('Closing connection')
            self._connection.close()

    def on_connection_open(self, _unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.
        :param pika.SelectConnection _unused_connection: The connection
        """
        LOGGER.debug('Connection opened')
        self.open_channel()

    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.
        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error
        """
        LOGGER.error('Connection open failed: %s', err)
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
            LOGGER.warning('Connection closed, reconnect necessary: %s', reason)
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
        LOGGER.debug('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
        Since the channel is now open, we'll declare the exchange to use.
        :param pika.channel.Channel channel: The channel object
        """
        LOGGER.debug('Channel opened')
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
        LOGGER.debug('QOS set to: %d', self._prefetch_count)
        self.start_consuming()

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.
        """
        LOGGER.debug('Adding channel close callback')
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
        LOGGER.warning('Channel %i was closed: %s', channel, reason)
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
        LOGGER.debug('Issuing consumer related RPC commands')
        self.add_on_cancel_callback()
        qname='%s_own_queue' %self._nodelevel
        self._consumer_tag = self._channel.basic_consume(
            qname, self.on_message)
        self.was_consuming = True
        self._consuming = True

    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.
        """
        LOGGER.debug('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.
        :param pika.frame.Method method_frame: The Basic.Cancel frame
        """
        LOGGER.debug('Consumer was cancelled remotely, shutting down: %r',
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
        LOGGER.debug('Received message # %s: %s', basic_deliver.delivery_tag, body)
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
        LOGGER.debug('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def nacknowledge_message(self, delivery_tag):
        """Nacknowledge the message delivery from RabbitMQ by sending a
        Basic.Nack RPC method for the delivery tag.
        :param int delivery_tag: The delivery tag from the Basic.Deliver frame
        """
        LOGGER.debug('Nacknowledging message %s', delivery_tag)
        self._channel.basic_nack(delivery_tag)

    def stop_consuming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.
        """
        if self._channel:
            LOGGER.debug('Sending a Basic.Cancel RPC command to RabbitMQ')
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
        LOGGER.debug(
            'RabbitMQ acknowledged the cancellation of the consumer: %s',
            userdata)
        self.close_channel()

    def close_channel(self):
        """Call to close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.
        """
        LOGGER.debug('Closing the channel')
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
            LOGGER.debug('Stopping')
            if self._consuming:
                self.stop_consuming()
                self._connection.ioloop.start()
            else:
                self._connection.ioloop.stop()
            LOGGER.debug('Stopped')


class ReconnectingNodeConsumer(object):
    """This is a consumer that will reconnect if the nested
    Consumer indicates that a reconnect is necessary.
    """
    
    VHOST='anuutech'
    NODE_TICK_INTERVAL=60.0
    UID_PATH='/home/node_uid.file'
    MPORT=15672
    PORT=5672
  
    def __init__(self, xargs):
        self._reconnect_delay = 0
        self._pikaconn_parameters = None
        self._defaultnodes=[]
        self._nodeslist=[]
        self._uid=''
        self._msgs_to_send = []
        self._first_init = True
        self._sending = False
        self._threadsend = None

        self._nodelevel = str(xargs)
        self._node_user=str(self._nodelevel+'_node')
        self._np=ii_helper('access.bin', 1+int(self._nodelevel[1]))
        self._dbp=ii_helper('access.bin', 12)
        self._IPU_path='/home/ip_updates.file'

        # Get Signature keys
        pubkey_path='node_pub.key'
        privkey_path='node_priv.key'
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
        self._PUBKEY=public_key
        self._PRIVKEY=private_key
        
        #Ensure existing log file
        LOGGER.info("Node has started\n")

    def run(self):        
        #node name read from uid
        if os.path.isfile(self.UID_PATH):
            with open(self.UID_PATH, 'r') as uid_file:
                self._uid=uid_file.read()
      
        #start the regular ticking
        self._ticking() # will init a ticking dameon

        #First initialisation of node
        self._initnode()
        self._consumer = NodeConsumer(self._pikaconn_parameters, self._nodelevel, self._node_consumer)
        
        # Start sending_msg thread on a separate connection
        self._threadsend = Thread(target=self._sending_msg)
        self._threadsend.start()
        
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
            LOGGER.info('Reconnecting after %d seconds', reconnect_delay)
            time.sleep(reconnect_delay)
            # Re-init node, redefine consumer and restart sending thread
            self._initnode()
            self._consumer = NodeConsumer(self._pikaconn_parameters, self._nodelevel, self._node_consumer)
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
        # Update connection parameters
        credentials = pika.PlainCredentials(self._node_user, self._np)
        self._pikaconn_parameters = pika.ConnectionParameters('localhost', self.PORT, self.VHOST, credentials,
                                                              heartbeat=10)

        # Ensure local queue exists
        connectiontemp = pika.BlockingConnection(self._pikaconn_parameters)
        channeltemp=connectiontemp.channel()
        qname='%s_own_queue' %self._nodelevel
        channeltemp.queue_declare(queue=qname, auto_delete=False)
        channeltemp.queue_bind(exchange=(self._nodelevel+'_main_exchange'), queue=qname, routing_key='all',
                       arguments={'x-match': 'any', 'dest': self._uid, 'dest_all': 'nodes'})


        # Create/Update public key on AnuuTechDB
        # Prepare connection to DB
        db_url='mongodb://admin:' + urllib.parse.quote(self._dbp) +'@localhost:27017/?authMechanism=DEFAULT&authSource=admin'
        db_client = pymongo.MongoClient(db_url)
        at_db = db_client["AnuuTechDB"]
        nodes_col = at_db["nodes"]
        # Prepare query in good format
        pem = self._PUBKEY.exportKey('PEM')
        db_query = { "uid": self._uid }
        db_values_toset = {"$set":{"pubkey": pem, "level": self._nodelevel, "last_view" : time.time()}}
        # Update/Insert values, using upsert = True
        nodes_col.update_one(db_query, db_values_toset, True)
        
        x=nodes_col.find_one({ "uid": self._uid })
        puk=RSA.importKey(x.get('pubkey'))
        if self._PUBKEY.exportKey('PEM') == puk.exportKey('PEM'):
            print('Verification of node pub key done!')
    
        try:
            connection.close()
            logmsg=("INITIALISATION Done with " + self._uid)
            LOGGER.info(logmsg)
        except:
            e = sys.exc_info()[1]
            logmsg=str('Problem while closing the queue creation connection: %s</p>' % e)
            LOGGER.warning(logmsg)

    def _ticking(self):
        if not self._first_init:
            logmsg=("PoH aggregation ticking for "+ self._uid)
            LOGGER.info(logmsg)
        self._first_init = False

        t = Timer(self.NODE_TICK_INTERVAL, self._ticking)
        t.daemon=True
        t.start()

    # Consumer method
    def _node_consumer(self, ch, method, properties, body):
        try:
            msg=json.loads(body.decode("utf-8"))
            LOGGER.info("Received decode: " + str(msg))
            msgback=msg
            hdrs=properties.headers
            LOGGER.debug(hdrs)
            
            if (hdrs.get('type')=='HMES'):
                #time.sleep(0.1)
                #Create fingerprint
                tt=time.time()
                hh=SHA256.new(msg['content'].encode())
                hh.update(msg['content_hash'].encode())
                hh.update(str(tt).encode())
                signer = PKCS115_SigScheme(self._PRIVKEY)
                fingerprint = signer.sign(hh)

                # Create transaction on AnuuTechDB
                # Prepare connection to DB
                db_url='mongodb://admin:' + urllib.parse.quote(self._dbp) +'@localhost:27017/?authMechanism=DEFAULT&authSource=admin'
                db_client = pymongo.MongoClient(db_url)
                at_db = db_client["AnuuTechDB"]
                tx_col = at_db["transactions_pending"]
                # Prepare query in good format
                db_query = { "uid": msg['uid'], "content": msg['content'], "content_hash": msg['content_hash'],
                             "timestamp": tt, "node_uid": self._uid, "fingerprint": fingerprint }
                # Insert value
                tx_col.insert_one(db_query)
                LOGGER.info("Tx sent to pending Txs on DB" +str(db_query))

                # Sends back to client
                hdrs['dest']=hdrs.get('sender')
                msgback['content']='Tx successfully added to pending Txs, fingerprint is in content_hash'
                msgback['content_hash']=binascii.hexlify(fingerprint).decode()
                LOGGER.info("HMES will send back "+str(msgback['uid'])+" " +str(hdrs))
                self._msgs_to_send.append([msgback, hdrs])
            elif (hdrs.get('type')=='IP_update'):
                IP_update={}
                # If already new IPs have been collected and not handled yet
                if os.path.isfile(self._IPU_path):
                    with open(self._IPU_path, 'r') as ip_file:
                        IP_update = json.load(ip_file)
                    # Add the new IP
                    IP_update[hdrs.get('sender')]=msg['content']
                # or file does not exist
                else:
                    IP_update[hdrs.get('sender')]=msg['content']
                # Write new file
                with open(self._IPU_path, 'w') as ip_file:
                        json.dump(IP_update, ip_file)
                LOGGER.info("New IP "+msg['content']+" saved for " +hdrs.get('sender'))
            else:
                LOGGER.error("ERROR: unknown message type" + hdrs.get('type'))
            return True
        except:
            e = sys.exc_info()[1]
            logmsg=("<p>WARNING! Unidentified error in Node_consumer, DEBUG!: %s</p>" % e )
            LOGGER.warning(logmsg)
            return False
            
    # Sender Method
    def _sending_msg(self):
        self._sending=True
        # creation of sending connection:
        try:
            sendingconn = pika.BlockingConnection(self._pikaconn_parameters)
            sendingchan = sendingconn.channel()
        except pika.exceptions.AMQPConnectionError as err:
            logmsg=str("Impossible to create sending connection!".format(err))
            LOGGER.critical(logmsg)
            return

        LOGGER.info("Starting sending_msg")
        
        while self._sending:
            try:
                if len(self._msgs_to_send)>0:
                    msg, hdrs =self._msgs_to_send.pop(0)
                    LOGGER.debug(str(msg))
                    LOGGER.debug(str(hdrs))
                    new_hdrs={}
                    # below is needed for Headers exchange to work correctly
                    if (hdrs.get('dest') != None):
                        new_hdrs['dest']=hdrs.get('dest')
                    if (hdrs.get('type') != None):
                        new_hdrs['type']=hdrs.get('type')
                    if (hdrs.get('sender') != None):
                        new_hdrs['sender']=hdrs.get('sender')
                    if (hdrs.get('dest_all') != None):
                        new_hdrs['dest_all']=hdrs.get('dest_all')
                         
                    # messages to reply queue
                    if self._nodelevel == 'L3':
                        if (hdrs.get('type') == 'getL3nodeslist' or hdrs.get('type') == 'HMES'):
                            #sends back to client
                            sendingchan.basic_publish(exchange='L3_main_exchange', routing_key='all',
                                              properties=pika.BasicProperties(
                                                  headers=new_hdrs), body=(json.dumps(msg)))
                    elif self._nodelevel == 'L2':
                        if (hdrs.get('type') == 'getL2nodeslisttoL3'):
                            #sends back to L3 initial sender TODO implement connection to L3
                            pass
##                            sendingchan.basic_publish(exchange='L3_main_exchange', routing_key='all',
##                                              properties=pika.BasicProperties(
##                                                  headers=new_hdrs), body=(json.dumps(msg)))
                        if (hdrs.get('type') == 'getL2nodeslisttoL1'):
                            pass
                            #sends back to L1 initial sender TODO implement connection to L1
##                            sendingchan.basic_publish(exchange='L1_main_exchange', routing_key='all',
##                                              properties=pika.BasicProperties(
##                                                  headers=new_hdrs), body=(json.dumps(msg)))
                    elif self._nodelevel == 'L1':
                        if (hdrs.get('type') == 'getL1nodeslisttoL2'):
                            pass
                            #sends back to L3 initial sender TODO implement connection to L2
##                            sendingchan.basic_publish(exchange='L2_main_exchange', routing_key='all',
##                                              properties=pika.BasicProperties(
##                                                  headers=new_hdrs), body=(json.dumps(msg)))

                    LOGGER.info(str("msg sent to reply queue: " + hdrs.get('type')))
                else:
                    sendingconn.sleep(0.1) # ensure heartbeat
            except:
                e = sys.exc_info()[1]
                logmsg=str("<p>Problem while sending, trying to reinit connections...: %s</p>" % e )
                LOGGER.error(logmsg)
                try:
                    try:
                        sendingconn.close() #try to reinit
                    except:
                        pass
                    time.sleep(5)
                    self._sending_msg()
                except:
                    LOGGER.critical('Problem while sending and impossible to stop consuming')
                break
            
        # Closing connection (stopped manually)
        if not self._sending:
            try:
                sendingconn.close()
            except:
                e = sys.exc_info()[1]
                logmsg=str('Problem while closing send connection: %s</p>' % e)
                LOGGER.warning(logmsg)

#-----------------------------    
def main():
    hdlr = logging.StreamHandler()
    fhdlr = logging.FileHandler("log_poh_agg.txt", mode='w')
    format = logging.Formatter('%(asctime)-15s %(levelname)s : %(message)s')
    fhdlr.setFormatter(format)
    hdlr.setFormatter(format)
    LOGGER.addHandler(hdlr)
    LOGGER.addHandler(fhdlr)
    LOGGER.setLevel(logging.DEBUG)
    
    # Check arguments
    if len(sys.argv) == 2:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            nodelevel=sys.argv[1]
            consumer = ReconnectingNodeConsumer(nodelevel)
            consumer.run()   
    else:
        print("Script needs 1 parameter (L1, L2, L3, clean or update). Please retry.")
        exit()


if __name__ == '__main__':
    main()
