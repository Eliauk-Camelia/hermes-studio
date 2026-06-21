#!/bin/bash
# 开发模式启动 Electron 壳
cd "$(dirname "$0")/electron"
exec electron main.js
