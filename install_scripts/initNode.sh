#!/bin/bash
## Installation script for AnuuTech LX node: Basic (re-)initialization
cd /home
mkdir logs/
rm node_data/*.file

## CHECK ARGUMENTS FOR DEFINING NODE LEVEL
if [ "$1" = 'L1' ] || [ "$1" = 'L2' ] || [ "$1" = 'L3' ]; then
    nodelevel=$1
else
    echo "Missing Node level argument (L1, L2 or L3), exiting..."
	exit
fi
echo $nodelevel

## Create and save a unique name id 
aa=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 6 | head -n 1)
nodename=$nodelevel"Node_${aa}"
echo $nodename > node_data/node_uid.file

## Create and save a local password 
< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c 12 >node_data/ps_loc.file
puid=$( cat node_data/ps_loc.file )
psloc="pass_"$puid

## Get own_ip
own_ip=$(curl -s https://api.ipify.org)
echo $own_ip

## Define node name containing own IP in env conf file
rm /etc/rabbitmq/rabbitmq-env.conf
mkdir /etc/rabbitmq # ensure it exists
cat >>/etc/rabbitmq/rabbitmq-env.conf <<EOF
RABBITMQ_USE_LONGNAME=true
RABBITMQ_NODENAME=$nodename@$own_ip
EOF
service rabbitmq-server restart

## Reset RabbitMQ
rabbitmqctl stop_app
rabbitmqctl reset
rabbitmqctl start_app

## Configure RabbitMQ

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

