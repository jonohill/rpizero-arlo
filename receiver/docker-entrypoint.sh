#!/usr/bin/env bash

python arlo_monitor.py \
    --state-file "$ARLO_STATE_FILE" \
    --mount-device "$ARLO_MOUNT_DEVICE" \
    --mount-options "$ARLO_MOUNT_OPTIONS" \
    "$ARLO_VIDEOS_DIR"
