"""
Simple Transfer File Server
A Tftpd64-like desktop tool: run HTTP + TFTP servers from a single GUI.

Requirements: Python 3.8+ (only stdlib, no pip packages needed)
Run: python main.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import socket
import os
import queue
from datetime import datetime

from server_http import HTTPServerThread
from server_tftp import TFTPServerThread


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_local_ips():
    """Return a list of IPv4 addresses on this machine, most useful first."""
    ips = []
    # Primary outbound IP first (no actual connection made)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip:
            ips.append(ip)
    except Exception:
        pass
    # All interface addresses
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    for fallback in ("127.0.0.1", "0.0.0.0"):
        if fallback not in ips:
            ips.append(fallback)
    return ips


# ── Main application window ───────────────────────────────────────────────────

class App(tk.Tk):

    _STATUS_STOPPED = "● Stopped"
    _STATUS_RUNNING = "● Running"
    _COLOR_STOPPED  = "#888888"
    _COLOR_RUNNING  = "#27ae60"
    _COLOR_BG_LOG   = "#1e1e1e"
    _COLOR_FG_LOG   = "#d4d4d4"

    def __init__(self):
        super().__init__()
        self.title("Simple Transfer File Server")
        self.geometry("740x600")
        self.minsize(660, 520)
        self.resizable(True, True)

        self._http_thread = None
        self._tftp_thread = None
        self._log_queue   = queue.Queue()

        self._build_ui()
        self._poll_log()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._style_setup()
        self._build_toolbar()
        self._build_server_panels()
        self._build_log_area()

    def _style_setup(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TLabelframe.Label", font=("Arial", 10, "bold"))
        s.configure("Header.TLabel",     font=("Arial", 9,  "bold"))
        s.configure(
            "Start.TButton",
            font=("Arial", 9, "bold"),
            foreground="#ffffff",
            background="#2980b9",
            padding=5,
        )
        s.configure(
            "Stop.TButton",
            font=("Arial", 9, "bold"),
            foreground="#ffffff",
            background="#c0392b",
            padding=5,
        )
        s.map("Start.TButton", background=[("active", "#3498db"), ("disabled", "#bdc3c7")])
        s.map("Stop.TButton",  background=[("active", "#e74c3c"), ("disabled", "#bdc3c7")])

    def _build_toolbar(self):
        """Root-directory selector bar."""
        frame = ttk.LabelFrame(self, text="Root Directory (Shared Folder)", padding=8)
        frame.pack(fill="x", padx=12, pady=(12, 4))

        self._root_dir_var = tk.StringVar(value=os.path.expanduser("~"))
        entry = ttk.Entry(frame, textvariable=self._root_dir_var, font=("Arial", 9))
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(
            frame, text="  Browse…  ", command=self._browse_dir
        ).pack(side="left", padx=(8, 0))

    def _build_server_panels(self):
        outer = ttk.Frame(self)
        outer.pack(fill="x", padx=12, pady=4)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)

        self._build_http_panel(outer)
        self._build_tftp_panel(outer)

    def _build_http_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="HTTP Server", padding=12)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        frame.columnconfigure(1, weight=1)

        ips = _get_local_ips()
        self._http_ip_var   = tk.StringVar(value=ips[0])
        self._http_port_var = tk.StringVar(value="8080")

        ttk.Label(frame, text="IP Address:", style="Header.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Combobox(
            frame, textvariable=self._http_ip_var, values=ips, width=20, state="readonly"
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(frame, text="Port:", style="Header.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self._http_port_var, width=8).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        self._http_status_lbl = tk.Label(
            frame, text=self._STATUS_STOPPED,
            fg=self._COLOR_STOPPED, bg=self.cget("bg"),
            font=("Arial", 9, "bold"),
        )
        self._http_status_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 6))

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew")

        self._http_start_btn = ttk.Button(
            btn_row, text="▶  Start HTTP", style="Start.TButton", command=self._start_http)
        self._http_start_btn.pack(side="left", fill="x", expand=True)

        self._http_stop_btn = ttk.Button(
            btn_row, text="■  Stop", style="Stop.TButton",
            command=self._stop_http, state="disabled")
        self._http_stop_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_tftp_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="TFTP Server", padding=12)
        frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        frame.columnconfigure(1, weight=1)

        ips = _get_local_ips()
        self._tftp_ip_var   = tk.StringVar(value=ips[0])
        self._tftp_port_var = tk.StringVar(value="69")

        ttk.Label(frame, text="IP Address:", style="Header.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Combobox(
            frame, textvariable=self._tftp_ip_var, values=ips, width=20, state="readonly"
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(frame, text="Port:", style="Header.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        port_frame = ttk.Frame(frame)
        port_frame.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(port_frame, textvariable=self._tftp_port_var, width=8).pack(side="left")
        ttk.Label(
            port_frame, text=" (69 needs sudo on macOS/Linux)",
            font=("Arial", 8), foreground="#888"
        ).pack(side="left")

        self._tftp_status_lbl = tk.Label(
            frame, text=self._STATUS_STOPPED,
            fg=self._COLOR_STOPPED, bg=self.cget("bg"),
            font=("Arial", 9, "bold"),
        )
        self._tftp_status_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 6))

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew")

        self._tftp_start_btn = ttk.Button(
            btn_row, text="▶  Start TFTP", style="Start.TButton", command=self._start_tftp)
        self._tftp_start_btn.pack(side="left", fill="x", expand=True)

        self._tftp_stop_btn = ttk.Button(
            btn_row, text="■  Stop", style="Stop.TButton",
            command=self._stop_tftp, state="disabled")
        self._tftp_stop_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_log_area(self):
        log_frame = ttk.LabelFrame(self, text="Activity Log", padding=6)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self._log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Courier", 9),
            state="disabled",
            wrap="word",
            bg=self._COLOR_BG_LOG,
            fg=self._COLOR_FG_LOG,
            insertbackground="white",
            relief="flat",
        )
        self._log_text.pack(fill="both", expand=True)

        bar = ttk.Frame(log_frame)
        bar.pack(fill="x", pady=(4, 0))
        ttk.Button(bar, text="Clear Log", command=self._clear_log).pack(side="right")

    # ── Directory browser ─────────────────────────────────────────────────────

    def _browse_dir(self):
        current = self._root_dir_var.get()
        directory = filedialog.askdirectory(
            title="Select Root / Shared Directory",
            initialdir=current if os.path.isdir(current) else os.path.expanduser("~"),
        )
        if directory:
            self._root_dir_var.set(directory)

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        """Thread-safe: put a message on the queue for the GUI thread to write."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_queue.put(f"[{ts}]  {msg}")

    def _poll_log(self):
        """Drain the log queue into the ScrolledText widget every 100 ms."""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._log_text.configure(state="normal")
                self._log_text.insert("end", msg + "\n")
                self._log_text.see("end")
                self._log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ── HTTP controls ─────────────────────────────────────────────────────────

    def _start_http(self):
        root_dir = self._root_dir_var.get()
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Root directory does not exist.")
            return
        try:
            port = int(self._http_port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "HTTP port must be an integer between 1 and 65535.")
            return

        ip = self._http_ip_var.get()
        self._http_thread = HTTPServerThread(ip, port, root_dir, self._log)
        try:
            self._http_thread.start_server()
        except OSError as exc:
            messagebox.showerror("Cannot start HTTP server", str(exc))
            self._http_thread = None
            return

        self._http_status_lbl.config(
            text=f"{self._STATUS_RUNNING}  —  {ip}:{port}",
            fg=self._COLOR_RUNNING,
        )
        self._http_start_btn.configure(state="disabled")
        self._http_stop_btn.configure(state="normal")
        self._log(f"HTTP server started  →  http://{ip}:{port}/   root: {root_dir}")

    def _stop_http(self):
        if self._http_thread:
            self._http_thread.stop_server()
            self._http_thread = None
        self._http_status_lbl.config(text=self._STATUS_STOPPED, fg=self._COLOR_STOPPED)
        self._http_start_btn.configure(state="normal")
        self._http_stop_btn.configure(state="disabled")
        self._log("HTTP server stopped.")

    # ── TFTP controls ─────────────────────────────────────────────────────────

    def _start_tftp(self):
        root_dir = self._root_dir_var.get()
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Root directory does not exist.")
            return
        try:
            port = int(self._tftp_port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "TFTP port must be an integer between 1 and 65535.")
            return

        ip = self._tftp_ip_var.get()
        self._tftp_thread = TFTPServerThread(ip, port, root_dir, self._log)
        try:
            self._tftp_thread.start_server()
        except PermissionError:
            messagebox.showerror(
                "Permission denied",
                f"Cannot bind to port {port}.\n\n"
                "Port 69 requires administrator/root privileges.\n"
                "Try a port above 1024 (e.g. 6969) or run as sudo.",
            )
            self._tftp_thread = None
            return
        except OSError as exc:
            messagebox.showerror("Cannot start TFTP server", str(exc))
            self._tftp_thread = None
            return

        self._tftp_status_lbl.config(
            text=f"{self._STATUS_RUNNING}  —  {ip}:{port}",
            fg=self._COLOR_RUNNING,
        )
        self._tftp_start_btn.configure(state="disabled")
        self._tftp_stop_btn.configure(state="normal")
        self._log(f"TFTP server started  →  {ip}:{port}   root: {root_dir}")

    def _stop_tftp(self):
        if self._tftp_thread:
            self._tftp_thread.stop_server()
            self._tftp_thread = None
        self._tftp_status_lbl.config(text=self._STATUS_STOPPED, fg=self._COLOR_STOPPED)
        self._tftp_start_btn.configure(state="normal")
        self._tftp_stop_btn.configure(state="disabled")
        self._log("TFTP server stopped.")

    # ── Window close ──────────────────────────────────────────────────────────

    def _on_close(self):
        self._stop_http()
        self._stop_tftp()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
