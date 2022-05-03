import sys
abc = b'k_AnuuTech'
abcl = len(abc)
if (str.isdigit(sys.argv[2])):
    with open(sys.argv[1], 'rb') as s_file:
        brezl=s_file.readlines()
    brez=brezl[int(sys.argv[2])].replace(b'\n',b'')
    brezi=bytes(c ^ abc[i % abcl] for i, c in enumerate(brez)).decode()
    print(brezi)


    
