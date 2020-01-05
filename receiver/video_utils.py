import asyncio
from asyncio import StreamReader, subprocess
from subprocess import PIPE
import logging
from itertools import chain
import json
from typing import AsyncGenerator
from mjpeg_frame_generator import generate_jpegs
from utils import as_completed_and_iterated

log = logging.getLogger(__name__)

def _check_result(returncode, stderr: bytearray):
    if returncode != 0:
        log.info(f'ffmpeg return code {returncode}')
        log.info(stderr.decode('utf-8'))
        raise Exception('ffmpeg failed')

async def _exec(program, args):
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    _check_result(proc.returncode, stderr)
    return stdout

async def extract_frame(input, frame_num, extra_filters=[]):
    ff_cmd = [
        '-i', input,
        '-vf', ','.join([f'select=\'eq(n\\,{frame_num})\''] + extra_filters),
        '-vframes', '1',
        '-y',
        '-f', 'singlejpeg',
        '-'
    ]
    log.debug(f'ffmpeg args: {" ".join(ff_cmd)}')
    return await _exec('ffmpeg', ff_cmd)

async def extract_frames(input_stream: StreamReader, frame_times: array[int]) -> AsyncGenerator[AsyncGenerator[bytearray, None], None]:
    
    
    
    args = [
        'ffmpeg', 
        '-i', '-',
        '-vsync', 'vfr', # else duplicate frames are produced to fill in the 'gaps'
        '-vf', f"select={'+'.join()
        '-f', 'mjpeg',
        '-'
    ]
    log.debug(' '.join(args))
    proc = await asyncio.create_subprocess_exec(*args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    
    stderr = b''
    try:

        async def send_stdin():
            while not input_stream.at_eof():
                data = await input_stream.read(2 ** 16)
                proc.stdin.write(data)
                await proc.stdin.drain()
            if proc.stdin.can_write_eof():
                proc.stdin.write_eof()

        async def read_stdout():
            async for frame in generate_jpegs(proc.stdout):
                yield frame

        async def read_stderr():
            nonlocal stderr
            stderr = await proc.stderr.read()

        frame_generator = read_stdout()
        async for task, result in as_completed_and_iterated(send_stdin(), read_stderr(), frame_generator):
            if task == frame_generator:
                yield result
    finally:
        _check_result(proc.returncode, stderr)

async def draw_boxes_on_image(input: bytearray, output_file: str, colour, *boxes, thickness=3):
    if not boxes:
        with open(output_file, 'wb') as f:
            f.write(input)

    proc = await asyncio.create_subprocess_exec('ffmpeg', 
        '-i', '-',
        '-vf', ','.join(( f'drawbox=x={x}:y={y}:w={w}:h={h}:color={colour}:t={thickness}' for x, y, w, h in boxes )),
        '-f', 'singlejpeg',
        output_file,
        stdin=PIPE, stderr=PIPE)
    
    _, stderr = await proc.communicate(input)
    _check_result(proc.returncode, stderr)
