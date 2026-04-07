"""
macOS build script for Simple Transfer File Server.

Usage:
    python setup.py py2app

Output: dist/Simple Transfer File Server.app

For Windows packaging, use PyInstaller with:
    pyinstaller "Simple Transfer File Server.spec"
"""

from setuptools import setup

APP     = ["main.py"]
OPTIONS = {
    "argv_emulation": False,          # Must be False for Tkinter apps on macOS
    "iconfile": None,
    "includes": [
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.scrolledtext",
        "tkinter.messagebox",
        "server_http",
        "server_tftp",
        "http.server",
        "socket",
        "struct",
        "threading",
        "queue",
        "os",
        "datetime",
    ],
    "packages": [],
    "excludes": [
        "unittest", "distutils",
        "pydoc", "doctest",
        "audioop", "ftplib", "imaplib",
        "nntplib", "poplib", "smtplib", "telnetlib",
    ],
    "plist": {
        "CFBundleName":             "Simple Transfer File Server",
        "CFBundleDisplayName":      "Simple Transfer File Server",
        "CFBundleIdentifier":       "com.backsimon88.simpletransferfile",
        "CFBundleVersion":          "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable":  True,
        "LSMinimumSystemVersion":   "10.13.0",
        "NSHumanReadableCopyright": "© 2026 backsimon88",
    },
}

setup(
    name="Simple Transfer File Server",
    app=APP,
    data_files=[],
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
