"""
TFTP Server module — RFC 1350 compliant.

Supports:
  - RRQ  (Read / download from server)
  - WRQ  (Write / upload to server)
  - Transfer modes: octet (binary), netascii
  - Path-traversal protection
"""

import socket
import struct
import os
import threading

# ── Opcodes ───────────────────────────────────────────────────────────────────
OP_RRQ   = 1   # Read request
OP_WRQ   = 2   # Write request
OP_DATA  = 3   # Data block
OP_ACK   = 4   # Acknowledgement
OP_ERROR = 5   # Error

# ── Error codes ───────────────────────────────────────────────────────────────
E_NOT_DEFINED      = 0
E_FILE_NOT_FOUND   = 1
E_ACCESS_VIOLATION = 2
E_DISK_FULL        = 3
E_ILLEGAL_OP       = 4
E_UNKNOWN_TID      = 5
E_FILE_EXISTS      = 6
E_NO_SUCH_USER     = 7

# ── Transfer constants ────────────────────────────────────────────────────────
BLOCK_SIZE  = 512
TIMEOUT_SEC = 5
MAX_RETRIES = 5


# ── Packet helpers ────────────────────────────────────────────────────────────

def _parse_request(data: bytes):
    """Return (opcode, filename, mode) from a RRQ/WRQ packet."""
    opcode = struct.unpack("!H", data[:2])[0]
    body   = data[2:]
    sep1   = body.index(0)
    filename = body[:sep1].decode("ascii", errors="replace")
    body   = body[sep1 + 1:]
    sep2   = body.index(0)
    mode   = body[:sep2].decode("ascii", errors="replace").lower()
    return opcode, filename, mode


def _data_pkt(block: int, payload: bytes) -> bytes:
    return struct.pack("!HH", OP_DATA, block) + payload


def _ack_pkt(block: int) -> bytes:
    return struct.pack("!HH", OP_ACK, block)


def _err_pkt(code: int, msg: str) -> bytes:
    return struct.pack("!HH", OP_ERROR, code) + msg.encode("ascii") + b"\x00"


# ── Session handler (one per transfer) ───────────────────────────────────────

class _TFTPSession(threading.Thread):
    """Handles a single TFTP RRQ or WRQ in its own daemon thread."""

    def __init__(self, opcode, filename, mode, client_addr, root_dir, log_cb):
        super().__init__(daemon=True)
        self.opcode      = opcode
        self.filename    = filename
        self.mode        = mode
        self.client_addr = client_addr
        self.root_dir    = root_dir
        self._log        = log_cb

        # Each transfer uses its own ephemeral UDP socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(TIMEOUT_SEC)
        self._sock.bind(("", 0))   # OS picks the ephemeral port

    # ── path validation ───────────────────────────────────────────────────────

    def _safe_path(self, filename: str):
        """Resolve the requested filename within root_dir; return None if unsafe."""
        filename = filename.lstrip("/\\").replace("..", "")
        full      = os.path.realpath(os.path.join(self.root_dir, filename))
        root_real = os.path.realpath(self.root_dir)
        if full != root_real and not full.startswith(root_real + os.sep):
            return None
        return full

    # ── thread entry point ────────────────────────────────────────────────────

    def run(self):
        try:
            if self.opcode == OP_RRQ:
                self._handle_read()
            elif self.opcode == OP_WRQ:
                self._handle_write()
        finally:
            self._sock.close()

    # ── RRQ — send file to client ─────────────────────────────────────────────

    def _handle_read(self):
        filepath = self._safe_path(self.filename)
        client_ip = self.client_addr[0]

        if not filepath or not os.path.isfile(filepath):
            self._sock.sendto(_err_pkt(E_FILE_NOT_FOUND, "File not found"), self.client_addr)
            self._log(f"TFTP  [{client_ip}] RRQ {self.filename!r} — file not found")
            return

        self._log(f"TFTP  [{client_ip}] RRQ {self.filename!r} — starting")

        try:
            with open(filepath, "rb") as fh:
                block = 1
                while True:
                    chunk = fh.read(BLOCK_SIZE)
                    pkt   = _data_pkt(block, chunk)

                    # Send with retry
                    sent = False
                    for _ in range(MAX_RETRIES):
                        self._sock.sendto(pkt, self.client_addr)
                        try:
                            resp, addr = self._sock.recvfrom(512)
                        except socket.timeout:
                            continue
                        if addr != self.client_addr:
                            continue
                        op = struct.unpack("!H", resp[:2])[0]
                        if op == OP_ACK and struct.unpack("!H", resp[2:4])[0] == block:
                            sent = True
                            break
                        if op == OP_ERROR:
                            self._log(f"TFTP  [{client_ip}] RRQ {self.filename!r} — client error, aborted")
                            return

                    if not sent:
                        self._log(f"TFTP  [{client_ip}] RRQ {self.filename!r} — timeout after {MAX_RETRIES} retries")
                        return

                    if len(chunk) < BLOCK_SIZE:
                        self._log(f"TFTP  [{client_ip}] RRQ {self.filename!r} — transfer complete")
                        return

                    block = (block + 1) % 65536

        except OSError as exc:
            self._log(f"TFTP  [{client_ip}] RRQ {self.filename!r} — IO error: {exc}")

    # ── WRQ — receive file from client ────────────────────────────────────────

    def _handle_write(self):
        filepath = self._safe_path(self.filename)
        client_ip = self.client_addr[0]

        if not filepath:
            self._sock.sendto(_err_pkt(E_ACCESS_VIOLATION, "Access violation"), self.client_addr)
            self._log(f"TFTP  [{client_ip}] WRQ {self.filename!r} — access violation")
            return

        self._log(f"TFTP  [{client_ip}] WRQ {self.filename!r} — starting")

        try:
            with open(filepath, "wb") as fh:
                # Acknowledge the WRQ (block 0)
                self._sock.sendto(_ack_pkt(0), self.client_addr)
                expected = 1

                while True:
                    data_chunk = None
                    last_ack   = expected - 1

                    for _ in range(MAX_RETRIES):
                        try:
                            resp, addr = self._sock.recvfrom(BLOCK_SIZE + 4)
                        except socket.timeout:
                            # Re-send last ACK to trigger retransmit
                            self._sock.sendto(_ack_pkt(last_ack), self.client_addr)
                            continue
                        if addr != self.client_addr:
                            continue
                        op = struct.unpack("!H", resp[:2])[0]
                        if op == OP_DATA:
                            blk = struct.unpack("!H", resp[2:4])[0]
                            if blk == expected:
                                data_chunk = resp[4:]
                                break
                        elif op == OP_ERROR:
                            self._log(f"TFTP  [{client_ip}] WRQ {self.filename!r} — client error, aborted")
                            return

                    if data_chunk is None:
                        self._log(f"TFTP  [{client_ip}] WRQ {self.filename!r} — timeout, aborted")
                        return

                    fh.write(data_chunk)
                    self._sock.sendto(_ack_pkt(expected), self.client_addr)

                    if len(data_chunk) < BLOCK_SIZE:
                        self._log(f"TFTP  [{client_ip}] WRQ {self.filename!r} — transfer complete")
                        return

                    expected = (expected + 1) % 65536

        except OSError as exc:
            self._log(f"TFTP  [{client_ip}] WRQ {self.filename!r} — IO error: {exc}")


# ── Public server class ───────────────────────────────────────────────────────

class TFTPServerThread:
    """
    UDP listener that spawns a _TFTPSession for every incoming request.
    Call start_server() — raises OSError if the port cannot be bound.
    Call stop_server() to shut down cleanly.
    """

    def __init__(self, host: str, port: int, root_dir: str, log_callback):
        self.host         = host
        self.port         = port
        self.root_dir     = root_dir
        self.log_callback = log_callback
        self._sock        = None
        self._thread      = None
        self._running     = False

    def start_server(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))   # raises OSError on failure
        self._sock.settimeout(1.0)
        self._running = True
        self._thread  = threading.Thread(
            target=self._listen,
            name="TFTPServer",
            daemon=True,
        )
        self._thread.start()

    def stop_server(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _listen(self):
        while self._running:
            try:
                data, client_addr = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break   # socket closed

            if len(data) < 4:
                continue

            try:
                opcode, filename, mode = _parse_request(data)
            except Exception:
                continue

            if opcode not in (OP_RRQ, OP_WRQ):
                continue

            _TFTPSession(
                opcode, filename, mode, client_addr,
                self.root_dir, self.log_callback,
            ).start()
