#!/usr/bin/env python3

import asyncio
import video_notifier
import logging
import argparse
import os
import ctypes
import ctypes.util

log = logging.getLogger(__name__)

async def exec(cmd, args):
    proc = await asyncio.create_subprocess_exec(cmd, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.error(stderr)
        raise Exception(f'Error running {cmd}')

async def main():
    logging.basicConfig(level=os.environ.get('LOGLEVEL', 'WARNING').upper())

    parser = argparse.ArgumentParser()
    parser.add_argument('videos_dir', help='Path to directory containing video files. Will also be treated as the mount point.', default='.')
    parser.add_argument('--state-file', help='File for state, to avoid reprocessing the same files', required=False, default=None)
    parser.add_argument('--mount-device', help='If specified, this device will be remounted to the videos_dir on each poll. Useful if this is running on an OTG device (Pi Zero).', default=None)
    parser.add_argument('--mount-options', help='Mount options, to be used to mount mount-device. (e.g. ro,offset)', default='ro')
    args = parser.parse_args()
    log.debug(args)

    AZURE_ENDPOINT = os.environ['AZURE_ENDPOINT']
    AZURE_API_KEY = os.environ['AZURE_API_KEY']
    IFTTT_KEY = os.environ['IFTTT_KEY']

    while True:
        try:
            if args.mount_device:
                try:
                    await exec('umount', [args.videos_dir])
                except:
                    pass
                await exec('mount', ['-o', args.mount_options, args.mount_device, args.videos_dir])
            await video_notifier.check_videos(AZURE_ENDPOINT, AZURE_API_KEY, IFTTT_KEY, args.videos_dir, args.state_file)
            await asyncio.sleep(1)
        except Exception as err:
            log.error(err)
            await asyncio.sleep(5)

asyncio.run(main())
