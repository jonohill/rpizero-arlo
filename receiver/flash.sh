#!/usr/bin/env bash

git clone https://github.com/hypriot/flash.git
pushd flash
git pull
popd
envsubst <cloud-init.yaml >cloud-init.tmp
./flash/flash --userdata cloud-init.tmp https://github.com/hypriot/image-builder-rpi/releases/download/v1.11.4/hypriotos-rpi-v1.11.4.img.zip
rm cloud-init.tmp
