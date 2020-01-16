#!/usr/bin/env bash

export MOUNT_DEVICE=/piusb.bin
export MOUNT_DIR=/home/pi/usb

while true; do
    umount "$MOUNT_DEVICE"
    mount -o ro,loop,offset=4194304 "$MOUNT_DEVICE" "$MOUNT_DIR"
    ./arlo_sender.py --state-file files.txt "$MOUNT_DIR"
    sleep 1
done
