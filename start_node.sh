nohup python3 -u node_services/net_maintenance.py L3 > /dev/null 2>&1 &
echo \$! > node_services/python_pid_net_maintenance.file
echo "Waiting for net_maintenance service to start"
while [ ! -f C:\Users\User\kDrive\Antoine\AnuuTech/node_data/ip.file ]
do
  sleep 0.2
done
nohup python3 -u node_services/chat.py L3 > /dev/null 2>&1 &
echo \$! > node_services/python_pid_chat.file
nohup python3 -u node_services/net_storage.py L3 > /dev/null 2>&1 &
echo \$! > node_services/python_pid_net_storage.file
nohup python3 -u node_services/PoH.py L3 > /dev/null 2>&1 &
echo \$! > node_services/python_pid_PoH.file
