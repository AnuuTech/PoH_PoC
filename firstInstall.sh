#!/bin/bash
## FIRST installation script for AnuuTech LX node
cd /home

## CHECK ARGUMENTS FOR DEFINING NODE LEVEL
if [ "$1" = 'L1' ] || [ "$1" = 'L2' ] || [ "$1" = 'L3' ]; then
    nodelevel=$1
else
    echo "Missing Node level argument (L1, L2 or L3), exiting..."
	exit
fi
echo $nodelevel


## INSTALL DEPENDENCIES (ERLANG+RABBITMQ+ optionally MONGODB)
chmod +x install_scripts/installDependencies.sh
if [ "$3" = '1' ]; then
	./install_scripts/installDependencies.sh 'mongo'
else 
	./install_scripts/installDependencies.sh 
fi


## INIT NODE 
chmod +x install_scripts/initNode.sh
./install_scripts/initNode.sh $nodelevel


## PREPARE AND START PYTHON SERVICES
python3 node_services/prepare_services.py $nodelevel $2 $3 $4 $5
chmod +x start_node.sh
chmod +x stop_node.sh


## LAUNCH
./start_node.sh