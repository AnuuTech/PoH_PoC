## AnuuTech Proof-Of-Hash ##

Initial network solution using RabbitMQ.


### CLIENT SIDE / TESTING THE NETWORK
You can test the network using the client_emulator.py python application.
1. Type "Python3 client_emulator.py" in a command line where the file is present
2. Select one cluster node
3. Click "Connect"
4. Choose the number of messages per second to send (1 to 100).
5. Click "Send msg"
6. Check on the command window that messages are correctly received back.
7. Then click "Stop Sending"
8. Click "Disconnect"
9. Click "QUIT"


### SERVER SIDE / ADDING A NODE TO THE NETWORK
To launch a Cluster node on a debian 10 or 11 machine:
1. Put cluster_node.py and installCluster.sh in /home directory
2. In /home directory, type "chmod +x installCluster.sh" 
3. Type "./installCluster.sh LX" to launch the installation process and the automatic launch.

LX should be L1, L2 or L3 depending on the cluster layer we want to join.

###### NOTE: The node initially creating the cluster should be launched using "initLX" instead of "LX".

You can check the python output log by typing "tail -f output.log", CTRL-C will end the output reading.

You can check the rabbitmq output by typing "tail -f /var/log/rabbitmq/at-node\@--IPADDRESS--.log"

##### Basic debugging:

Start/Stop Python:
- To stop the python application: "./stop_layer.sh"
- To restart the python application: "./start_layer.sh"

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


