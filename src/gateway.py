import signal
from DTOs import *
from socket import *
from threading import Thread
from time import sleep, time
from Packet import *
import utils
import random

PRINT_DEBUG = True # set to True to print debugging infos
SIMULATE_PACKET_LOSS = True # set to True to simulate packet loss

TCP_ADDRESS: Address = ('127.0.0.1', 8080)
UDP_ADDRESS: Address = ('127.0.0.1', 8081)
ACCEPTING_DRONES_THREAD: Thread
running: bool = True
client_is_connected: bool = False
client_socket: socket
should_update_client_console: bool = False # used to notify the main thread that client's console needs an update.

connected_drones: dict[Address, Drone] = {}

def print_debug(string: str):
    if PRINT_DEBUG or SIMULATE_PACKET_LOSS: print(string + "\n")

def should_be_lost() -> bool:
    return SIMULATE_PACKET_LOSS and random.randint(0, 3) < 1 # 25% probability of losing a sent packet.

def SIGINT_handler(sig, frame):
    global running

    running = False

    SERVER.close()

    ACCEPTING_DRONES_THREAD.join()

    for d in connected_drones.values():
        d.thread.join()
        d.sock.close()

    if client_is_connected:
        client_socket.shutdown(SHUT_RDWR)
        client_socket.close()

    exit(0)

signal.signal(signal.SIGINT, SIGINT_handler)


# ----- FUNCTIONS IMPLEMENTING DRONE PROTOCOL -----
def drone_loop(drone: Drone):
    ''' A loop which manages a drone workflow by checking when it's available and sending it shipping requests '''
    global should_update_client_console

    while running:
        if drone.state != DroneState.AVAILABLE:
            check_when_drone_gets_available(drone)
            drone.pending_shipping_request = None
            drone.state = DroneState.AVAILABLE
            should_update_client_console = True
        if drone.pending_shipping_request:
            send_shipping_request(drone.pending_shipping_request, drone)
            drone.state = DroneState.CURRENTLY_SHIPPING
            should_update_client_console = True
        else:
            sleep(0.2) # just to not waste all CPU time.

    print_debug("drone_loop %d:\tApp is being closed, exiting drone_loop." % drone.id)


def accept_drones():
    ''' Accepts new connections from drones and then starts a new thread for each drone '''
    global connected_drones, should_update_client_console

    drones_socket = socket(AF_INET, SOCK_DGRAM)
    drones_socket.bind(UDP_ADDRESS)

    while running:
        drones_socket.settimeout(0.5) # every half second check if app is being closed.
        try:
            data, address = drones_socket.recvfrom(4096)
        except timeout:
            continue
        
        packet = Packet.decode(data)
        if not packet.is_SYN:
            print_debug("accept_drones: Ignored message from %s because it's not a SYN" % str(address))
            break
        
        if address in connected_drones:
            print_debug("accept_drones: Ignored message from %s as the drone is already connected." % str(address))
        else:
            drone_sock = socket(AF_INET, SOCK_DGRAM)
            drone_sock.bind(('127.0.0.1', 0))
            drone = Drone(len(connected_drones)+1, address, DroneState.NOT_AVAILABLE, drone_sock)
            drone.increment_expected_recv_sequence_number()
            print("[GATEWAY]\t<--\tSYN\t<--\t[DRONE %d]\n" % drone.id)

            new_port = drone_sock.getsockname()[1]
            
            SYNACK = Packet.SYNACK(ACK_number=packet.seq_num+1, new_port=new_port)
            drone.increment_send_sequence_number()

            while running and not address in connected_drones:
                if not should_be_lost():
                    drones_socket.sendto(SYNACK.encode(), address)
                    print("[GATEWAY]\t-->\tSYNACK\t-->\t[DRONE %d]\n" % drone.id)
                else:
                    print_debug("[GATEWAY]\t-->\tSYNACK\t--X\t[DRONE %d] (LOST)" % drone.id)
                start = time()
                while running and not address in connected_drones:
                    drones_socket.settimeout(1 - abs(time() - start))
                    try:
                        data, new_address = drones_socket.recvfrom(4096)
                    except timeout:
                        break
                    if address != new_address:
                        print_debug("accept_drones: Ignored message from %s while connecting with %s" % (str(new_address), str(address)))
                    else:
                        packet = Packet.decode(data)
                        if packet.is_SYN: #SYNACK was lost
                            print_debug("accept_drones: Received duplicate SYN. SYNACK was lost.")
                            break
                        elif packet.is_ACK:
                            # even if last handshake ACK was lost, drones_socket can't recv an AVB as it would be sent to the drone.sock, not this one.
                            # so this packet must be an ACK
                            print("[GATEWAY]\t<--\tACK\t<--\t[DRONE %d]\n" % drone.id)
                            connected_drones[address] = drone
                            print("Connessione stabilita con il Drone %d all'indirizzo: %s\n" % (drone.id, str(address)))
                            drone.thread = Thread(target=drone_loop, args=[drone])
                            drone.thread.start()
                            should_update_client_console = True
                        else:
                            print("ERROR while sending an AVB.\nUnexpected Packet while waiting for ACK:\n" + packet.__str__())
                            exit(1)
    drones_socket.close()

def send_shipping_request(request: ShippingRequestDTO, drone: Drone):
    SHP = Packet.SHP(sequence_number=drone.send_sequence_number, shipping_address=request.shipping_address)
    drone.increment_send_sequence_number()
    while running:
        if not should_be_lost():
            drone.sock.sendto(SHP.encode(), drone.address)
            print("[GATEWAY]\t-->\tSHP\t-->\t[DRONE %d]\n" % drone.id)
        else:
            print_debug("[GATEWAY]\t-->\tSHP\t--X\t[DRONE %d] (LOST)" % drone.id)
        start = time()
        while running:
            try:
                drone.sock.settimeout(1 - abs(time()-start))
                data, address = drone.sock.recvfrom(4096)
            except timeout:
                break
            if drone.address == address:
                packet = Packet.decode(data)
                drone.sock.settimeout(None)
                if packet.is_ACK:
                    print("[GATEWAY]\t<--\tACK\t<--\t[DRONE %d]\n" % drone.id)
                    return
                elif packet.is_AVB:
                    if packet.seq_num < drone.expected_recv_sequence_number: # already received AVB which accumulated in the socket
                        print_debug("send_shipping_request: ignoring accumulated AVB")
                        continue
                    else:
                        # ACK from drone was lost, this AVB means that the drone is available again.
                        # ignoring this AVB while interpreting it as the ACK
                        # drone will retransmit it and it will be catched in the appropriate function
                        print("[GATEWAY]\t<--\tAVB\t<--\t[DRONE %d]\n" % drone.id)
                        print_debug("send_shipping_request: Ignoring AVB and iterpreting as a lost ACK")
                        return
                else:
                    print("ERROR while sending a shipping request.\nUnexpected Packet while waiting for ACK:\n" + packet.__str__())
                    exit(1)
            else:
                print_debug("send_shipping_request: Ignored message from %s while waiting for ACK from %s" % (str(address), str(drone.address)))
    print_debug("send_shipping_request: App is being closed, exiting send_shipping_request")

def check_when_drone_gets_available(drone: Drone):
    while running:
        drone.sock.settimeout(0.5) # every half second check if app is being closed.
        try:
            data, address = drone.sock.recvfrom(4096)
        except timeout:
            continue

        packet = Packet.decode(data)

        if drone.address == address:
            # message can only be an AVB
            if packet.seq_num < drone.expected_recv_sequence_number:
                print_debug("drone_loop %d:\tcheck_when_drone_gets_available: ignoring accumulated AVB")
                continue
            else:
                print("[GATEWAY]\t<--\tAVB\t<--\t[DRONE %d]\n" % drone.id)
                drone.increment_expected_recv_sequence_number()
                if not should_be_lost():
                    drone.sock.sendto(Packet.ACK(packet.seq_num + 1).encode(), drone.address)
                    print("[GATEWAY]\t-->\tACK\t-->\t[DRONE %d]" % drone.id)
                else:
                    print_debug("[GATEWAY]\t-->\tACK\t--X\t[DRONE %d] (LOST)\n" % drone.id)
                drone.sock.settimeout(None)
                return
        else:
            print_debug("drone_loop %d:\tcheck_when_drone_gets_available: Ignoring message from address: %s while waiting for AVB" % (drone.id, str(address)))

    print_debug("drone_loop %d:\tcheck_when_drone_gets_available: App is being closed, exiting check_when_drone_gets_available" % drone.id)

# ----- FUNCTIONS ABOUT SHIPPING REQUESTS ------
def handle_shipping_request(request: ShippingRequestDTO):
    drone: Drone = None
    for d in connected_drones.values():
        if d.id == request.drone_id:
            drone = d
            break
    if drone:
        if drone.state == DroneState.AVAILABLE:
            drone.pending_shipping_request = request
            print_debug("handle_shipping_request: Drone %d has new pending_shipping_request" % drone.id)
        else:
            send_error_message("Il Drone %d è NON DISPONIBILE." % request.drone_id)    
    else:
        send_error_message("Il Drone %d non è connesso." % request.drone_id)

# ----- FUNCTIONS RESPONSIBLE FOR UPDATING CLIENT'S CONSOLE ----- 
def client_interface_text() -> str:
    drones_state_description = ""
    for drone_address in connected_drones:
        drone = connected_drones[drone_address]
        drones_state_description += "DRONE " + str(drone.id) + "\t--->   " + drone.state.__str__()
        if drone.pending_shipping_request:
            drones_state_description += " a \"%s\"\n" % drone.pending_shipping_request.shipping_address
        else:
            drones_state_description += "\n"
    return drones_state_description

def update_client_console():
    if client_is_connected:
        print("[GATEWAY]\t-->\tAggiornamento interfaccia\t-->\t[CLIENT]\n")
        dto = GatewayInterfaceDTO(client_interface_text(), is_error=False)
        utils.send_message(client_socket, dto.encode())

def send_error_message(message: str):
    if client_is_connected:
        print("[GATEWAY]\t-->\t%s\t-->\t[CLIENT]\n" % message)
        dto = GatewayInterfaceDTO(message, is_error=True)
        utils.send_message(client_socket, dto.encode())


# ----- MAIN -----
if __name__ == "__main__":
    ACCEPTING_DRONES_THREAD = Thread(target=accept_drones)
    ACCEPTING_DRONES_THREAD.start()

    SERVER = socket(AF_INET, SOCK_STREAM)
    SERVER.bind(TCP_ADDRESS)
    
    SERVER.listen(1)
    print("\n\nGateway attivo su %s:%s\n" % SERVER.getsockname())

    while True:
        client_socket, client_address = SERVER.accept()
        client_is_connected = True
        should_update_client_console = True
        print("[GATEWAY]\t<--\tConnesso\t<--\t[CLIENT]\n")

        while True:
            if should_update_client_console:
                should_update_client_console = False
                update_client_console()
            client_socket.settimeout(0.5)
            try:
                data = utils.recv_one_message(client_socket)
            except timeout:
                continue
            client_socket.settimeout(None)
            if data:
                shipping_request = ShippingRequestDTO.decode(data)
                print("[GATEWAY]\t<--\tSpedizione per il Drone %d all'indirizzo: %s\t<--\t[CLIENT]\n" % (shipping_request.drone_id, shipping_request.shipping_address))
                handle_shipping_request(shipping_request)
            else:
                print("[GATEWAY]\t<--\tDisconnesso\t<--\t[CLIENT]\n")
                client_is_connected = False
                client_socket.close()
                break
