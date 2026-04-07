# Simple Transfer File Server

A lightweight macOS desktop app (Tkinter) that runs both:
- HTTP file server
- TFTP server (RFC 1350)

The app is designed for quickly sharing firmware/config files to network devices, similar to Tftpd64 workflows.

## Features

- Start/Stop HTTP and TFTP independently
- Select shared root folder from GUI
- Real-time activity log
- TFTP supports:
  - RRQ (download)
  - WRQ (upload)
- Basic path traversal protection for TFTP
- Packaged macOS `.app` included in `release/`

## Project Structure

- `main.py`: Tkinter GUI app
- `server_http.py`: HTTP server module
- `server_tftp.py`: TFTP server module
- `setup.py`: py2app build configuration
- `release/Simple Transfer File Server.app`: macOS app bundle
- `release/Simple-Transfer-File-Server-macOS.zip`: distributable zip

## Run From Source

Requirements:
- Python 3.8+
- `tkinter` available

Run:

```bash
python3 main.py
```

## Build macOS .app

```bash
python3 setup.py py2app
```

Output:
- `dist/Simple Transfer File Server.app`

## Use Prebuilt App

Use one of these artifacts:
- `release/Simple Transfer File Server.app`
- `release/Simple-Transfer-File-Server-macOS.zip`

If macOS warns on first open:
1. Right-click app
2. Open
3. Open again

## Networking Notes

- TFTP uses UDP, not TCP
- Port `69` needs admin/root privileges on macOS/Linux
- If needed, use port `6969` instead

## Quick Test

HTTP:
- Start HTTP in the app
- Open `http://<server-ip>:8080/`

TFTP (example):

```bash
tftp <server-ip> 6969 -c get <filename>
```

## License

MIT (you can change this as needed)
