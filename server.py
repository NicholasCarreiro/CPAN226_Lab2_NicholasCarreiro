# This program was modified by Nicholas Carreiro / N01492047

import socket
import argparse
import struct

def run_server(port, output_file):
    # 1. Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 2. Bind the socket to the port (0.0.0.0 means all interfaces)
    server_address = ('', port)
    print(f"[*] Server listening on port {port}")
    print(f"[*] Server will save each received file as 'received_<ip>_<port>.jpg' based on sender.")
    sock.bind(server_address)

    # 3. Keep listening for new transfers
    try:
        while True:
            f = None
            sender_filename = None
            sender_addr = None
            expected_seq_num = 0
            buffer = {}  # Dictionary to store out-of-order packets
            eof_seq = None
            
            print("==== Waiting for file transfer ====")
            while True:
                packet, addr = sock.recvfrom(4096)  # 4 bytes header + 4092 data
                
                # Extract sequence number and data
                if len(packet) < 4:
                    continue
                
                seq_num = struct.unpack('!I', packet[:4])[0]
                data = packet[4:]
                
                # Protocol: If we receive an empty packet (data length is 0), it means "End of File"
                if not data:
                    eof_seq = seq_num
                    if eof_seq == expected_seq_num and not buffer:
                        ack_packet = struct.pack('!I', seq_num)
                        for _ in range(3):
                            sock.sendto(ack_packet, addr)
                        print(f"[*] End of file signal received from {addr} (seq: {seq_num}).")
                        break
                    continue
                
                # Initialize file on first packet
                if f is None:
                    print("==== Start of reception ====")
                    ip, sender_port = addr
                    sender_filename = f"received_{ip.replace('.', '_')}_{sender_port}.jpg"
                    sender_addr = addr
                    f = open(sender_filename, 'wb')
                    print(f"[*] First packet received from {addr}. File opened for writing as '{sender_filename}'.")
                
                # Reordering logic
                if seq_num == expected_seq_num:
                    # This is the packet we needed next! Write it.
                    f.write(data)
                    expected_seq_num += 1
                    # print(f"[*] Wrote packet {seq_num}, expecting next: {expected_seq_num}")
                    
                    # VITAL STEP: Check if the next packet is already waiting in buffer
                    while expected_seq_num in buffer:
                        buffered_data = buffer.pop(expected_seq_num)
                        f.write(buffered_data)
                        # print(f"[*] Wrote buffered packet {expected_seq_num}, expecting next: {expected_seq_num + 1}")
                        expected_seq_num += 1
                
                elif seq_num > expected_seq_num:
                    # Packet arrived too early (out of order). Store it for later.
                    buffer[seq_num] = data
                    # print(f"[*] Out-of-order packet {seq_num} (expected {expected_seq_num}), buffering...")
                
                else:
                    # Packet is old (duplicate). Ignore it.
                    # print(f"[*] Duplicate packet {seq_num} (expected {expected_seq_num}), ignoring...")
                    pass

                # Send ACK back (repeat to improve delivery under loss)
                ack_packet = struct.pack('!I', seq_num)
                for _ in range(3):
                    sock.sendto(ack_packet, addr)

                # If EOF already arrived and we've caught up, finalize
                if eof_seq is not None and eof_seq == expected_seq_num and not buffer:
                    ack_packet = struct.pack('!I', eof_seq)
                    for _ in range(3):
                        sock.sendto(ack_packet, addr)
                    print(f"[*] End of file signal received from {addr} (seq: {eof_seq}).")
                    break
            
            if f:
                f.close()
            print("==== End of reception ====")
    
    except KeyboardInterrupt:
        print("\n[!] Server stopped manually.")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        sock.close()
        print("[*] Server socket closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Naive UDP File Receiver")
    parser.add_argument("--port", type=int, default=12001, help="Port to listen on")
    parser.add_argument("--output", type=str, default="received_file.jpg", help="File path to save data")
    args = parser.parse_args()

    try:
        run_server(args.port, args.output)
    except KeyboardInterrupt:
        print("\n[!] Server stopped manually.")
    except Exception as e:
        print(f"[!] Error: {e}")