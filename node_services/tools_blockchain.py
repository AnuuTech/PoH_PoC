#import class_service
import settings as S
import sys
import os
import json
from Crypto.Signature.pkcs1_15 import PKCS115_SigScheme
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
import binascii
import time
from collections import Counter
from filelock import FileLock
import urllib
import pymongo
import copy

def ii_helper(fily, sel):
    abc = b'k_AnuuTech'
    abcl = len(abc)
    with open(fily, 'rb') as s_file:
        brezl=s_file.readlines()
    brez=brezl[int(sel)].replace(b'\n',b'')
    brezi=bytes(c ^ abc[i % abcl] for i, c in enumerate(brez)).decode()
    return (brezi)

def full_BC_verif(filename):
    poh_blocks=[]
    block={}
    listofblocks_str = next(os.walk(S.NET_STORAGE_PATH), (None, None, []))[2]
    print(str(len(listofblocks_str)))
    
    #Load blockchain from L1 <-- !! file should be manually put in L2 !!
    if os.path.isfile(filename):
        with open(filename, 'r') as b_file:
            poh_blocks=json.load(b_file)

    #Go through all blocks
    for j in range(0,len(poh_blocks)):
        print(poh_blocks[j][0]) # height
        if str(poh_blocks[j][1]) not in listofblocks_str:
            print("block "+str(poh_blocks[j][1])+" is missing")
            break
        else:
            with FileLock(S.NET_STORAGE_PATH+str(poh_blocks[j][1])+'.lock', timeout=1):
                with open(S.NET_STORAGE_PATH+str(poh_blocks[j][1]), 'r') as filedata:
                    block=json.load(filedata)
            print(block['height']) # height
            #check corespondinging values
            if j != 0:
                if block['previous_hash'] != poh_blocks[j-1][1]: # hash
                    print(str(j)+": Previous hash not matching: "+str(block['current_hash'])+ ' vs '+str(poh_blocks[j-1][1]))
                    break
                if block['height'] != poh_blocks[j][0]: # height
                    print(str(j)+": Height not matching : "+str(block['height'])+ ' vs '+str(poh_blocks[j][0]))
                    break
                if block['epoch'] != poh_blocks[j][2]: # epoch
                    print(str(j)+": Epoch not matching: "+str(block['epoch'])+ ' vs '+str(poh_blocks[j][2]))
                    break

def verif_L1BC():
    poh_blocks=[]
    #Load blockchain
    if os.path.isfile(S.POH_BLOCKS_PATH):
        with open(S.POH_BLOCKS_PATH, 'r') as b_file:
            poh_blocks=json.load(b_file)
    for j in range(0,len(poh_blocks)-1):
        # check height
        if(poh_blocks[j+1][0]!=poh_blocks[j][0]+1):
            print('Height error at ' +str(j)+ ' '+str(poh_blocks[j+1][0]) +' vs '+ str(poh_blocks[j][0]))
        # check epoch
        if(poh_blocks[j+1][2]<=poh_blocks[j][2]):
            print('Epoch error at ' +str(j)+ ' '+str(poh_blocks[j+1][2]) +' vs '+ str(poh_blocks[j][2]))
        # check hash
        if(poh_blocks[j+1][1]==poh_blocks[j][1]):
            print('oups!')
    print('finished!')

def verif_L2blocks(inp, push, IP_sel, nb_max_block):
    block1={}
    block2={}
    all_blocks=[]
    bc_ok=True
    c_hash=inp
    listofblocks_str = next(os.walk(S.NET_STORAGE_PATH), (None, None, []))[2]
    print(str(len(listofblocks_str)))
    nb_block=0
    while (nb_block < int(nb_max_block) and c_hash != '00f1bd32b41a160291e28b79276d2db53f943795451f74be4cdba56cd3ca1170'): #block 1 Hash
        block1=copy.deepcopy(block2)
        if str(c_hash) not in listofblocks_str:
            print("block "+str(c_hash)+" is missing")
            bc_ok=False
            break
        else:
            with FileLock(S.NET_STORAGE_PATH+str(c_hash)+'.lock', timeout=1):
                with open(S.NET_STORAGE_PATH+str(c_hash), 'r') as filedata:
                    block2=json.load(filedata)
            #print(block2['height'])
            #check signature
            if check_block(block2):
                if len(block1) != 0:
                    #check coresponding Hash
                    if block1['previous_hash'] != block2['current_hash']:
                        print(str(c_hash)+": Hash not matching: "+str(block2['current_hash'])+ ' vs '+str(block1['previous_hash']))
                        bc_ok=False
                        break
                    #check height
                    if block1['height'] != block2['height']+1:
                        print(str(c_hash)+": Height not increased by 1: "+str(block2['height'])+ ' vs '+str(block1['height']))
                        bc_ok=False
                        break
                    #check epoch
                    if block1['epoch'] <= block2['epoch']: # this would be wrong!
                        print(str(c_hash)+": Epoch not increasing: "+str(block2['epoch'])+ ' vs '+str(block1['epoch']))
                        bc_ok=False
                        break
                c_hash=block2['previous_hash']
                if push:
                    all_blocks.append(block2)
            else:
                print(str(c_hash)+": Block invalid!")
                bc_ok=False
                break
        nb_block=nb_block+1
    if bc_ok:
        print("All blocks verified!")
        if push:
            updatingDB(IP_sel, all_blocks)
    else:
        print("Chain of blocks not complete or invalid...")
        
                         
def check_block(block):
    # Verify Hash is correct
    hh=SHA256.new(block['previous_hash'].encode())# put previous block hash
    hh.update(str(block['epoch']).encode()) # put epoch
    # order all txs by timestamps TODO check if txs have not already been included in a previous block?
    txs_ord=sorted(block['transactions'], key=lambda t: t['timestamp'])
    for tx in txs_ord:
        hh.update(tx['fingerprintL1'].encode())#put each tx L1 fingerprint
    return (binascii.hexlify(hh.digest()).decode() == block['current_hash'])#compute final hash
            
def L1_blocks_removal(height):
    poh_blocks=[]
    # load small blockchain
    if os.path.isfile(S.POH_BLOCKS_PATH):
        with open(S.POH_BLOCKS_PATH, 'r') as b_file:
            poh_blocks=json.load(b_file)
    # remove blocks
    for j in range(0,len(poh_blocks)):
        # check height
        while (poh_blocks[-1][0]>int(height)):
            a=poh_blocks.pop()
            print("Height removed "+str(a[0]))

    print(str(len(poh_blocks)))

    # save the blocks on disk
    if 0==0:
        with open(S.POH_BLOCKS_PATH, 'w') as b_file:
            b_file.write(json.dumps(poh_blocks))

def reconfigure_blocks():
    poh_blocks=[]
    block1={}
    block2={}
    listofblocks_str = next(os.walk(S.NET_STORAGE_PATH), (None, None, []))[2]
    print(str(len(listofblocks_str)))
    allnbs=list(range(0,6370))
    for b in allnbs:
        #block1=copy.deepcopy(block2)
        if str(b) not in listofblocks_str:
            print("block "+str(b)+" is missing")
        else:
            try:
                with FileLock(S.NET_STORAGE_PATH+str(b)+'.lock', timeout=1):
                    with open(S.NET_STORAGE_PATH+str(b), 'r') as filedata:
                        block=json.load(filedata)
                # Save file locally using current hash as filename
                data_path=S.NET_STORAGE_PATH+str(block['current_hash'])
                with FileLock(data_path+'.lock', timeout=1):
                    with open(data_path, 'w') as data_file:
                        data_file.write(json.dumps(block))
                print(str(b)+": Block saved")
                
            except:
                e = sys.exc_info()[1]
                print(str(b)+": Block empty or incomplete: " + str(e))
                break

def updatingDB(IP_sel, blocks_list):
    db_pass=ii_helper('node_data/access.bin', '11')
    height_list=[el['height'] for el in blocks_list]
    # update data to DB
    db_url='mongodb://admin:' + urllib.parse.quote(db_pass) +'@'+IP_sel+':28991/?authMechanism=DEFAULT&authSource=admin'
    with pymongo.MongoClient(db_url) as db_client:
        at_db = db_client['AnuuTech_DB']
        col = at_db['blocks']
        col.delete_many({'height':{'$in':height_list}})
        col.insert_many(blocks_list)
        print(str(len(blocks_list))+" block(s) written on DB "+str(IP_sel))

#----------------------------------------------------------------
def main():

    # Check arguments
    if len(sys.argv) == 2 :
        tool=sys.argv[1]
        if tool == 'verifL1':
            verif_L1BC()
        elif tool == 'reconfL2':
            reconfigure_blocks()
    if len(sys.argv) == 3 :
        tool=sys.argv[1]
        arg=sys.argv[2]
        if tool == 'verifL2':
            verif_L2blocks(arg, False, '', 1000000)
        elif tool == 'removalL1':
            L1_blocks_removal(arg)
        elif tool == 'fullverif':
            full_BC_verif(arg)
    if len(sys.argv) == 5 :
        tool=sys.argv[1]
        arg=sys.argv[2]
        arg2=sys.argv[3]
        arg3=sys.argv[4]
        if tool == 'pushonDBL2':
            verif_L2blocks(arg, True, arg2, arg3)
        
        
if __name__ == '__main__':
    main()
