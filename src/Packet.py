from typing import Optional, Tuple

Address = Tuple[str, int]

# Note that a SYNACK is not a combination of is_SYN=True and is_ACK=True but it has it's own attribute.
# It is not the most nice and safe way but it is simpler to manage.

class Packet:
    seq_num: Optional[int]
    is_SYN: bool
    is_SYNACK: bool
    new_port: Optional[int]
    is_ACK: bool
    ACK_num: Optional[int]
    is_AVB: bool
    is_SHP: bool
    shp_addr: Optional[str]

    @staticmethod
    def SYN() -> 'Packet':
        return Packet(sequence_number=0, is_SYN=True)

    @staticmethod
    def SYNACK(ACK_number: int, new_port: int) -> 'Packet':
        return Packet(sequence_number=0, ACK_number=ACK_number, new_port=new_port, is_SYNACK=True)

    @staticmethod
    def ACK(ACK_number: int) -> 'Packet':
        return Packet(is_ACK=True, ACK_number=ACK_number)

    @staticmethod
    def AVB(sequence_number: int) -> 'Packet':
        return Packet(sequence_number=sequence_number, is_AVB=True)

    @staticmethod
    def SHP(sequence_number: int, shipping_address: str) -> 'Packet':
        return Packet(sequence_number=sequence_number, is_SHP=True, shipping_address=shipping_address)

    def __init__(self,
                sequence_number: Optional[int] = None,
                is_SYN: bool = False,
                is_SYNACK: bool = False,
                new_port: Optional[int] = None,
                is_ACK: bool = False,
                ACK_number: Optional[int] = None,
                is_AVB: bool = False,
                is_SHP: bool = False,
                shipping_address: Optional[str] = None,) -> None:
        self.seq_num = sequence_number
        self.is_SYN = is_SYN
        self.is_SYNACK = is_SYNACK
        self.new_port = new_port
        self.is_ACK = is_ACK
        self.ACK_num = ACK_number
        self.is_AVB = is_AVB
        self.is_SHP = is_SHP
        self.shp_addr = shipping_address

    def encode(self) -> bytes: 
        return ":::".join([
            self.seq_num.__str__(),
            self.is_SYN.__str__(),
            self.is_SYNACK.__str__(),
            self.new_port.__str__(),
            self.is_ACK.__str__(),
            self.ACK_num.__str__(),
            self.is_AVB.__str__(),
            self.is_SHP.__str__(),
            self.shp_addr.__str__()
        ]).encode()

    @staticmethod
    def decode(bytes: bytes) -> 'Packet':
        seq_num_str, is_SYN_str, is_SYNACK_str, new_port_str, is_ACK_str, ACK_num_str, is_AVB_str, is_SHP_str, shp_addr_str = bytes.decode().split(":::")
        seq_num = None if seq_num_str == "None" else int(seq_num_str)
        is_SYN = is_SYN_str == "True"
        is_SYNACK = is_SYNACK_str == "True"
        new_port = None if new_port_str == "None" else int(new_port_str)
        is_ACK = is_ACK_str == "True"
        ACK_num = None if ACK_num_str == "None" else int(ACK_num_str)
        is_AVB = is_AVB_str == "True"
        is_SHP = is_SHP_str == "True"
        shp_addr = None if shp_addr_str == "None" else shp_addr_str

        return Packet(
            sequence_number=seq_num,
            is_SYN=is_SYN,
            is_SYNACK=is_SYNACK,
            new_port=new_port,
            is_ACK=is_ACK,
            ACK_number=ACK_num,
            is_AVB=is_AVB,
            is_SHP=is_SHP,
            shipping_address=shp_addr
        )

    def __str__(self) -> str:
        s: str = "Type: "
        if self.is_SYN:
            s += "SYN"
        elif self.is_SYNACK:
            s += "SYNACK"
        elif self.is_ACK:
            s += "ACK"
        elif self.is_AVB:
            s += "AVB"
        elif self.is_SHP:
            s += "SHP"
        else:
            print("ERROR: Bad Packet")

        if not self.is_ACK:
            s += "\nsequence_number: " + str(self.seq_num)

        if self.is_SYNACK or self.is_ACK:
            s += "\nACK_number: " + str(self.ACK_num)
        elif self.is_SHP:
            s += "\nshipping_address: " + self.shp_addr
        
        s += "\n"
        return s
