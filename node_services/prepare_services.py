import os
import json
import sys

# Check list of services configured
SERVICES_PATH='node_services/services.conf'
LAUNCHER_PATH='start_node.sh'
STOPPER_PATH='stop_node.sh'
IP_PATH='node_data/ip.file'

def starting(nodelevel):
    serv_list={}
    if os.path.isfile(SERVICES_PATH):
        with open(SERVICES_PATH, 'r') as serv_file:
            serv_list=json.load(serv_file)
    else:
        #default config, net_maintenance is mandatory
        serv_list={'net_maintenance': 1, 'chat': 0, 'net_storage': 0,
                   'PoH': 0, 'data_storage': 0}
        with open(SERVICES_PATH, 'w') as serv_file:
                serv_file.write(json.dumps(serv_list))

    print("List of services configured: " + str(serv_list))

    # Prepare launcher
    with open(LAUNCHER_PATH, 'w') as lau_file:
        for serv in serv_list.keys():
            if serv_list[serv] == 1:
                line='nohup python3 -u node_services/service_'+serv+'.py '+nodelevel+' > /dev/null 2>&1 &\n'
                lau_file.write(line)
                line='echo $! > node_services/python_pid_'+serv+'.file\n'
                lau_file.write(line)
                if serv=='net_maintenance':
                    line='echo "Waiting for net_maintenance service to start"\n'
                    lau_file.write(line)
                    line='while [ ! -f '+IP_PATH+' ]\n'
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
    if len(sys.argv) == 2:
        if sys.argv[1] == 'L1' or sys.argv[1] == 'L2' or sys.argv[1] == 'L3' :
            nodelevel=sys.argv[1]
            starting(nodelevel)
    else:
        print("Script needs 1 parameter (L1, L2 or L3). Please retry.")
        exit()
        
if __name__ == '__main__':
    main()

