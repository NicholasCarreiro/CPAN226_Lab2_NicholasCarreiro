"""
UDP Relay Proxy (Unreliable Network Simulator)

Usage:
    python relay.py --bind_port 12000 --server_ip 127.0.0.1 --server_port 12001 --loss 0.05 --reorder 0.0

How it works:
    - Client sends to Relay (bind_port).
    - Relay forwards to Server (server_ip:server_port).
    - Relay also forwards responses from Server back to the last Client it saw.

Arguments:
    --bind_port   Port the relay listens on (client sends here)
    --server_ip   Destination server IP
    --server_port Destination server port
    --loss        Packet loss probability (0.0 - 1.0)
    --reorder     Packet reorder/delay probability (0.0 - 1.0)
"""

import socket
import random
import time
import threading
import argparse

# Buffer size
BUF_SIZE = 4096

def handle_traffic(sock, target_ip, target_port, loss_rate, reorder_rate, delay):
    """
    Listens on the socket and forwards to target with noise.
    """
    client_addr = None
    buffer_to_server = []
    buffer_to_client = []

    def send_buffered(buffer, target_addr, label):
        if not buffer:
            return
        idx = random.randrange(len(buffer))
        pkt = buffer.pop(idx)
        sock.sendto(pkt, target_addr)
        print(f"[+] Proxy forwarded {len(pkt)} bytes (buffered) to {label} {target_addr}")

    def maybe_forward(data, target_addr, label, buffer):
        # Simulate loss
        if random.random() < loss_rate:
            print(f"[-] Dropped packet from {label}")
            return

        # Reorder: buffer some packets and send later in shuffled order
        if reorder_rate > 0 and random.random() < reorder_rate:
            buffer.append(data)
            print(f"[*] Buffered packet for reordering to {label}")
            # If we have more than one, force out-of-order by sending a random buffered packet
            if len(buffer) >= 2:
                send_buffered(buffer, target_addr, label)
            return

        # Normal (optionally delayed) forwarding
        if delay > 0:
            time.sleep(random.uniform(0.0, delay))
        sock.sendto(data, target_addr)
        print(f"[+] Proxy forwarded {len(data)} bytes to {label} {target_addr}")

        # Occasionally flush a buffered packet to increase reordering likelihood
        if buffer and random.random() < 0.3:
            send_buffered(buffer, target_addr, label)

    while True:
        try:
            data, addr = sock.recvfrom(BUF_SIZE)
            # Identify direction
            if addr == (target_ip, target_port):
                # Packet from server to client
                if client_addr:
                    maybe_forward(data, client_addr, "client", buffer_to_client)
            else:
                # Packet from client to server
                client_addr = addr
                maybe_forward(data, (target_ip, target_port), "server", buffer_to_server)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UDP Unreliable Relay")
    parser.add_argument("--bind_port", type=int, default=12000, help="Port relay listens on")
    parser.add_argument("--server_ip", type=str, default="127.0.0.1", help="Real Server IP")
    parser.add_argument("--server_port", type=int, default=12001, help="Real Server Port")
    parser.add_argument("--loss", type=float, default=0.0, help="Packet loss probability (0.0 - 1.0)")
    parser.add_argument("--reorder", type=float, default=0.0, help="Reorder/Delay probability (0.0 - 1.0)")
    
    args = parser.parse_args()

    # Create the relay socket
    relay_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Increase socket buffers to reduce UDP drops under load
        relay_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        relay_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        relay_sock.bind(("", args.bind_port))

        print(f"--- RELAY STARTED ---")
        print(f"Listening on: *:{args.bind_port}")
        print(f"Forwarding to: {args.server_ip}:{args.server_port}")
        print(f"Noise Profile: Loss={args.loss*100}%, Reorder={args.reorder*100}%")

        # In a real rigorous implementation, we need two sockets or complex NAT logic.
        # To keep it simple: 
        # The Relay acts as a 'dumb pipe'. 
        # Note: This simple script forwards one-way. 
        # For full bidirectional RDT, students point Client -> Relay, 
        # and Server sends ACKs directly to Client, OR you run two Relays.
        
        # SIMPLIFICATION FOR LAB:
        # Students configure Client to send to Relay_IP:Relay_Port.
        # Relay forwards to Server_IP:Server_Port.
        # Server receives packet from Relay_IP. 
        
        handle_traffic(relay_sock, args.server_ip, args.server_port, args.loss, args.reorder, 0.0)
    except KeyboardInterrupt:
        print("\n[!] Relay stopped manually.")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        relay_sock.close()
        print("[*] Relay socket closed.")