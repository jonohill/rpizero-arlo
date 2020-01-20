#!/usr/bin/env bash

./arlo_sender.py \
    --state-file files.txt \
    --remount /piusb.bin \
    --mount-options "ro,loop,offset=4194304" \
    --header "x-key: $ARLO_KEY" \
    "/home/pi/usb" "$ARLO_URL"
