#!/bin/bash

proxy_pid=$(ps -ef | grep http2socks.py | grep -v grep | awk '{print $2}')
kill -9 ${proxy_pid}

pkill -TERM corplink-rs
