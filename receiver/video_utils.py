import asyncio
from asyncio import StreamReader, subprocess
from subprocess import PIPE
import logging
from itertools import chain
import json
from typing import AsyncGenerator
import io
import traceback
import re
from time import time

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def _check_result(returncode, stderr):
    if returncode != 0:
        log.info(f'ffmpeg return code {returncode}')
        log.info(stderr)
        raise Exception('ffmpeg failed')

async def _exec(program, args):
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    _check_result(proc.returncode, stderr)
    return stdout

async def generate_bmps(bmps_streamreader: StreamReader):
    '''Given a stream containing raw bitmap files, yield each as byte array'''

    def check_eof():
        if bmps_streamreader.at_eof():
            raise EOFError()

    try:
        while True:
            bmp_data = io.BytesIO()

            magic_number = await bmps_streamreader.read(2)
            check_eof()
            if magic_number != b'BM':
                raise Exception('Corrupted stream or not a bitmap')
            bmp_data.write(magic_number)

            size_bytes = await bmps_streamreader.read(4)
            check_eof()
            bmp_data.write(size_bytes)
            # minus 6 to account for already read bytes
            size = int.from_bytes(size_bytes, byteorder='little') - 6

            read_count = 0
            while not bmps_streamreader.at_eof() and read_count < size:
                chunk = await bmps_streamreader.read(size - read_count)
                read_count += len(chunk)
                bmp_data.write(chunk)

            yield bmp_data.getvalue()
    except EOFError:
        log.debug('eof')
        pass

async def extract_frames(input_chunk_generator, realtime=True) -> AsyncGenerator[bytearray, None]:
    '''if realtime=True, extract frames as fast as possible, but skip frames if read slower than realtime.'''    

    args = [
        'ffmpeg', 
        '-i', '-',
        '-an',
        '-vcodec', 'bmp',
        '-f', 'rawvideo',
        '-'
    ]
    log.debug(args)
    proc: asyncio.Process = await asyncio.create_subprocess_exec(*args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    
    stderr = ''
    fps = 0
    try:

        async def send_stdin():
            async for chunk in input_chunk_generator:
                proc.stdin.write(chunk)
                await proc.stdin.drain()
            if proc.stdin.can_write_eof():
                proc.stdin.write_eof()

        async def read_stderr():
            nonlocal stderr
            nonlocal fps
            re_fps = re.compile(r'(\d+(?:\.\d+)?)\sfps')

            reader = proc.stderr
            while not reader.at_eof():
                try:
                    line_bytes = await reader.readuntil()
                except asyncio.LimitOverrunError as err:
                    line_bytes = await reader.read(err.consumed)
                except asyncio.IncompleteReadError as err:
                    line_bytes = err.partial
                line = line_bytes.decode('utf-8')
                stderr += line

                if not fps:
                    fps_match = re_fps.search(line)
                    if fps_match:
                        fps = float(fps_match.group(1))
                        log.debug(f'fps is {fps}')

        last_frame = None
        frame_event = asyncio.Event()
        start = last_frame_time = time()
        frame_n = 0
        last_frame_n = 0
        async def read_stdout():
            nonlocal last_frame
            nonlocal last_frame_time
            nonlocal frame_n
            async for frame in generate_bmps(proc.stdout):
                if fps and realtime:
                    expected_time = last_frame_time + ((1 / fps) * (frame_n - last_frame_n))
                    sleep_time = expected_time - time()
                    if sleep_time > 0:
                        # log.debug(f'sleep {sleep_time}')
                        await asyncio.sleep(sleep_time)
                last_frame = frame
                frame_n += 1
                frame_event.set()
            log.debug(f'Raw frame count: {frame_n}')
            log.debug(f'Effective raw frame fps = {frame_n / (time() - start)}')

            frame_event.set()

        send_stdin_task = asyncio.create_task(send_stdin())
        read_stderr_task = asyncio.create_task(read_stderr())
        read_stdout_task = asyncio.create_task(read_stdout())

        n = 0
        while not read_stdout_task.done():
            await frame_event.wait()
            if last_frame:
                n += 1
                this_frame = last_frame
                frame_event.clear()
                yield this_frame
                last_frame_time = time()
                last_frame_n = frame_n
        
        log.debug(f'Frames yielded: {n}')
        log.debug(f'Effective yielded fps = {n / (time() - start)}')

        await read_stdout_task
        await read_stderr_task
        await send_stdin_task
        await proc.wait()
    finally:
        _check_result(proc.returncode, stderr)
