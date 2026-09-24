#!/usr/bin/env python3
"""HTTP (CONNECT) proxy bridging to the corplink-rs SOCKS5 proxy.

Claude Code only supports HTTP(S) proxies (no SOCKS), so this bridge accepts
HTTP CONNECT (and absolute-URI plain HTTP) requests on a local port and
forwards them through the SOCKS5 proxy exposed by corplink-rs in netstack
mode. Hostnames are passed to the SOCKS5 proxy verbatim, so DNS resolves
inside the VPN tunnel (socks5h semantics) — corporate-internal domains work.

Credentials for the SOCKS5 proxy are read from the corplink-rs config file
whenever a new upstream connection is made, so config changes apply without
restarting the bridge.

Usage:
    python3 http2socks.py [-p PORT] [-c CONFIG]
        -p/--port    local listen port (default 8118)
        -c/--config  corplink-rs config file (default: config.json
                     in this script's directory)
"""
import argparse
import json
import os
import select
import socket
import struct
import threading
from urllib.parse import urlsplit

SOCKS_ADDR = ("0.0.0.0", 1080)
CONF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 8118
IDLE_TIMEOUT = 300  # seconds without traffic before a tunnel is dropped


def load_socks_creds():
    try:
        conf = json.load(open(CONF_FILE))
        return conf.get("socks5_username") or "", conf.get("socks5_password") or ""
    except (OSError, ValueError):
        return "", ""


def socks5_dial(host, port):
    user, pwd = load_socks_creds()
    s = socket.create_connection(SOCKS_ADDR, timeout=20)
    try:
        if user:
            s.sendall(b"\x05\x02\x00\x02")
            m = s.recv(2)
            if m[1] != 0x02:
                raise OSError("socks5: server refused user/pass auth")
            s.sendall(b"\x01" + bytes([len(user)]) + user.encode()
                      + bytes([len(pwd)]) + pwd.encode())
            r = s.recv(2)
            if len(r) < 2 or r[1] != 0:
                raise OSError("socks5: auth failed")
        else:
            s.sendall(b"\x05\x01\x00")
            m = s.recv(2)
            if len(m) < 2 or m[1] != 0x00:
                raise OSError("socks5: no acceptable auth method")
        # ATYP=domain: let the netstack resolver inside the VPN do the DNS
        d = host.encode("idna") if not host.isdigit() else host.encode()
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(d)]) + d + struct.pack(">H", port))
        resp = s.recv(10)
        if len(resp) < 2 or resp[1] != 0:
            code = resp[1] if len(resp) > 1 else -1
            raise OSError(f"socks5: connect failed, reply code {code}")
        return s
    except OSError:
        s.close()
        raise


def pipe(a, b):
    socks = [a, b]
    while True:
        r, _, x = select.select(socks, [], socks, IDLE_TIMEOUT)
        if x or not r:
            return
        for s in r:
            try:
                data = s.recv(65536)
            except OSError:
                return
            if not data:
                return
            try:
                (b if s is a else a).sendall(data)
            except OSError:
                return


def handle(client):
    upstream = None
    try:
        client.settimeout(30)
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = client.recv(65536)
            if not chunk:
                return
            req += chunk
            if len(req) > 1 << 16:
                return
        line = req.split(b"\r\n", 1)[0].decode("latin1")
        parts = line.split()
        if len(parts) >= 2 and parts[0].upper() == "CONNECT":
            host, _, port = parts[1].rpartition(":")
            host = host.strip("[]")
            upstream = socks5_dial(host, int(port) if port.isdigit() else 443)
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            client.settimeout(None)
            pipe(client, upstream)
        elif len(parts) >= 2:
            # plain HTTP with absolute URI (rare; Claude Code uses HTTPS/CONNECT)
            target = urlsplit(parts[1])
            host = target.hostname or ""
            port = target.port or 80
            upstream = socks5_dial(host, port)
            upstream.sendall(req)
            client.settimeout(None)
            pipe(client, upstream)
        else:
            client.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
    except OSError as e:
        try:
            client.sendall(f"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n"
                           f"X-Bridge-Error: {e}\r\n\r\n".encode())
        except OSError:
            pass
    finally:
        for s in (client, upstream):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass


def main():
    global CONF_FILE
    ap = argparse.ArgumentParser(
        description="HTTP (CONNECT) proxy bridging to the corplink-rs SOCKS5 proxy.")
    ap.add_argument("-p", "--port", type=int, default=DEFAULT_LISTEN_PORT,
                    help=f"local port to listen on (default {DEFAULT_LISTEN_PORT})")
    ap.add_argument("-c", "--config", metavar="FILE", default=CONF_FILE,
                    help=f"corplink-rs config file (default: {CONF_FILE})")
    args = ap.parse_args()
    CONF_FILE = args.config
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, args.port))
    srv.listen(64)
    print(f"http2socks: {LISTEN_HOST}:{args.port} -> socks5://{SOCKS_ADDR[0]}:{SOCKS_ADDR[1]} "
          f"(config: {CONF_FILE})", flush=True)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
