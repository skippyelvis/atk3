#!/bin/bash
if [ $EUID != 0 ]; then
    sudo -E "$0" "$@"
    exit $?
fi

python3 atk3driver.py "$@"
