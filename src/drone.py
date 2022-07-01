import random 
from time import sleep, time
from Packet import *
from socket import *
import signal

PRINT_DEBUG = True # set to True to print debugging infos
SIMULATE_PACKET_LOSS = True # set to True to simulate packet loss

connected = False
server_address: Address = ('127.0.0.1', 8081)
connection_address: Address = None
sock = socket(AF_INET, SOCK_DGRAM)
shipping: bool = False
shipping_address: str = None
send_sequence_number: int = 0
expected_recv_sequence_number: int = 0

def SIGINT_handler(sig, frame):
    sock.close()
    exit(0)

signal.signal(signal.SIGINT, SIGINT_handler)

def print_debug(string: str):
    if PRINT_DEBUG or SIMULATE_PACKET_LOSS: print(string + "\n")

def should_be_lost() -> bool:
    return SIMULATE_PACKET_LOSS and random.randint(0, 3) < 1 # 25% probability of losing a sent packet.

def increment_send_sequence_number():
    global send_sequence_number
    send_sequence_number += 1

def increment_expected_recv_sequence_number():
    global expected_recv_sequence_number
    expected_recv_sequence_number += 1

def connect_to_server():
    ''' Establishes a connection with the server '''
    global connected, server_address, connection_address

    SYN = Packet.SYN()
    increment_send_sequence_number()
    while not connected:
        if not should_be_lost():
            sock.sendto(SYN.encode(), server_address)
            print_debug("[GATEWAY]\t<--\tSYN\t<--\t[DRONE]\n")
            #print_debug("SYN sent")
        else:
            print_debug("[GATEWAY]\tX--\tSYN\t<--\t[DRONE] (LOST)\n")
        start = time()
        while not connected:
            sock.settimeout(1 - abs(time() - start))
            try:
                data, address = sock.recvfrom(4096)
            except timeout:
                print_debug("timeout waiting for SYNACK")
                break
            if server_address != address:
                print_debug("Ignored message not coming from server")
            else:
                packet = Packet.decode(data)
                if packet.seq_num < expected_recv_sequence_number:
                    continue
                increment_expected_recv_sequence_number()
                if packet.is_SYNACK:
                    print_debug("[GATEWAY]\t-->\tSYNACK\t-->\t[DRONE]\n")
                    if not should_be_lost():
                        sock.sendto(Packet.ACK(ACK_number=packet.seq_num + 1).encode(), server_address)
                        print_debug("[GATEWAY]\t<--\tACK\t<--\t[DRONE]\n")
                    else:
                        print_debug("[GATEWAY]\tX--\tACK\t<--\t[DRONE] (LOST)\n")
                    sock.settimeout(None)
                    connection_address = (server_address[0], packet.new_port)
                    connected = True
                else:
                    print("ERRORE: Messaggio inaspettato, l'unico tipo di messaggio ricevibile dal server è SYNACK")
                    print(packet.__str__())
                    exit(1)

def available():
    ''' Notifies the server that the drone is AVAILABLE for new shipments '''
    AVB = Packet.AVB(send_sequence_number)
    increment_send_sequence_number()

    while True:
        if not should_be_lost():
            sock.sendto(AVB.encode(), connection_address)
            print_debug("[GATEWAY]\t<--\tAVB\t<--\t[DRONE]\n")
        else:
            print_debug("[GATEWAY]\tX--\tAVB\t<--\t[DRONE] (LOST)\n")
        start = time()
        while True:
            try:
                sock.settimeout(1 - abs(time()-start))
                data, address = sock.recvfrom(4096)
            except timeout:
                print_debug("timeout waiting for ACK")
                break

            packet = Packet.decode(data)
            sock.settimeout(None)

            if address == server_address:
                print_debug("[GATEWAY]\t-->\tSYNACK\t-->\t[DRONE]\n") # duplicate SYNACK
                if not should_be_lost():
                    sock.sendto(Packet.ACK(packet.seq_num + 1).encode(), server_address)
                    print_debug("[GATEWAY]\t<--\tACK\t<--\t[DRONE]\n")
                else:
                    print_debug("[GATEWAY]\tX--\tACK\t<--\t[DRONE] (LOST)\n")
                break
            elif connection_address == address:
                if packet.is_ACK:
                    if packet.ACK_num == AVB.seq_num + 1:
                        print_debug("[GATEWAY]\t-->\tACK\t-->\t[DRONE]\n")
                        return
                    else:
                        continue
                elif packet.is_SHP:
                    if packet.seq_num < expected_recv_sequence_number:
                        print_debug("ignoring packet with seq_num %d while %d expected.." % (packet.seq_num, expected_recv_sequence_number))
                        continue
                    # message may be a shipping request if the ACK was lost
                    # ignoring this message while interpreting it as the ACK
                    # server will retransmit it and it will be catched in the appropriate function
                    print_debug("Ignoring received SHP and iterpreting as the lost ACK")
                    return
                else:
                    print("ERRORE: Inviando un AVB. Aspettando l'ACK è stato ricevuto un pacchetto inaspettato:\n" + packet.__str__())
                    exit(1)
            else:
                print_debug("Ignored message not coming from server")

def recv_shipping_request() -> Packet:
    ''' Waits until it receives a new shipping request Packet '''
    while True:
        data, address = sock.recvfrom(4096)
        packet = Packet.decode(data)
        if address == connection_address:
            if packet.seq_num < expected_recv_sequence_number:
                print_debug("ignoring packet: " + packet.__str__())
                continue
            else:
                increment_expected_recv_sequence_number()

            if packet.is_SHP:
                print_debug("[GATEWAY]\t-->\tSHP\t-->\t[DRONE]\n")
                if not should_be_lost():
                    sock.sendto(Packet.ACK(packet.seq_num + 1).encode(), connection_address)
                    print_debug("[GATEWAY]\t<--\tACK\t<--\t[DRONE]\n")
                else:
                    print_debug("[GATEWAY]\tX--\tACK\t<--\t[DRONE] (LOST)\n")
                return packet
            else:
                print("Messaggio inaspettato, l'unico tipo di messaggio ricevibile dal server è SHP")
                print(packet.__str__())
                exit(1)
        else:
            print_debug("Ignored message not coming from server")


def ship_to(shipping_address: str):
    ''' simulates a shipment '''
    shipping_time = random.randint(3, 20)
    deliverying_time = random.randint(1, 2)
    print("Parto per %s..." % shipping_address)
    sleep_while_listening(shipping_time)
    print("Consegno...")
    sleep_while_listening(deliverying_time)
    print("Torno alla stazione...")
    sleep_while_listening(shipping_time)
    print("Sono tornato alla stazione")
    return

# if SHP ACK is lost and the drone sleeps normally it would not be able to receive duplicate SHP and server will think the drone hasn't
# started shipping until it becomes available again.
# this function allows to listen for duplicate SHP while simulating a sleep.
def sleep_while_listening(seconds: float):
    sock.settimeout(0.1)
    while seconds > 0:
        sleep(0.2)
        seconds -= 0.2
        start = time()
        try:
            data, address = sock.recvfrom(4096)
        except timeout:
            seconds -= time() - start
            continue
        seconds -= time() - start
        if address == connection_address:
            # only packets i can get are duplicate SHP if my ACK was lost
            packet = Packet.decode(data)
            if packet.is_SHP and packet.seq_num < expected_recv_sequence_number:
                print_debug("[GATEWAY]\t-->\tSHP\t-->\t[DRONE]\n")
                if not should_be_lost():
                    sock.sendto(Packet.ACK(packet.seq_num + 1).encode(), connection_address)
                    print_debug("[GATEWAY]\t<--\tACK\t<--\t[DRONE]\n")
                else:
                    print_debug("[GATEWAY]\tX--\tACK\t<--\t[DRONE] (LOST)\n")
            else:
                print("ERROR. Unexpected packet, only duplicate SHP should be received here.\n" + packet.__str__())
        else:
            print_debug("Ignored message not coming from server")
    
    sock.settimeout(None)



if __name__ == "__main__":
    connect_to_server()
    print("connesso")
    while True:
        available()
        message = recv_shipping_request()
        ship_to(message.shp_addr)