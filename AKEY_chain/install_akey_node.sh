#!/bin/bash
## Installation script for AKEY private PoA blockchain based on BESU client

## GET BESU SW
apt-get update 
apt-get install openjdk-11-jdk

wget https://hyperledger.jfrog.io/artifactory/besu-binaries/besu/22.4.4/besu-22.4.4.tar.gz

tar -xvzf besu-22.4.4.tar.gz
mv besu-22.4.4 besu

# update PATH
echo 'export PATH=/home/besu/bin:$PATH' >> ~/.bashrc
source ~/.bashrc


## CREATE NEEDED DIRS AND CONFIG FILE
cd /home
mkdir QBFT
cd QBFT
mkdir node1
cd node1
mkdir data

own_addr=$((python3 ii_helper.py node_data/access.bin 13) 2>&1)
chainID=$((python3 ii_helper.py node_data/access.bin 14) 2>&1)

cat >>/home/QBFT/qbftConfigFile.json <<EOF
{
 "genesis": {
   "config": {
      "chainId": $chainID,
     "londonBlock": 0,
      "qbft": {
        "blockperiodseconds": 5,
        "epochlength": 21600,
        "requesttimeoutseconds": 10
      }
    },
    "nonce": "0x0",
    "timestamp": "0x0",
    "gasLimit": "0x1fffffffffffff",
    "difficulty": "0x1",
    "mixHash": "0x63746963616c2062797a1974a4696e65206661756c7420746f6c6572616e6365",
    "coinbase": "0x0000000000000000000000000000000000000000",
    "alloc": {
       "$own_addr": {
        "balance": "1000000000000000000000000000"
       }
      }
 },
 "blockchain": {
   "nodes": {
     "generate": true,
       "count": 1
   }
 }
}
EOF


## CRATE GENESIS FILE
cd /home/QBFT
besu operator generate-blockchain-config --config-file=qbftConfigFile.json --to=networkFiles --private-key-file-name=key

cp networkFiles/genesis.json /home/QBFT
cp networkfiles/keys/0x*/* /home/QBFT/node1/data 


## START THE BOOTNODE
cd node1
rh_port=$((python3 ii_helper.py node_data/access.bin 15) 2>&1)
p2p_port=$((python3 ii_helper.py node_data/access.bin 16) 2>&1)
bootnodes=$((python3 ii_helper.py node_data/access.bin 17) 2>&1)

nohup besu --data-path=data --genesis-file=../genesis.json --rpc-http-enabled --rpc-http-api=ETH,NET,QBFT,WEB3 --rpc-http-port=$rh_port --p2p-port=$p2p_port &
ufw allow p2p_port

exit

# Command to start a node offering RPC service to the outside (on L3)
nohup besu --data-path=data --genesis-file=../genesis.json --bootnodes=enode://$bootnodes --p2p-port=$p2p_port --rpc-http-enabled --rpc-http-api=ETH,NET,WEB3 --host-allowlist="*" --rpc-http-cors-origins="all" --rpc-http-port=$rh_port --rpc-http-host=0.0.0.0 --logging=DEBUG &

ufw allow $rh_port

# Command to start a node a block explorer service running directly on L3 (using local com with RPC)
nohup besu --data-path=data --genesis-file=../genesis.json --bootnodes=enode://$bootnodes --p2p-port=$p2p_port --rpc-http-enabled --rpc-http-api=ETH,NET,WEB3 --rpc-http-port=$rh_port &

# Command to start a standard node on L1/L2
nohup besu --data-path=data --genesis-file=../genesis.json --bootnodes=enode://$bootnodes --p2p-port=$p2p_port --rpc-http-enabled --rpc-http-api=ETH,NET,WEB3,QBFT --rpc-http-port=$rh_port &


## Additional commands
# To add a validator (should be run by a majority of validators):
curl -X POST --data '{"jsonrpc":"2.0","method":"qbft_proposeValidatorVote","params":["0x5b291303c1021f20cc9aa55826aa4c9ef948112c",true], "id":1}' http://127.0.0.1:$rh_port
# To check current validator votes:
curl -X POST --data '{"jsonrpc":"2.0","method":"qbft_getPendingVotes","params":[], "id":1}' http://127.0.0.1:$rh_port
# To check current validator lists:
curl -X POST --data '{"jsonrpc":"2.0","method":"qbft_getValidatorsByBlockNumber","params":["latest"], "id":1}' http://127.0.0.1:$rh_port
# To check balance of an address:
curl -X POST --data '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x5b291303c1021f20cc9aa55826aa4c9ef948112c", "latest"],"id":1}' localhost:$rh_port
