#!/bin/bash

# start http2socks
# claude does not support sock5 protocol, should redirect http to sock5 with proxy
nohup python http2socks.py &> log1 &

# start corplink-rs
nohup ./corplink-rs $PWD/config.json &

# test service
# HTTPS_PROXY=http://127.0.0.1:8118 NO_PROXY="localhost,127.0.0.1,open.bigmodel.cn,api.anthropic.com" curl https://api-gateway.glm.ai/v1/chat/completions   -H "Content-Type: application/json"   -H 'Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxx'   -d '{
#   "model": "gpt-5.5",
#   "messages": [
#     {
#       "role": "user",
#       "content": "Hello!"
#     }
#   ]
# }'
