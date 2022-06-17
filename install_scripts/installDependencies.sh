#!/bin/bash
## Installation script for AnuuTech LX node: ERLANG + RABBITMQ + MONGODB
cd /home

## CHECK ARGUMENTS FOR DEFINING IF MONGODB HAS TO BE INSTALLED
if [ "$1" = 'mongo' ]; then
    mongo=1
else
	mongo=0
fi
	
## GET PRE-REQUISITES AND REPOSITORIES
apt-get install curl gnupg apt-transport-https -y

## Team RabbitMQ's main signing key
curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" | gpg --dearmor | tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null
## Cloudsmith: modern Erlang repository
curl -1sLf https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/gpg.E495BB49CC4BBE5B.key | gpg --dearmor | tee /usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg > /dev/null
## Cloudsmith: RabbitMQ repository
curl -1sLf https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/gpg.9F4587F226208342.key | gpg --dearmor | tee /usr/share/keyrings/io.cloudsmith.rabbitmq.9F4587F226208342.gpg > /dev/null

## Add apt repositories maintained by Team RabbitMQ
rm /etc/apt/sources.list.d/rabbitmq.list
tee /etc/apt/sources.list.d/rabbitmq.list <<EOF
## Provides modern Erlang/OTP releases
##
deb [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/deb/debian buster main
deb-src [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.E495BB49CC4BBE5B.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/deb/debian buster main

## Provides RabbitMQ
##
deb [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.9F4587F226208342.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/deb/debian buster main
deb-src [signed-by=/usr/share/keyrings/io.cloudsmith.rabbitmq.9F4587F226208342.gpg] https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-server/deb/debian buster main

EOF

## Specify version for erlang
rm /etc/apt/preferences.d/erlang
cat >>/etc/apt/preferences.d/erlang <<EOF
Package: erlang* esl-erlang
Pin: version 1:24.3*
Pin-Priority: 501
EOF

## Add Mongo repository
echo "deb http://repo.mongodb.org/apt/debian buster/mongodb-org/5.0 main" | sudo tee /etc/apt/sources.list.d/mongodb-org-5.0.list

curl -sSL https://www.mongodb.org/static/pgp/server-5.0.asc  -o mongoserver.asc
gpg --no-default-keyring --keyring ./mongo_key_temp.gpg --import ./mongoserver.asc
gpg --no-default-keyring --keyring ./mongo_key_temp.gpg --export > ./mongoserver_key.gpg
sudo mv mongoserver_key.gpg /etc/apt/trusted.gpg.d/

## Update package indices
apt-get update -y


## INSTALL FIREWALL AND OPEN NEEDED PORTS
## (see https://www.rabbitmq.com/networking.html) TO REVIEW!
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


## INSTALL ERLANG PACKAGES
# apt-get install -y erlang-base \
                        # erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
                        # erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
                        # erlang-runtime-tools erlang-snmp erlang-ssl \
                        # erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl	
apt-get install esl-erlang


## INSTALL RABBITMQ_SERVER and its dependencies
apt-get install rabbitmq-server -y --fix-missing

## Enable the management plugin
rabbitmq-plugins enable rabbitmq_management


## INSTALL PYTHON DEPENDENCIES
apt -y install python3-pip
pip3 install pika
pip3 install requests
pip3 install pycryptodome
pip3 install pymongo
pip3 install psutil
pip3 install filelock


## INSTALL MONGODB V5
if $mongo == 0; then
	exit
fi
apt -y install mongodb-org

## Install service and give it some time to start
systemctl enable --now mongod
sleep 5

## Debug
## systemctl status mongod
## mongod --version

## Create JS file for adding user and rights NOT NEEDED
key=$((python3 ii_helper.py node_data/access.bin 11) 2>&1)
key2=$((python3 ii_helper.py node_data/access.bin 12) 2>&1)
rm installMongoScript.js
cat >>installMongoScript.js <<EOF
db.getSiblingDB("admin").createUser(
  {
    user: "admin",
    pwd: "$key", // or cleartext password
    roles: [ { role: "userAdminAnyDatabase", db: "admin" }, "readWriteAnyDatabase" ]
  }
)
db.getSiblingDB("admin").createUser(
  {
    user: "explorer",
    pwd: "$key2", // or cleartext password
    roles: [{role:"read", db: "AnuuTech_DB"}]
  }
)

EOF
mongo installMongoScript.js

# ## Create mongo security directory and move keyfile
# mkdir mongo-security
# mv node_data/keyfile.txt mongo-security/

# ## Change file permissions and owner
# cd mongo-security
# chmod 400 keyfile.txt
# chown mongodb:mongodb keyfile.txt

## Overwrite mongo config file
own_ip=$(curl -s https://api.ipify.org) # get own external IP
rm /etc/mongod.conf
cat >>/etc/mongod.conf <<EOF
# for documentation of all options, see:
#   http://docs.mongodb.org/manual/reference/configuration-options/

# Where and how to store data.
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

# where to write logging data.
systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

# network interfaces
net:
  port: 28991
  bindIp: 127.0.0.1, $own_ip

# how the process runs
processManagement:
  timeZoneInfo: /usr/share/zoneinfo

security:
  authorization: enabled

EOF

## Open firewall
ufw allow 28991

## Restart service and ready
systemctl restart mongod
sleep 5
systemctl status mongod