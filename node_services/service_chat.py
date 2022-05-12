#import class_service
from service_class import ReconnectingNodeConsumer 
import sys

class ServiceRunning(ReconnectingNodeConsumer):
    def _msg_process(self, msg, hdrs):
        super()._msg_process(msg, hdrs)
        self.LOGGER.info("Entered chat method")
        return True

#----------------------------------------------------------------
def main():


    # Check arguments
    if len(sys.argv) == 2:
        if (sys.argv[1] == 'L3'):
            nodelevel=sys.argv[1]

            # Create Instance and start the service
            consumer = ServiceRunning(nodelevel, 'chat')
            consumer.run()   
    else:
        print("The 'chat' service only works on L3")
        exit()
        
if __name__ == '__main__':
    main()
