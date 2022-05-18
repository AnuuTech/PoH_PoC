## AnuuTech Proof-Of-Hash ##
Initial network solution using RabbitMQ.


### CLIENT SIDE / TESTING THE NETWORK FEATURES
You can test the different features of the network using the client_basic.py python application.
1. Type "Python3 client_basic.py" in a command line where the file is present
2. Wait until a list of nodes is collected from the network (up to 20 seconds)
3. Select a node and the Chat message type, then click "Connect"
4. Edit your name and the AnuuChat message to send and click "Send msg", it will send one message.
5. Check that the message is correctly received back.
6. Alternatively edit the AnuuChat recipient with the unique identifier of another client.
7. Click "Send msg" and checks that recipient received the decrypted message.
8. For PoH, select a node and click send msg. A message back should confirm the success of the operation.
9. For Data Storage, select a file to store in the network, click connect and then "Send msg"
10. Check that the file has been successfully been stored, with the hash displayed below the "Select file" button.
11. You can click on "Send msg" again, and the network will retrieve the file with the corresponding hash.
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
2. In /home directory, type "chmod +x installNode.sh" 
3. Type "./installNode.sh LX" to launch the installation process and the automatic launch.

LX should be L1, L2 or L3 depending on the network layer we want to join.

You can check the python output log by typing "tail -f logs/output_SERVICENAME.log", CTRL-C will end the output reading.

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


