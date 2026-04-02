#!/bin/bash
cd "$(dirname "$0")" || exit
python3 -m venv .env
source .env/bin/activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
#source gen_cert.sh
#python3 upd.py --init-db
