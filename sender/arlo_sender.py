#!/usr/bin/env python3

import shlex
import logging
import os
import requests
import aiohttp
import asyncio
from time import time
import re
from datetime import timedelta

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get('LOGLEVEL', 'WARNING').upper())

RE_DURATION = re.compile(r'Duration: (\d+):(\d+):(\d+)\.(\d+)')

async def send_video(url, vid_path):
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
                http_response = await http.post(url, data=ff_proc.stdout, params={'duration': duration})
                log.debug(f'Video POST took {time()-post_start}s')

            for f in asyncio.as_completed([post_video(), ff_proc.wait(), ff_proc.stderr.read()]):
                await f
            log.debug(f'HTTP response code: {http_response.status}')
            http_response.raise_for_status()
    log.debug(f'Video took {time()-start}s')
        
async def send_new_videos(vid_dir, state={}):
    # Enumerate all video files
    dirs_to_scan = [vid_dir]
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
                            start = time()
                            await send_video(entry.path)
                            state[entry.path] = file_size
                            log.info(f'Video took {time()-start}s')
    return state

async def send_videos_forever(vid_dir, state_file=None):
    state = {}
    if state_file:
        try:
            with open(state_file, 'r') as f:
                num = 0
                for line in f:
                    state_line = shlex.split(line.strip())
                    state[state_line[0]] = int(state_line[1])
                    num += 1
                log.info(f'Read state for {num} existing files')
        except FileNotFoundError:
            log.debug('No state file')

    try:
        while True:
            try:
                state = await send_new_videos(vid_dir, state)
                await asyncio.sleep(1)
            except Exception as err:
                log.error('Sending videos failed, backing off...')
                log.debug(err)
                await asyncio.sleep(10)

    finally:
        if state_file:
            with open(state_file, 'w') as f:
                for file_path, file_size in state.items():
                    f.write(f'{shlex.quote(file_path)} {file_size}\n')

if __name__ == "__main__":
    # asyncio.run(send_videos_forever('.'))
    # asyncio.run(send_video('poetry.lock'))
    asyncio.run(send_video('http://localhost:8080/video', '../arlo-sample.mp4'))
