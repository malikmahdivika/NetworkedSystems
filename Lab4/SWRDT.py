import Network
import argparse
import hashlib
import time


class Segment:
    ## number of bytes to store segment length
    seq_num_S_length = 10
    length_S_length = 10
    ## length of md5 checksum in hex
    checksum_length = 32

    def __init__(self, seq_num, msg_S):
        self.seq_num = seq_num
        self.msg_S = msg_S  # payload or "ACK"

    @classmethod
    def from_byte_S(cls, byte_S):
        if Segment.corrupt(byte_S):
            return None

        length_off = cls.length_S_length
        seq_off = length_off + cls.seq_num_S_length
        checksum_off = seq_off + cls.checksum_length

        try:
            seq_num = int(byte_S[length_off:seq_off])
        except:
            return None
        msg_S = byte_S[checksum_off:]

        return cls(seq_num, msg_S)

    def get_byte_S(self):
        seq_num_S = str(self.seq_num).zfill(self.seq_num_S_length)
        total_length = (
            self.length_S_length +
            len(seq_num_S) +
            self.checksum_length +
            len(self.msg_S)
        )
        length_S = str(total_length).zfill(self.length_S_length)

        checksum = hashlib.md5((length_S + seq_num_S + self.msg_S).encode("utf-8"))
        checksum_S = checksum.hexdigest()

        return length_S + seq_num_S + checksum_S + self.msg_S

    @staticmethod
    def corrupt(byte_S):
        if len(byte_S) < (
            Segment.length_S_length +
            Segment.seq_num_S_length +
            Segment.checksum_length
        ):
            return True

        length_S = byte_S[:Segment.length_S_length]
        seq_S = byte_S[
            Segment.length_S_length:
            Segment.length_S_length + Segment.seq_num_S_length
        ]
        checksum_start = Segment.length_S_length + Segment.seq_num_S_length
        checksum_S = byte_S[
            checksum_start:
            checksum_start + Segment.checksum_length
        ]
        msg_S = byte_S[checksum_start + Segment.checksum_length:]

        computed = hashlib.md5((length_S + seq_S + msg_S).encode("utf-8")).hexdigest()
        return checksum_S != computed


class SWRDT:
    def __init__(self, role, receiver, port, timeout=2.0):
        self.network = Network.NetworkLayer(role, receiver, port)

        # Sender state
        self.curr_seq = 1

        # Receiver state
        self.expected_seq = 1
        self.last_delivered_seq = 0  # Track last delivered sequence number

        self.byte_buffer = ""
        self.app_buffer = []  # messages delivered to application
        self.timeout = timeout

    def disconnect(self):
        self.network.disconnect()

    # ---------------------------
    # INTERNAL: extract raw seg
    # ---------------------------
    def _extract_segment(self):
        if len(self.byte_buffer) < Segment.length_S_length:
            return None

        try:
            seg_len = int(self.byte_buffer[:Segment.length_S_length])
        except:
            self.byte_buffer = self.byte_buffer[1:]
            return None

        if len(self.byte_buffer) < seg_len:
            return None

        seg_bytes = self.byte_buffer[:seg_len]
        self.byte_buffer = self.byte_buffer[seg_len:]
        return seg_bytes

    # ---------------------------
    # INTERNAL: process incoming
    # returns list: (ack_seq, is_corrupt)
    # ---------------------------
    def _process_incoming(self):
        acks = []

        while True:
            raw = self._extract_segment()
            if raw is None:
                break

            corrupted = Segment.corrupt(raw)

            length_off = Segment.length_S_length
            seq_off = length_off + Segment.seq_num_S_length
            checksum_off = seq_off + Segment.checksum_length

            try:
                seq_num = int(raw[length_off:seq_off])
            except:
                seq_num = -1
                corrupted = True

            msg_S = raw[checksum_off:]

            if corrupted:
                if msg_S.startswith("ACK"):
                    acks.append((seq_num, True))     # corrupted ACK
                else:
                    # corrupted DATA
                    prev_ack = max(0, self.expected_seq - 1)
                    print(f"Corruption detected! Send ACK {prev_ack}")
                    ack = Segment(prev_ack, "ACK")
                    self.network.network_send(ack.get_byte_S())
                continue

            # Clean segment
            seg = Segment.from_byte_S(raw)
            
            if seg is None:
                # Segment construction failed, skip it
                continue

            if seg.msg_S.startswith("ACK"):
                acks.append((seg.seq_num, False))
            else:
                # DATA segment
                #print(f"[DEBUG] expected_seq={self.expected_seq}, last_delivered_seq={self.last_delivered_seq}, received_seq={seg.seq_num}")
                if seg.seq_num == self.expected_seq:
                    # Only deliver to application if not already delivered
                    if seg.seq_num > self.last_delivered_seq:
                        print(f"Receive message {seg.seq_num}. Send ACK {seg.seq_num}")
                        self.app_buffer.append(seg.msg_S)
                        self.last_delivered_seq = seg.seq_num
                        ack = Segment(seg.seq_num, "ACK")
                        self.network.network_send(ack.get_byte_S())
                        self.expected_seq += 1
                    else:
                        # Duplicate, already delivered, just ACK last delivered
                        prev_ack = self.last_delivered_seq
                        print(f"Receive duplicate message {seg.seq_num}. Send ACK {prev_ack}")
                        ack = Segment(prev_ack, "ACK")
                        self.network.network_send(ack.get_byte_S())
                else:
                    # Out of order
                    prev_ack = self.last_delivered_seq
                    print(f"Receive out-of-order message {seg.seq_num}. Send ACK {prev_ack}")
                    ack = Segment(prev_ack, "ACK")
                    self.network.network_send(ack.get_byte_S())

        return acks

    # ---------------------------
    # PUBLIC: swrdt_send()
    # ---------------------------
    def swrdt_send(self, msg_S):
        seg = Segment(self.curr_seq, msg_S)
        seg_bytes = seg.get_byte_S()

        print(f"Send message {self.curr_seq}")
        self.network.network_send(seg_bytes)
        start = time.time()

        while True:
            incoming = self.network.network_receive()
            if incoming:
                self.byte_buffer += incoming

            acks = self._process_incoming()

            for ack_seq, is_corrupt in acks:
                if is_corrupt:
                    print(f"Corruption detected in ACK. Resend message {self.curr_seq}")
                    self.network.network_send(seg_bytes)
                    start = time.time()
                    continue

                if ack_seq == self.curr_seq:
                    print(f"Receive ACK {ack_seq}. Message successfully sent!")
                    self.curr_seq += 1
                    return

                print(f"Receive ACK {ack_seq}. Resend message {self.curr_seq} Ignored")

            # timeout
            if time.time() - start > self.timeout:
                print(f"Timeout! Resend message {self.curr_seq}")
                self.network.network_send(seg_bytes)
                start = time.time()

    # ---------------------------
    # PUBLIC: swrdt_receive()
    # ---------------------------
    def swrdt_receive(self):
        if self.app_buffer:
            return self.app_buffer.pop(0)

        incoming = self.network.network_receive()
        if incoming:
            self.byte_buffer += incoming

        self._process_incoming()

        if self.app_buffer:
            return self.app_buffer.pop(0)

        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWRDT implementation.")
    parser.add_argument("role", choices=["sender", "receiver"])
    parser.add_argument("receiver")
    parser.add_argument("port", type=int)
    args = parser.parse_args()

    swrdt = SWRDT(args.role, args.receiver, args.port)

    if args.role == "sender":
        swrdt.swrdt_send("MSG_FROM_SENDER")
        time.sleep(2)
        print(swrdt.swrdt_receive())
        swrdt.disconnect()

    else:
        time.sleep(1)
        print(swrdt.swrdt_receive())
        swrdt.swrdt_send("MSG_FROM_RECEIVER")
        swrdt.disconnect()
