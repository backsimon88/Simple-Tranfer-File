"""
HTTP Server module — serves files from a root directory.
Uses Python's built-in http.server with directory listing enabled.
"""

import http.server
import threading
import os


class _LoggingHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler that forwards log messages to the GUI callback."""

    log_callback = None   # class-level slot, overridden per-instance via factory

    def __init__(self, *args, log_callback=None, directory=None, **kwargs):
        self._log_cb = log_callback
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, fmt, *args):
        msg = f"HTTP  [{self.client_address[0]}] {fmt % args}"
        if self._log_cb:
            self._log_cb(msg)

    def log_error(self, fmt, *args):
        msg = f"HTTP  [{self.client_address[0]}] ERROR {fmt % args}"
        if self._log_cb:
            self._log_cb(msg)


class HTTPServerThread:
    """Wraps Python's HTTPServer in a background daemon thread."""

    def __init__(self, host: str, port: int, root_dir: str, log_callback):
        self.host = host
        self.port = port
        self.root_dir = root_dir
        self.log_callback = log_callback
        self._server = None
        self._thread = None

    def start_server(self):
        """Bind the socket and start serving (raises OSError on failure)."""
        log_cb = self.log_callback
        root = self.root_dir

        def handler_factory(*args, **kwargs):
            return _LoggingHandler(*args, log_callback=log_cb, directory=root, **kwargs)

        self._server = http.server.HTTPServer((self.host, self.port), handler_factory)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="HTTPServer",
            daemon=True,
        )
        self._thread.start()

    def stop_server(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._thread = None
