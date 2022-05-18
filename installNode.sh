#!/bin/bash
## Installation script for AnuuTech LX node
#hostnamectl set-hostname at-clusternode1
cd /home

## CHECK ARGUMENTS FOR DEFINING NODE LEVEL
if [ "$1" = 'L1' ] || [ "$1" = 'L2' ] || [ "$1" = 'L3' ]; then
    nodelevel=$1
else
    echo "Missing Node level argument (L1, L2 or L3), exiting..."
	exit
fi
echo $nodelevel

## Create and save a unique name id 
if [ ! -s node_data/node_uid.file ]
then
	aa=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 6 | head -n 1)
	nodename=$nodelevel"Node_${aa}"
	echo $nodename > node_data/node_uid.file
fi
nodename=$( cat node_data/node_uid.file )

## Create and save a local password 
if [ ! -s node_data/ps_loc.file ]
then
	< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c 12 >node_data/ps_loc.file
fi
puid=$( cat node_data/ps_loc.file )
psloc="pass_"$puid

## Get own_ip
own_ip=$(curl -s https://api.ipify.org)
echo $own_ip

## Open the needed ports (see https://www.rabbitmq.com/networking.html) TO REVIEW!
apt-get install ufw
ufw allow ssh
ufw allow 4369
ufw allow 5672
ufw allow 15672
ufw allow 25672
ufw allow 5551
ufw allow 5552
ufw allow 35672:35682/tcp
yes | ufw enable 

## CLEAN INSTALLATION OF RABBITMQ
## Install prerequisites
apt-get install curl gnupg apt-transport-https -y

## Team RabbitMQ's main signing key
curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" | gpg --dearmor | tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null
## Cloudsmith: modern Erlang repository
curl -1sLf https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/gpg.E495BB49CC4BBE5B.key | gpg --dearmor | tee /usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg > /dev/null
## Cloudsmith: RabbitMQ repository
curl -1sLf https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/gpg.9F4587F226208342.key | gpg --dearmor | tee /usr/share/keyrings/io.cloudsmith.rabbitmq.9F4587F226208342.gpg > /dev/null

## Add apt repositories maintained by Team RabbitMQ
tee /etc/apt/sources.list.d/rabbitmq.list <<EOF
## Provides modern Erlang/OTP releases
##
deb [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/deb/ubuntu bionic main
deb-src [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/deb/ubuntu bionic main

## Provides RabbitMQ
##
deb [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.9F4587F226208342.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/deb/ubuntu bionic main
deb-src [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.9F4587F226208342.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/deb/ubuntu bionic main

EOF

## Update package indices
apt-get update -y

## Install python dependencies
apt -y install python3-pip
pip3 install pika
pip3 install requests
pip3 install pycryptodome
pip3 install pymongo
pip3 install psutil

## Install Erlang packages
apt-get install -y erlang-base \
                        erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
                        erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
                        erlang-runtime-tools erlang-snmp erlang-ssl \
                        erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl	


## Define node name containing own IP in env conf file
rm /etc/rabbitmq/rabbitmq-env.conf
mkdir /etc/rabbitmq # ensure it exists
cat >>/etc/rabbitmq/rabbitmq-env.conf <<EOF
RABBITMQ_USE_LONGNAME=true
RABBITMQ_NODENAME=$nodename@$own_ip
EOF
	
## Install rabbitmq-server and its dependencies
apt-get install rabbitmq-server -y --fix-missing

## Enable the management plugin
rabbitmq-plugins enable rabbitmq_management

## CONFIGURATION OF THE NODE

#config new dedicated vhost
rabbitmqctl add_vhost anuutech

#right="client_"
#config users TODO remove rbMN?
key=$((python3 ii_helper.py node_data/access.bin 0) 2>&1)
rabbitmqctl add_user rbMN $key
rabbitmqctl set_user_tags rbMN administrator
#local user
rabbitmqctl add_user layer_local $psloc
unset psloc
nodeperm=$nodelevel"_*"
rabbitmqctl set_permissions -p "anuutech" layer_local $nodeperm $nodeperm $nodeperm
rabbitmqctl delete_user 'guest'
#FOR LEVEL 1
if [ $nodelevel == 'L1' ]; then
	#L1ext_nodeext node
	key=$((python3 ii_helper.py node_data/access.bin 5) 2>&1)
	rabbitmqctl add_user L1ext_node $key
	rabbitmqctl set_permissions -p "anuutech" L1ext_node "" "L1_main_exchange" "L1_main_exchange"
fi
#FOR LEVEL 2
if [ $nodelevel == 'L2' ]; then
	#L2ext node
	key=$((python3 ii_helper.py node_data/access.bin 6) 2>&1)
	rabbitmqctl add_user L2ext_node $key
	rabbitmqctl set_permissions -p "anuutech" L2ext_node "" "L2_main_exchange" "L2_main_exchange"
fi
#FOR LEVEL 3
if [ $nodelevel == 'L3' ]; then
	#client user
	key=$((python3 ii_helper.py node_data/access.bin 1) 2>&1)
	rabbitmqctl add_user client_user $key
	rabbitmqctl set_permissions -p "anuutech" client_user "client_*" "L3_main_exchange|client_*" "L3_main_exchange|client_*"
	#L3ext node
	key=$((python3 ii_helper.py node_data/access.bin 7) 2>&1)
	rabbitmqctl add_user L3ext_node $key
	rabbitmqctl set_permissions -p "anuutech" L3ext_node "" "L3_main_exchange" "L3_main_exchange"
fi
unset key

## PREPARE AND START PYTHON SERVICES
mkdir /home/logs/
python3 node_services/prepare_services.py $nodelevel
chmod +x start_node.sh
chmod +x stop_node.sh

## Launch python program
./start_node.sh