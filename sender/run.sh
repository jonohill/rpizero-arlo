#!/usr/bin/env bash

export MOUNT_DEVICE=/piusb.bin
export MOUNT_DIR=/home/pi/usb

(while true; do
    umount "$MOUNT_DEVICE"
    sleep 1
    mount -o ro,loop,offset=4194304 "$MOUNT_DEVICE" "$MOUNT_DIR"    
    # Sending line triggers the script to check for videos
    echo 
done) | ./arlo_sender.py --state-file files.txt --on-enter --header "x-key: $ARLO_KEY" "$MOUNT_DIR" "$ARLO_URL"
