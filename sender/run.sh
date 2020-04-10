#!/usr/bin/env bash

: ${MZ_STATE:=state.txt}
: ${MZ_DEV:=/piusb.bin}
: ${MZ_PATH:=/tmp/piusb}
: ${MZ_KEY:=test}
: ${MZ_URL:=}

fdisk_output="$(fdisk --list --bytes -o Start "$MZ_DEV")"
start_sectors=$(echo "$fdisk_output" | grep -A1 '^Start' | tail -n1 | awk '{$1=$1};1')
sector_size=$(echo "$fdisk_output" | grep '^Units' | awk '{print $(NF-1)}')
start_bytes=$(( $start_sectors * $sector_size ))

./arlo_sender.py \
    --state-file "$MZ_STATE" \
    --remount "$MZ_DEV" \
    --mount-options "ro,loop,offset=$start_bytes" \
    --header "x-key: $MZ_KEY" \
    "$MZ_PATH" "$MZ_URL"
