## AnuuTech Proof-Of-Hash ##
Initial network solution using RabbitMQ as message protocol.


### CLIENT SIDE / TESTING THE NETWORK FEATURES
You can test the different features of the network using the client_basic.py python application.
1. Type "Python3 client_basic.py" in a command line where the file is present
3. Select the message type you want to test, the node to connect to and then click "Connect"
4. For the Chat feature, click "Send msg", to send a broadcast message
6. Alternatively fill the AnuuChat recipient field with the unique identifier of another client to send an encrypted private message
8. For PoH, click send msg and wait for a confirmation message
9. For Data Storage, select a file to store in the network, click connect and then "Send msg"
10. To retrieve a file, fill in with a hash that has been stored and clicking "Send msg" will retrieve the file with the corresponding hash.
12. Click "Disconnect" and then "QUIT"


### CLIENT SIDE / STRESS TESTING
You can stress test the network using the client_stresstest.py python application.
1. Type "Python3 client_stresstest.py" in a command line where the file is present
2. Select one node
3. Click "Connect"
4. Choose the number of messages per second to send (1 to 100).
5. Select CHAT or PoH depending on what to test
6. Click "Send msg", it will start continuously sending messages
7. Check on the command window that messages are correctly received back.
8. Then click "Stop Sending"
9. Click "Disconnect"
10. Click "QUIT"


### SERVER SIDE / ADDING A NODE TO THE NETWORK
To launch a node on a debian 10 or 11 machine:
1. Copy the files from Github in the /home directory
2. In /home directory, type "chmod +x firstInstall.sh" 
3. Type "./firstInstall.sh LX CHAT NET_SERV POH DATA_STOR" to launch the installation process and the automatic launch.

LX should be L1, L2 or L3 depending on the network layer you want to join.

CHAT NET_SRV POH and DATA_STOR can be used to optionnally set which services the node will offer (1 to offer, 0 otherwise).

For example, "./firstInstall.sh L3 1 0 0 0" will install a L3 node with only the chat service running.

You can check the python output log by typing "tail -f logs/log_SERVICENAME.log", CTRL-C will end the output reading.

You can check the rabbitmq output by typing "tail -f /var/log/rabbitmq/at-node\@--IPADDRESS--.log"

##### Basic debugging:

Start/Stop Python:
- To stop all python services: "./stop_node.sh"
- To restart all python services: "./start_node.sh"

To debug RabbitMQ (self-explanatory):
- rabbitmqctl status
- rabbitmqctl stop_app
- rabbitmqctl reset
- rabbitmqctl start_app


If issue is worse then stopping the service may be needed:
- service rabbitmq-server stop
- service rabbitmq-server start


### CHANGELOG
The changelog is visible in [releases](https://github.com/AnuuTech/PoH_PoC/releases)


