import sys
import socket
import threading
import json
import time
from copy import deepcopy

INF = 999               # infinity value
BCAST_TTL = 5           # starting TTL for broadcasted LS messages
DIJKSTRA_INTERVAL = 10  # seconds
SENDER_INTERVAL = 1     # seconds
LOCALHOST = "127.0.0.1" # le localhost

class Router:
    def __init__(self, router_id: int, router_port: int, config_file: str): # type hint perchance
        self.router_id = router_id
        self.router_port = router_port
        self.config_file = config_file

        # read configuration
        self.num_nodes = None
        # neighbors: {neighbor_id: (cost, port, label)}
        self.neighbors = {}

        # link state DB: node_id -> list of costs length num_nodes
        self.link_states = {}

        # seen messages to prevent duplicates: set of (origin, seq)
        self.seen_msgs = set()

        # sequence number counters for messages originated by this router
        self.own_seq = 0

        # socket for UDP comms
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # bind to given port on localhost
        self.sock.bind((LOCALHOST, self.router_port))

        # thread safety; operating systems in my networked systems class O_O
        self.lock = threading.Lock()

        self._read_config()
        self._init_own_link_state()

    # -------------------------
    # config parsing & init
    # -------------------------
    def _read_config(self):
        with open(self.config_file, "r") as f:
            lines = [ln.strip() for ln in f.readlines() if ln.strip() != ""]
            if not lines:
                raise ValueError("Empty config file")

            self.num_nodes = int(lines[0])
            for line in lines[1:]:
                parts = line.split()
                if len(parts) != 4:
                    raise ValueError(f"Bad config line: '{line}'")
                label, nid_s, cost_s, port_s = parts
                nid = int(nid_s)
                cost = int(cost_s)
                port = int(port_s)
                self.neighbors[nid] = (cost, port, label)

            # basic checks
            if self.num_nodes <= 0 or self.num_nodes > 10:
                raise ValueError("num_nodes must be between 1 and 10 (inclusive)")

    def _init_own_link_state(self):
        vec = [INF] * self.num_nodes
        vec[self.router_id] = 0
        for nid, (cost, _, _) in self.neighbors.items():
            vec[nid] = cost
        with self.lock:
            self.link_states[self.router_id] = vec

    # -------------------------
    # message creation / send
    # -------------------------
    def _make_ls_message(self):
        with self.lock:
            self.own_seq += 1
            msg = {
                "origin": self.router_id,
                "seq": self.own_seq,
                "ls_vector": self.link_states[self.router_id],
                "ttl": BCAST_TTL
            }
            return msg

    def _send_to_neighbor(self, data_bytes, port):
        self.sock.sendto(data_bytes, (LOCALHOST, port))

    # sender thread: send own LS vector every second
    def sender(self):
        while True:
            msg = self._make_ls_message()
            data = json.dumps(msg).encode()
            # mark as seen so we don't reprocess our own message when looped back
            with self.lock:
                self.seen_msgs.add((msg["origin"], msg["seq"]))
            for nid, (_, port, _) in self.neighbors.items():
                try:
                    self._send_to_neighbor(data, port)
                except Exception as e:
                    print(f"[Router {self.router_id}] send error to {nid}@{port}: {e}")
            time.sleep(SENDER_INTERVAL)

    # -------------------------
    # receiver thread
    # -------------------------
    def receiver(self):
        while True:
            try:
                raw, addr = self.sock.recvfrom(65536)
            except Exception as e:
                print(f"[Router {self.router_id}] socket recv error: {e}")
                continue

            try:
                msg = json.loads(raw.decode())
            except Exception as e:
                # ignore bad messages
                continue

            origin = int(msg.get("origin", -1))
            seq = int(msg.get("seq", -1))
            ls_vector = msg.get("ls_vector")
            ttl = int(msg.get("ttl", 0))

            if origin < 0 or seq < 0 or ls_vector is None:
                # malformed
                continue

            with self.lock:
                # if we've already seen this exact message, ignore
                if (origin, seq) in self.seen_msgs:
                    continue
                # mark seen
                self.seen_msgs.add((origin, seq))

                # ensure vector length correct -> convert to ints
                try:
                    vec = [int(x) for x in ls_vector]
                except Exception:
                    continue
                if len(vec) != self.num_nodes:
                    # invalid vector length: ignore
                    continue

                # check if link_states[origin] is new or changed
                prev = self.link_states.get(origin)
                if prev is None or prev != vec:
                    self.link_states[origin] = vec.copy()

            # rebroadcast if ttl > 0 to all neighbors
            if ttl > 0:
                msg["ttl"] = ttl - 1
                data = json.dumps(msg).encode()
                # rebroadcast to all neighbors
                with self.lock:
                    for nid, (_, port, _) in self.neighbors.items():
                        try:
                            self._send_to_neighbor(data, port)
                        except Exception:
                            pass

    # -------------------------
    # dijkstra thread
    # -------------------------
    def dijkstra_thread(self):
        while True:
            time.sleep(DIJKSTRA_INTERVAL)
            with self.lock:
                if len(self.link_states) < self.num_nodes:
                    print(f"\nRouter {self.router_id}: LSDB incomplete ({len(self.link_states)}/{self.num_nodes}), skipping Dijkstra.\n")
                    continue

                # copy LSDB to work on (avoid holding lock during compute/print)
                lsdb_copy = deepcopy(self.link_states)

            dist, prev = self.run_dijkstra(lsdb_copy)
            self.print_dijkstra(dist, prev)
            self.print_forwarding_table(dist, prev)

    # -------------------------
    # Dijkstra implementation
    # -------------------------
    def run_dijkstra(self, lsdb):
        N = self.num_nodes
        dist = [INF] * N
        prev = [-1] * N
        visited = [False] * N

        dist[self.router_id] = 0
        prev[self.router_id] = -1

        for _ in range(N):
            # choose smallest unvisited node
            u = None
            min_val = INF + 1
            for i in range(N):
                if not visited[i] and dist[i] < min_val:
                    min_val = dist[i]
                    u = i
            if u is None:
                break
            visited[u] = True

            # relax using u's link-state vector
            # lsdb[u] is vector of costs from u to all v
            # if for some reason lsdb doesn't have u, treat as INF
            vec_u = lsdb.get(u, [INF]*N)
            for v in range(N):
                cost_uv = int(vec_u[v]) if v < len(vec_u) else INF
                if cost_uv >= INF:
                    continue
                if dist[u] + cost_uv < dist[v]:
                    dist[v] = dist[u] + cost_uv
                    prev[v] = u

        return dist, prev

    # -------------------------
    # printing helpers
    # -------------------------
    def print_dijkstra(self, dist, prev):
        # Print in the format requested in the lab manual
        print(f"\n=== Router {self.router_id} Dijkstra Results ===")
        print("Destination_Routerid     Distance    Previous_node_id")
        for i in range(self.num_nodes):
            d = dist[i]
            p = prev[i] if prev[i] != -1 else ""
            # ensure alignment: show INF as 999 when unreachable
            disp_d = d if d < INF else INF
            print(f"{i:<25}{disp_d:<12}{p}")
        print("")

    def print_forwarding_table(self, dist, prev):
        print("Forwarding table:")
        print("  Destination_Routerid         Next_hop_routerlabel\n")
        for dest in range(self.num_nodes):
            if dest == self.router_id:
                continue
            if dist[dest] >= INF:
                # unreachable
                continue

            # reconstruct path from self.router_id -> dest using prev[]
            path = []
            cur = dest
            while cur != -1:
                path.append(cur)
                if cur == self.router_id:
                    break
                cur = prev[cur]
            if not path or path[-1] != self.router_id:
                # no path found
                continue
            path.reverse()  # now path[0] == self.router_id, path[-1] == dest

            # next hop is path[1] if exists, else dest (direct)
            if len(path) >= 2:
                next_hop_id = path[1]
            else:
                next_hop_id = dest

            next_hop_label = chr(ord('A') + next_hop_id) if 0 <= next_hop_id < 26 else str(next_hop_id)
            print(f"     {dest:<25}{next_hop_label}")
        print("")

    # -------------------------
    # run threads
    # -------------------------
    def run(self):
        t_send = threading.Thread(target=self.sender, daemon=True)
        t_recv = threading.Thread(target=self.receiver, daemon=True)
        t_dij  = threading.Thread(target=self.dijkstra_thread, daemon=True)

        t_send.start()
        t_recv.start()
        t_dij.start()

        # main thread idle loop
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting router.")

# -------------------------
# MAIN
# -------------------------
def main():
    if len(sys.argv) != 4:
        print("Usage: python Router.py <routerid> <routerport> <configfile>")
        return

    router_id = int(sys.argv[1])
    router_port = int(sys.argv[2])
    config_file = sys.argv[3]

    r = Router(router_id, router_port, config_file)
    print(f"Router {router_id} starting on port {router_port} with config {config_file}")
    print(f"Neighbors: {r.neighbors}")
    r.run()

if __name__ == "__main__":
    main()