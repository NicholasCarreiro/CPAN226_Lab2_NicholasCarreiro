# This program was modified by Nicholas Carreiro / N01492047

import socket
import argparse
import time
import os
import struct

def run_client(target_ip, target_port, input_file):
    # 1. Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (target_ip, target_port)

    # Set timeout for receiving ACKs (200ms for faster retry)
    sock.settimeout(0.2)

    print(f"[*] Sending file '{input_file}' to {target_ip}:{target_port}")

    if not os.path.exists(input_file):
        print(f"[!] Error: File '{input_file}' not found.")
        return

    try:
        # Prepare all chunks
        chunk_size = 4092  # 4-byte header + 4092 data = 4096 total
        with open(input_file, 'rb') as f:
            chunks = []
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)

        total_packets = len(chunks)
        window_size = 10
        base = 0
        next_seq = 0
        acked = set()
        send_count = {}
        max_sends = 1000

        def send_packet(seq):
            header = struct.pack('!I', seq)
            packet = header + chunks[seq]
            # Send twice to overcome relay buffering
            sock.sendto(packet, server_address)
            sock.sendto(packet, server_address)

        # Selective Repeat with aggressive resending
        timeout_count = 0
        while base < total_packets:
            # Send all packets in window
            while next_seq < base + window_size and next_seq < total_packets:
                if next_seq not in acked:
                    send_count[next_seq] = send_count.get(next_seq, 0) + 1
                    if send_count[next_seq] > max_sends:
                        print(f"[!] Failed to deliver packet {next_seq} after {max_sends} sends.")
                        return
                    send_packet(next_seq)
                next_seq += 1

            # Collect ACKs with short timeout
            try:
                ack_data, _ = sock.recvfrom(4)
                ack_seq = struct.unpack('!I', ack_data)[0]
                if ack_seq < total_packets and ack_seq not in acked:
                    acked.add(ack_seq)
                    # print(f"[*] ACK received for packet {ack_seq}")
                    while base in acked:
                        base += 1
                timeout_count = 0
            except socket.timeout:
                timeout_count += 1
                # Resend unacked packets in window
                for seq in range(base, min(base + window_size, total_packets)):
                    if seq not in acked:
                        send_count[seq] = send_count.get(seq, 0) + 1
                        if send_count[seq] > max_sends:
                            print(f"[!] Failed to deliver packet {seq} after {max_sends} sends.")
                            return
                        send_packet(seq)

        # Send EOF signal: packet with sequence number and empty data
        eof_seq = total_packets
        eof_packet = struct.pack('!I', eof_seq)
        eof_acked = False
        eof_sends = 0
        max_eof_sends = 100

        while not eof_acked and eof_sends < max_eof_sends:
            try:
                # Send EOF twice
                sock.sendto(eof_packet, server_address)
                sock.sendto(eof_packet, server_address)
                eof_sends += 1
                
                ack_data, _ = sock.recvfrom(4)
                ack_seq = struct.unpack('!I', ack_data)[0]
                if ack_seq == eof_seq:
                    print("[*] File transmission complete.")
                    return
            except socket.timeout:
                pass

        print("[!] File transmission failed during EOF.")

    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Naive UDP File Sender")
    parser.add_argument("--target_ip", type=str, default="127.0.0.1", help="Destination IP (Relay or Server)")
    parser.add_argument("--target_port", type=int, default=12000, help="Destination Port")
    parser.add_argument("--file", type=str, required=True, help="Path to file to send")
    args = parser.parse_args()

    run_client(args.target_ip, args.target_port, args.file)