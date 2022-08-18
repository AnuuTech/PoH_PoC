from web3 import Web3
from web3.middleware import geth_poa_middleware

w3= Web3(Web3.HTTPProvider('http://xx:xx'))

w3.middleware_onion.inject(geth_poa_middleware, layer=0)

w3.eth.getBlock(363786)

abi=[
	{
		"inputs": [],
		"stateMutability": "payable",
		"type": "constructor"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "dest",
				"type": "address"
			},
			{
				"internalType": "string",
				"name": "tx_hash",
				"type": "string"
			}
		],
		"name": "callTransfer",
		"outputs": [],
		"stateMutability": "payable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "dest",
				"type": "address"
			}
		],
		"name": "payments",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address payable",
				"name": "payee",
				"type": "address"
			}
		],
		"name": "withdrawPayments",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	}
]

caddr='[CONTRACT NUMBER]'

tx=w3.eth.getTransactionByBlock(363786,0)
contract = w3.eth.contract(address=caddr, abi=abi)

a=contract.decode_function_input(tx.input)
print(w3.toText(a[1]['tx_hash']))

