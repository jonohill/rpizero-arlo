# Motion Zero

A project to detect interesting things from video files and notify. Intended use is to run on a Raspberry Pi Zero directly connected to an Arlo base station (see below) but it can operate anywhere that video files are placed.

## Intended use

A Raspberry Pi Zero can emulate a USB mass storage device. Therefore, when configured correctly and connected to (some models of) an Arlo base station, this script can be run in a tight loop to check for interesting video clips in near real time.

https://docs.microsoft.com/en-us/azure/cognitive-services/cognitive-services-apis-create-account?tabs=multiservice%2Cwindows