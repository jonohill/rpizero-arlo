#!/usr/bin/env python3

import shlex
import logging
import os
import requests
import aiohttp
import asyncio
import argparse
from time import time
import re
from datetime import timedelta
import sys

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get('LOGLEVEL', 'WARNING').upper())

RE_DURATION = re.compile(r'Duration: (\d+):(\d+):(\d+)\.(\d+)')

async def exec(cmd, args):
    proc = await asyncio.create_subprocess_exec(cmd, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.error(stderr)
        raise Exception(f'Error running {cmd}')

class ArloSender:

    def __init__(self, video_dir, url, headers={}, state_file=None, max_concurrent=2):
        self.video_dir = video_dir
        self.url = url
        self.headers = headers
        self.state_file = state_file
        self.send_semaphore = asyncio.Semaphore(max_concurrent)

    async def send_video(self, vid_path):
        with self.send_semaphore:
            start = time()
            ff_proc = await asyncio.create_subprocess_exec('ffmpeg', '-i', vid_path, '-acodec', 'copy', '-vcodec', 'copy', '-f', 'mpegts', '-', 
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

            # Read stderr until the duration is printed. This also means we can know if it's a valid video or not.
            duration = None
            err_lines = []
            while (ff_proc.returncode is None) and (duration is None) and (not ff_proc.stderr.at_eof()):
                err_line = (await ff_proc.stderr.readline()).decode()
                err_lines.append(err_line)
                re_result = RE_DURATION.search(err_line)
                if re_result:
                    h, m, s, ms = re_result.groups()
                    duration = int(timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms)) / timedelta(milliseconds=1))
                    log.debug(f'Video duration is {duration}ms')

            if not duration:
                log.info(f'{vid_path} is not a video')
                log.debug(''.join(err_lines) + '\n' + (await ff_proc.stderr.read()).decode())
                await ff_proc.stdout.read() # clear buffer
            else:
                log.debug(f'Duration took {time()-start}')
                async with aiohttp.ClientSession() as http:
                    http_response = None
                    async def post_video():
                        post_start = time()
                        nonlocal http_response
                        http_response = await http.post(self.url, data=ff_proc.stdout, params={'duration': duration}, headers=self.headers)
                        log.debug(f'Video POST took {time()-post_start}s')

                    for f in asyncio.as_completed([post_video(), ff_proc.wait(), ff_proc.stderr.read()]):
                        await f
                    log.debug(f'HTTP response code: {http_response.status}')
                    http_response.raise_for_status()
            log.debug(f'Video took {time()-start}s')
        
    async def send_new_videos(self, state={}):
        '''Send any videos not in state, returning new state only if modified'''
        state_changed = False
        # Enumerate all video files
        dirs_to_scan = [self.video_dir]
        pending_tasks = []
        while dirs_to_scan:
            these_dirs = dirs_to_scan.copy()
            dirs_to_scan = []
            for dir in these_dirs:
                with os.scandir(dir) as dir_it:
                    for entry in dir_it:
                        if entry.is_dir():
                            dirs_to_scan.append(entry.path)
                        elif entry.is_file():
                            file_size = entry.stat().st_size
                            if state.get(entry.path, 0) != file_size:
                                pending_tasks.append(self.send_video(entry.path))
                                state[entry.path] = file_size
                                state_changed = True

        try:
            for t in asyncio.as_completed(pending_tasks):
                await t
        except aiohttp.ClientResponseError as err:
            log.warning(f'Server returned {err.status}')
            if err.status >= 500:
                raise

        if state_changed:
            return state

    async def send_videos_forever(self):
        '''Generator (of None), send videos as long as generating'''
        state = {}
        if self.state_file:
            try:
                with open(self.state_file, 'r') as f:
                    num = 0
                    for line in f:
                        state_line = shlex.split(line.strip())
                        state[state_line[0]] = int(state_line[1])
                        num += 1
                    log.info(f'Read state for {num} existing files')
            except FileNotFoundError:
                log.debug('No state file')

        def save_state():
            if self.state_file:
                with open(self.state_file, 'w') as f:
                    for file_path, file_size in state.items():
                        f.write(f'{shlex.quote(file_path)} {file_size}\n')

        try:
            while True:
                try:
                    new_state = await self.send_new_videos(state)
                    # Only save state once no new videos processed
                    if new_state:
                        state = new_state
                    else:
                        save_state()
                except Exception as err:
                    log.error('Sending videos failed, backing off...')
                    log.debug(err)
                    await asyncio.sleep(10)
                yield

        finally:
            save_state()

    async def send_videos_every_seconds(self, seconds=1):
        '''Check/send videos every n seconds'''
        async for _ in self.send_videos_forever():
            await asyncio.sleep(seconds)

    async def send_videos_forever_with_remount(self, mount_device, mount_options, seconds=1):
        
        async def mount():
            await exec('mount', ['-o', mount_options, mount_device, self.video_dir])
        
        async def unmount():
            try:
                await exec('umount', [self.video_dir])
            except:
                pass

        try:
            await unmount()
            await mount()
            async for _ in self.send_videos_forever():
                await unmount()
                await asyncio.sleep(seconds)
                await mount()
        finally:
            await unmount()

async def _main():
    def header(str_val):
        vals = [ s.strip() for s in str_val.split(':') ]
        if len(vals) != 2:
            raise ValueError()
        return vals[0], vals[1]
    
    parser = argparse.ArgumentParser()
    parser.add_argument('video_dir')
    parser.add_argument('url')
    parser.add_argument('--state-file')
    parser.add_argument('--header', '-H', help='Add header value to request. Curl syntax, i.e. "header-name: value"', action='append', type=header)
    parser.add_argument('--remount', help='(Re-)mount this device before reading each batch')
    parser.add_argument('--mount-options', help='Mount options, for use with remount device', default='ro')
    args = parser.parse_args()
    headers = { k: v for k, v in args.header } if args.header else {}

    sender = ArloSender(args.video_dir, args.url, headers, args.state_file)
    if args.remount:
        await sender.send_videos_forever_with_remount(args.remount, args.mount_options)
    else:
        await sender.send_videos_every_seconds(1)
    
if __name__ == "__main__":
    asyncio.run(_main())
