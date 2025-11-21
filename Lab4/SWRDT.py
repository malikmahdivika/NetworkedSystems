import Network
import argparse
from time import sleep
import hashlib


class Segment:
    ## the number of bytes used to store segment length
    seq_num_S_length = 10
    length_S_length = 10
    ## length of md5 checksum in hex
    checksum_length = 32

    def __init__(self, seq_num, msg_S):
        self.seq_num = seq_num
        self.msg_S = msg_S

    @classmethod
    def from_byte_S(self, byte_S):
        if Segment.corrupt(byte_S):
            raise RuntimeError("Cannot initialize Segment: byte_S is corrupt")
        # extract the fields
        seq_num = int(
            byte_S[
                Segment.length_S_length : Segment.length_S_length
                + Segment.seq_num_S_length
            ]
        )
        msg_S = byte_S[
            Segment.length_S_length + Segment.seq_num_S_length + Segment.checksum_length :
        ]
        return self(seq_num, msg_S)

    def get_byte_S(self):
        # convert sequence number of a byte field of seq_num_S_length bytes
        seq_num_S = str(self.seq_num).zfill(self.seq_num_S_length)
        # convert length to a byte field of length_S_length bytes
        length_S = str(
            self.length_S_length
            + len(seq_num_S)
            + self.checksum_length
            + len(self.msg_S)
        ).zfill(self.length_S_length)
        # compute the checksum
        checksum = hashlib.md5((length_S + seq_num_S + self.msg_S).encode("utf-8"))
        checksum_S = checksum.hexdigest()
        # compile into a string
        return length_S + seq_num_S + checksum_S + self.msg_S

    @staticmethod
    def corrupt(byte_S):
        # extract the fields
        length_S = byte_S[0 : Segment.length_S_length]
        seq_num_S = byte_S[
            Segment.length_S_length : Segment.seq_num_S_length + Segment.seq_num_S_length
        ]
        checksum_S = byte_S[
            Segment.seq_num_S_length
            + Segment.seq_num_S_length : Segment.seq_num_S_length
            + Segment.length_S_length
            + Segment.checksum_length
        ]
        msg_S = byte_S[
            Segment.seq_num_S_length + Segment.seq_num_S_length + Segment.checksum_length :
        ]

        # compute the checksum locally
        checksum = hashlib.md5(str(length_S + seq_num_S + msg_S).encode("utf-8"))
        computed_checksum_S = checksum.hexdigest()
        # and check if the same
        return checksum_S != computed_checksum_S


class SWRDT:
    ## latest sequence number used in a segment
    seq_num = 1
    ## buffer of bytes read from network
    byte_buffer = ""

    def __init__(self, role_S, receiver_S, port):
        self.network = Network.NetworkLayer(role_S, receiver_S, port)

    def disconnect(self):
        self.network.disconnect()

    def swrdt_send(self, msg_S):
        p = Segment(self.seq_num, msg_S)
        self.seq_num += 1
        self.network.network_send(p.get_byte_S())

    def swrdt_receive(self):
        ret_S = None
        byte_S = self.network.network_receive()
        self.byte_buffer += byte_S
        # keep extracting segments
        while True:
            # check if we have received enough bytes
            if len(self.byte_buffer) < Segment.length_S_length:
                return ret_S  # not enough bytes to read segment length
            # extract length of segment
            length = int(self.byte_buffer[: Segment.length_S_length])
            if len(self.byte_buffer) < length:
                return ret_S  # not enough bytes to read the whole Segment
            # create Segment from buffer content and add to return string
            p = Segment.from_byte_S(self.byte_buffer[0:length])
            ret_S = p.msg_S if (ret_S is None) else ret_S + p.msg_S
            # remove the Segment bytes from the buffer
            self.byte_buffer = self.byte_buffer[length:]
            # if this was the last Segment, will return on the next iteration



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWRDT implementation.")
    parser.add_argument(
        "role",
        help="Role is either sender or receiver.",
        choices=["sender", "receiver"],
    )
    parser.add_argument("receiver", help="receiver.")
    parser.add_argument("port", help="Port.", type=int)
    args = parser.parse_args()

    swrdt = SWRDT(args.role, args.receiver, args.port)
    if args.role == "sender":
        swrdt.swrdt_send("MSG_FROM_SENDER")
        sleep(2)
        print(swrdt.swrdt_receive())
        swrdt.disconnect()

    else:
        sleep(1)
        print(swrdt.swrdt_receive())
        swrdt.swrdt_send("MSG_FROM_RECEIVER")
        swrdt.disconnect()
