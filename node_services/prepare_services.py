import settings as S
import os
import json
import sys

# Check list of services configured
LAUNCHER_PATH='start_node.sh'
STOPPER_PATH='stop_node.sh'

def startingdef(nodelevel):
    serv_list={}
    if os.path.isfile(S.SERVICES_PATH):
        with open(S.SERVICES_PATH, 'r') as serv_file:
            serv_list=json.load(serv_file)
    else:
        #default config, net_maintenance is mandatory
        serv_list={'net_maintenance': 1, 'chat': 0, 'net_storage': 0,
                   'poh': 0, 'data_storage': 0}
        with open(S.SERVICES_PATH, 'w') as serv_file:
                serv_file.write(json.dumps(serv_list))
    print("List of services configured: " + str(serv_list))
    prepare(nodelevel, serv_list)

def starting(nodelevel,s1, s2, s3, s4):
    #apply config
    serv_list={'net_maintenance': 1, 'chat': int(s1), 'net_storage': int(s2),
               'poh': int(s3), 'data_storage': int(s4)}
    with open(S.SERVICES_PATH, 'w') as serv_file:
        serv_file.write(json.dumps(serv_list))
    print("List of services configured: " + str(serv_list))
    prepare(nodelevel, serv_list)
    
def prepare(nodelevel, serv_list):
    # Prepare launcher
    with open(LAUNCHER_PATH, 'w') as lau_file:
        line='rm '+S.IP_PATH+'\n' # to ensure that python processes wait until network maintenance service is ready
        lau_file.write(line)
        for serv in serv_list.keys():
            if serv_list[serv] == 1:
                line='nohup python3 -u node_services/service_'+serv+'.py '+nodelevel+' &>/home/logs/output_'+serv+'.log </dev/null &\n'
                lau_file.write(line)
                line='echo $! > node_services/python_pid_'+serv+'.file\n'
                lau_file.write(line)
                if serv=='net_maintenance':
                    line='echo "Waiting for net_maintenance service to start"\n'
                    lau_file.write(line)
                    line='while [ ! -f '+S.IP_PATH+' ]\n'
                    lau_file.write(line)
                    line='do\n'
                    lau_file.write(line)
                    line='  sleep 0.2\n'
                    lau_file.write(line)
                    line='done\n'
                    lau_file.write(line)
                    

    # Prepare stopper
    with open(STOPPER_PATH, 'w') as lau_file:
        for serv in serv_list.keys():
            if serv_list[serv] == 1:
                line='pid=$(cat node_services/python_pid_'+serv+'.file)\n'
                lau_file.write(line)
                line='kill -SIGINT $pid\n'
                lau_file.write(line)
                line='echo python process $pid stopping...\n'
                lau_file.write(line)
                
            
def main():
    # Check arguments
    if len(sys.argv) == 6:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            starting(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif len(sys.argv) == 2:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            startingdef(sys.argv[1])
    else:
        print("Script needs 1 or 5 parameters: 1 for L1, L2 or L3 and 4 for services activation. Please retry.")
        exit()
        
if __name__ == '__main__':
    main()

