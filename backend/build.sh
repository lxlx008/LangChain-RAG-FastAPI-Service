#!/bin/bash
set -e

# 安装系统依赖
apt-get update && apt-get install -y libmagic1

# 安装 Python 依赖
pip install -e .
