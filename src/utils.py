from socket import socket
import struct
from typing import Optional

# Utilities for turning a socket stream communication into a message-like communication
# Using the first 4 bytes of evey message to describe its length.

def send_message(sock: socket, message: bytes):
    length = len(message)
    sock.sendall(struct.pack('!I', length))
    sock.sendall(message)

def recv_one_message(sock: socket) -> Optional[bytes]:
    lengthbuf = recvall(sock, 4)
    if not lengthbuf:
        return None
    length, = struct.unpack('!I', lengthbuf)
    return recvall(sock, length)

def recvall(sock: socket, count: int) -> Optional[bytes]:
    buf = b''
    while count:
        newbuf = sock.recv(count)
        if not newbuf:
            return None
        buf += newbuf
        count -= len(newbuf)
    return buf