# use on linux remote server

1. clone and build
```shell
git clone https://github.com/small-cat/corplink-rs.git
```

install cargo/rustc
```shell
sudo apt-cache search cargo
sudo apt-get install cargo # select the right version, for example: cargo-1.91
```

set the following env variables first, otherwise go get will encounter the timeout errors
```shell
go env -w GO111MODULE=on
go env -w GOPROXY=https://goproxy.cn,direct
go env -w GOSUMDB=off
```

compile
```shell
cd corplink-rs
git submodule update --init --recursive

cd libwg
./build.sh

cd .. # back to root of corplink-rs source directory
cargo build --release
```

the complied outputs located in `target/release`

2. start
copy scripts to target/release

```shell
cp scripts/http2socks.py target/release
cp scripts/startup.sh target/release
cp scripts/stop.sh target/release

cd target/release
# first time start corplink-rs service manually
./corplink-rs config.json
# click the url or scan qrcode with feishu app, and authorize on the app, then click enter to keep corplink-rs going on 

# next time to start with ./startup.sh directly

# stop use ./stop.sh
```

3. set env vars before use claude
```shell
export HTTPS_PROXY="http://127.0.0.1:8118"
export NO_PROXY="localhost,127.0.0.1,open.bigmodel.cn,api.anthropic.com"
```
