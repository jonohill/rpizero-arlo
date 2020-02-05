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

log = logging.getLogger(__name__)

INTERESTING_OBJECTS = { 'any' }
#     'person',
#     'man',
#     'woman',
#     'animal',
#     'cat',
#     'dog',
#     'bird',
#     'vehicle',
#     'car',
#     'truck'
# }
NOTIFICATION_TITLE = 'Camera Alert'
NOTIFICATION_MESSAGE = '{} spotted'

class VideoNotifier:

    def __init__(self, ifttt_key, yolo_conf_dir, frame_dir, frame_url_base, video_dir=None, 
        ifttt_endpoint='https://maker.ifttt.com/', ifttt_event='push_notification'):
        self.ifttt_key = ifttt_key
        self.frame_url_base = frame_url_base
        self.video_dir = video_dir
        self.ifttt_endpoint = ifttt_endpoint
        self.ifttt_event = ifttt_event
        self.recogniser = YoloRecogniser(frame_dir)
        self.recogniser.load(yolo_conf_dir)

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(raise_for_status=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
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
            notify_all = 'any' in INTERESTING_OBJECTS
            async for vid_results in self.recogniser.recognise_video_stream(stream):
                objects = vid_results['objects']
                if objects:
                    actionable = objects - notified_objects
                    if not notify_all:
                        actionable &= INTERESTING_OBJECTS
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
                file_name = os.path.join(self.video_dir, str(uuid()) + '.ts')

            async def yield_stream(stream: asyncio.StreamReader):
                while True:
                    chunk = await stream.read(2 ** 16)
                    if not chunk:
                        break
                    yield chunk

            async def save_and_yield_stream(stream: asyncio.StreamReader):
                with open(file_name, 'wb') as f:
                    async for chunk in yield_stream(stream):
                        f.write(chunk)
                        yield chunk

            notified = False
            vid_gen = save_and_yield_stream(video_stream) if self.video_dir else yield_stream(video_stream)
            try:
                notified = await recognise(vid_gen)
            finally:
                if not notified:
                    try:
                        os.remove(file_name)
                    except:
                        pass
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
