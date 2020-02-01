import asyncio
import aiofile
import cv2
import threading
import tempfile
from shutil import rmtree
import os
import time
import logging

log = logging.getLogger(__name__)

async def get_realtime_frames(video_bytes_generator):
    '''Generator of video frames, no slower than realtime. Effectively this means frames are dropped if not read in time.'''

    loop = asyncio.get_running_loop()
    written_event = threading.Event()
    fully_written_event = threading.Event()
    frame_event = asyncio.Event()
    frame_lock = threading.Lock()
    frame = None

    pipe_dir = tempfile.mkdtemp()
    try:
        pipe_file = os.path.join(pipe_dir, 'vid_pipe')

        async def write_bytes():
            async with aiofile.AIOFile(pipe_file, 'wb') as f:
                write = aiofile.Writer(f)
                async for chunk in video_bytes_generator:
                    await write(chunk)
                    await f.fsync()
                    written_event.set()
            fully_written_event.set()

        def read_frames():
            nonlocal frame
            written_event.wait()
            video = cv2.VideoCapture(pipe_file)

            fps = video.get(cv2.CAP_PROP_FPS)
            expected_gap = 1 / fps
            last_frame_time = 0

            start = time.time()
            frame_count = 0
            
            end_of_video = False
            while not end_of_video:
                grabbed, new_frame = video.read()
                written_event.clear()

                if grabbed:
                    with frame_lock:
                        last_frame_read = not frame_event.is_set()
                    if not last_frame_read:
                        sleep_time = last_frame_time + expected_gap - time.time()
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                    with frame_lock:
                        frame = new_frame.copy()
                        frame_count += 1
                    last_frame_time = time.time()
                    loop.call_soon_threadsafe(frame_event.set)
                else:
                    end_of_video = True
                    # Handle case that we've run out of data in the pipe, but there's more to come.
                    # TODO Bug: We are likely part way through a frame, so some produced frames will be corrupt. 
                    #           Resolution would be to find a way to have opencv wait for data, or to ensure chunks always contain whole frames.
                    #           This bug only manifests if frames are produced and read faster than chunks can be written to the pipe.
                    if not fully_written_event.is_set():
                        written_event.wait()
                        end_of_video = False

            end = time.time()
            log.debug(f'Effective frame rate: {frame_count / (end - start)}')

        write_task = loop.create_task(write_bytes())
        read_task = loop.run_in_executor(None, read_frames)
    
        while not read_task.done():
            await frame_event.wait()
            with frame_lock:
                frame_event.clear()
                new_frame = frame.copy()
            yield new_frame
        
        for t in asyncio.as_completed([ write_task, read_task ]):
            await t
    finally:
        rmtree(pipe_dir, ignore_errors=True)
