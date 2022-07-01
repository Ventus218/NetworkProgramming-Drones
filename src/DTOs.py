from enum import Enum, auto
from socket import socket
from threading import Thread
from typing import Optional, Tuple

class ShippingRequestDTO:
    drone_id: int
    shipping_address: str

    def __init__(self, drone_id: int, shipping_address: str):
        self.drone_id = drone_id
        self.shipping_address = shipping_address

    def encode(self) -> bytes: 
        return (str(self.drone_id) + ":::" + self.shipping_address).encode()

    @staticmethod
    def decode(bytes: bytes) -> 'ShippingRequestDTO':
        drone_id, shipping_address = bytes.decode().split(":::")
        return ShippingRequestDTO(int(drone_id), shipping_address)


class GatewayInterfaceDTO:
    message: str
    is_error: bool

    def __init__(self, message: str, is_error: bool = False):
        self.message = message
        self.is_error = is_error

    def encode(self) -> bytes: 
        return (self.is_error.__str__() + ":::" + self.message).encode()

    @staticmethod
    def decode(bytes: bytes) -> 'GatewayInterfaceDTO':
        is_error_str, message = bytes.decode().split(":::")
        return GatewayInterfaceDTO(message, is_error_str == "True")


class DroneState(Enum):
    NOT_AVAILABLE = auto()
    CURRENTLY_SHIPPING = auto()
    AVAILABLE = auto()

    def __str__(self):
        if self == DroneState.NOT_AVAILABLE:
            return "NON DISPONIBILE"
        if self == DroneState.CURRENTLY_SHIPPING:
            return "STA CONSEGNANDO"
        if self == DroneState.AVAILABLE:
            return "DISPONIBILE"
        print("Errore")
        exit(1)

class Drone:
    id: int
    address: Tuple[str, int]
    state: DroneState
    sock: socket
    send_sequence_number: int
    expected_recv_sequence_number: int
    pending_shipping_request: Optional[ShippingRequestDTO]
    thread: Optional[Thread]

    def __init__(self, id: int, address: Tuple[str, int], state: DroneState, sock: socket, send_sequence_number: int = 0, expected_recv_sequence_number: int = 0):
        self.id = id
        self.address = address
        self.state = state
        self.sock = sock
        self.send_sequence_number = send_sequence_number
        self.expected_recv_sequence_number = expected_recv_sequence_number
        self.pending_shipping_request = None
        self.thread = None

    def increment_send_sequence_number(self):
        self.send_sequence_number += 1

    def increment_expected_recv_sequence_number(self):
        self.expected_recv_sequence_number += 1