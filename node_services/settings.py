# Define all global settings for python services

# Global
SW_VERSION='0.2.0'
GENESIS_HASH='145120157110_AnnuTech_is_born_74312d646576' # For Genesis block
E_TRIM=1655157600 # epoch trim (14.06.2022 00:00 in CET)
VHOST='anuutech'
REQ_TIMEOUT=5 #timeout for http requests
MPORT=15672
PORT=5672
MAIN_PATH=''#Disabled for now os.path.abspath(os.path.join(os.getcwd(), os.pardir))
IP_PATH=MAIN_PATH+'node_data/ip.file'
NODESLIST_PATH=MAIN_PATH+'node_data/nodeslist.file'
NODESLIST_LOWER_PATH=MAIN_PATH+'node_data/nodeslist_lower.file'
NODESLIST_UPPER_PATH=MAIN_PATH+'node_data/nodeslist_upper.file'
UID_PATH=MAIN_PATH+'node_data/node_uid.file'
PS_PATH=MAIN_PATH+'node_data/ps_loc.file'
SERVICES_PATH='node_services/services.conf'
SERVICES_STATS_PATH='node_data/'
SERVICES_STATS_PATHEND='_stat.file'
PUBKEY_PATH='node_data/node_pub.key'
PRIVKEY_PATH='node_data/node_priv.key'
DEFAULT_TICK_INTERVAL=20.0 # may be increased to 60 sec

# Specific paths for services
POH_BLOCKS_PATH='node_data/blocks.file'
NET_STORAGE_PATH='node_data/blocks/'
NODE_DOWNTIME_LIMIT=900 #in seconds
DATA_STORAGE_PATH='node_data/data_storage/'

# Additional specific settings
MIN_NUMBER_OF_DATA_REPLICA=2
