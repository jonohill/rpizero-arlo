#!/usr/bin/env python3

import argparse
import logging
import os
import glob
import shlex
from pprint import pprint
import json
import tempfile
import math
from time import time
import aiohttp
import asyncio
import sys
import video_utils
from mjpeg_frame_generator import generate_jpegs
from utils import as_completed_and_iterated

log = logging.getLogger(__name__)

# TODO
# parser = argparse.ArgumentParser()
# parser.add_argument('')

VIDEO_FILES = '*.mp4'
FRAME_COUNT = 3

class VideoRecogniser:

    def __init__(self, azure_endpoint, azure_api_key, http_session=None):
        self._session = None
        self._endpoint = azure_endpoint
        self._api_key = azure_api_key
        self._created_session = False
        if http_session:
            self._session = http_session

    async def __aenter__(self):
        if not self._session:
            self._created_session = True
            self._session = aiohttp.ClientSession(raise_for_status=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._created_session:
            await self._session.close()

    async def recognise_image(self, image_data):
        '''image_data can be anything supported by aiohttp, e.g. bytes, generator'''

        headers = {'Ocp-Apim-Subscription-Key': self._api_key, 'Content-Type': 'application/octet-stream'}
        params = {'visualFeatures': 'Objects'}
        async with self._session.post(self._endpoint + 'vision/v2.1/analyze', headers=headers, params=params, data=image_data) as resp:
            result = await resp.json()

            objects = []
            if result['objects']:
                for obj in result['objects']:
                    objects.append({
                        'label': obj['object'],
                        'position': {
                            'x': obj['rectangle']['x'],
                            'y': obj['rectangle']['y'],
                            'w': obj['rectangle']['w'],
                            'h': obj['rectangle']['h']
                        }
                    })
                return { 'objects': objects }

    async def check_video(self, vid_stream, duration_ms: int):
        '''Generator. Given a video stream, generate recognition results.'''

        async def recognise(jpeg):
            jpeg_data = b''
            async def yield_jpeg():
                nonlocal jpeg_data
                async for chunk in jpeg:
                    jpeg_data += chunk
                    yield chunk
            results = await self.recognise_image(yield_jpeg())
            if results:
                results['frame'] = jpeg_data
                return results

        frame_seconds = [0.1]
        add_end_frame = FRAME_COUNT >= 3
        middle_frame_count = FRAME_COUNT - (2 if add_end_frame else 1)
        middle_frame_gap = duration_ms / (middle_frame_count + 1) / 1000
        for n in range(1, middle_frame_count + 1):
            frame_seconds.append(n * middle_frame_gap)
        if add_end_frame:
            frame_seconds.append((duration_ms / 1000) - 0.1)

        jpeg_generator = video_utils.extract_frames(vid_stream, frame_seconds)
        task_completer = as_completed_and_iterated(jpeg_generator)
        async for task, result in task_completer:
            if task == jpeg_generator: # frame generator
                await task_completer.asend(recognise(result))
            elif task and result: # image results
                yield result

if __name__ == "__main__":
    VIDEOS_DIR = os.environ.get('ARLO_VIDEOS_DIR', os.getcwd())
    STATE_FILE = os.environ.get('ARLO_STATE_FILE', 'arlo_files.txt')
    
    FRAME_GAP = os.environ.get('ARLO_VIDEO_FRAMES_GAP', 1)
    AZURE_ENDPOINT = os.environ['AZURE_ENDPOINT']
    AZURE_API_KEY = os.environ['AZURE_API_KEY']

    logging.basicConfig(level=os.environ.get('LOGLEVEL', 'WARNING').upper())


    async def main():
        async with VideoRecogniser(AZURE_ENDPOINT, AZURE_API_KEY) as recogniser:
            async for vid_info in recogniser.check_videos(VIDEOS_DIR, STATE_FILE):
                pprint(vid_info)

    asyncio.run(main())
