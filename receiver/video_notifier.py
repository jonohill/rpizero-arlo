import asyncio
import argparse
from yolo_recogniser import YoloRecogniser
import os
import logging
import aiohttp
from time import time
from uuid import uuid4 as uuid
import utils
import traceback
import tempfile
import shutil

log = logging.getLogger(__name__)

NOTIFICATION_TITLE = 'Camera Alert'
NOTIFICATION_MESSAGE = '{} spotted'

class VideoNotifier:

    def __init__(self, ifttt_key, yolo_conf_dir, frame_dir, frame_url_base, video_dir=None, 
        ifttt_endpoint='https://maker.ifttt.com/', ifttt_event='push_notification', whitelist=set(), blacklist=set()):
        self.ifttt_key = ifttt_key
        self.frame_url_base = frame_url_base
        self.video_dir = video_dir
        self.ifttt_endpoint = ifttt_endpoint
        self.ifttt_event = ifttt_event
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.recogniser = YoloRecogniser(frame_dir)
        self.recogniser.load(yolo_conf_dir)

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(raise_for_status=True)
        self._temp_dir = tempfile.mkdtemp()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        shutil.rmtree(self._temp_dir, ignore_errors=True)
        await self._session.close()        

    async def notify(self, title, message, image_url=''):
        async with self._session.post(self.ifttt_endpoint + f'trigger/{self.ifttt_event}/with/key/{self.ifttt_key}',
            json={'value1': title, 'value2': message, 'value3': image_url}) as resp:
            log.debug(f'ifttt response: {await resp.text()}')

    async def check_video(self, video_stream):
        log.debug('check_video')

        start = time()

        async def recognise(stream):
            notified = False
            notified_objects = set()
            async for vid_results in self.recogniser.recognise_video_stream(stream):
                objects = vid_results['objects']
                if objects:
                    actionable = objects - notified_objects
                    if self.whitelist:
                        actionable &= self.whitelist
                    if self.blacklist:
                        actionable -= self.blacklist
                    if actionable:
                        notified_objects |= actionable
                        object_names = ', '.join(actionable).capitalize()
                        
                        # Text only notification
                        await self.notify(NOTIFICATION_MESSAGE.format(object_names), 'Photo incoming...')
                        if not notified:
                            log.info(f'Time to first notify: {time()-start}')
                            notified = True

                        # Rich notification
                        log.debug(vid_results)
                        image_url = self.frame_url_base + vid_results['frame']
                        log.debug(f'Image URL is {image_url}')
                        await self.notify(NOTIFICATION_MESSAGE.format(object_names), '📸', image_url)
            return notified

        try:
            if self.video_dir:
                file_name = str(uuid()) + '.m2ts'
                file_path = os.path.join(self.video_dir, file_name)
                temp_file = os.path.join(self._temp_dir, file_name)

            async def yield_stream(stream: asyncio.StreamReader):
                while True:
                    chunk = await stream.read(2 ** 16)
                    if not chunk:
                        break
                    yield chunk

            async def save_and_yield_stream(stream: asyncio.StreamReader):
                with open(temp_file, 'wb') as f:
                    async for chunk in yield_stream(stream):
                        f.write(chunk)
                        yield chunk

            notified = False
            vid_gen = save_and_yield_stream(video_stream) if self.video_dir else yield_stream(video_stream)
            try:
                notified = await recognise(vid_gen)
            finally:
                try:
                    if self.video_dir:
                        if notified:
                            log.debug(f'Move {temp_file} to {file_path}')
                            shutil.move(temp_file, file_path)
                        else:
                            os.remove(temp_file)
                except Exception:
                    log.debug('Failed to move video')
                    log.debug(traceback.format_exc())
        except:
            log.debug(traceback.format_exc())
            raise
        finally:
            log.info(f'Time to check all videos and notify: {time()-start}')
                    
if __name__ == "__main__":

    logging.basicConfig(level=os.environ.get('LOGLEVEL', 'WARNING').upper())

    parser = argparse.ArgumentParser()
    parser.add_argument('videos_dir', help='Path to directory containing video files', default='.')
    parser.add_argument('--state-file', help='File for state, to avoid reprocessing the same files', required=False, default=None)
    args = parser.parse_args()
    log.debug(args)

    AZURE_ENDPOINT = os.environ['AZURE_ENDPOINT']
    AZURE_API_KEY = os.environ['AZURE_API_KEY']
    IFTTT_KEY = os.environ['IFTTT_KEY']

    # asyncio.run(check_videos(AZURE_ENDPOINT, AZURE_API_KEY, IFTTT_KEY, args.videos_dir, args.state_file))
