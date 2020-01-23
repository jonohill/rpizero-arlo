import asyncio
import argparse
from video_recogniser import VideoRecogniser
import video_utils
import os
import logging
import aiohttp
from time import time
from uuid import uuid4 as uuid

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

    def __init__(self, ifttt_key, azure_endpoint, azure_key, frame_dir, frame_url_base, video_dir=None, ifttt_event='push_notification'):
        self.ifttt_key = ifttt_key
        self.azure_endpoint = azure_endpoint
        self.azure_key = azure_key
        self.frame_dir = frame_dir
        self.frame_url_base = frame_url_base
        self.video_dir = video_dir
        self.ifttt_event = ifttt_event

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(raise_for_status=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._session.close()        

    async def notify(self, title, message, image_url=''):
        async with self._session.post(f'https://maker.ifttt.com/trigger/{self.ifttt_event}/with/key/{self.ifttt_key}',
            json={'value1': title, 'value2': message, 'value3': image_url}) as resp:
            log.debug(f'ifttt response: {await resp.text()}')

    async def check_video(self, video_stream, duration):
        start = time()
        notified = False
        notified_objects = set()
        notify_all = 'any' in INTERESTING_OBJECTS

        file_name = os.path.join(self.video_dir, str(uuid()) + '.ts')
        def save_and_yield_video(stream):
            async def fork_stream():
                with open(file_name, 'wb') as f:
                    async for chunk in stream:
                        f.write(chunk)
                        yield chunk
            if self.video_dir: 
                return fork_stream()
            else:
                return stream

        try:
            async with VideoRecogniser(self.azure_endpoint, self.azure_key, self._session) as recogniser:
                async for vid_results in recogniser.check_video(save_and_yield_video(video_stream), duration):
                    objects = vid_results['objects']
                    if objects:
                        actionable = set(( o['label'] for o in objects )) - notified_objects
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
                            boxes = ( (p['x'], p['y'], p['w'], p['h']) for p in ( o['position'] for o in objects if o['label'] in actionable ) )
                            out_file = f'{uuid()}.jpg'
                            await video_utils.draw_boxes_on_image(input=vid_results['frame'], output_file=os.path.join(self.frame_dir, out_file), colour='red', boxes=boxes)
                            
                            image_url = self.frame_url_base + out_file
                            log.debug(f'Image URL is {image_url}')
                            await self.notify(NOTIFICATION_MESSAGE.format(object_names), '📸', image_url)
        finally:
            if self.video_dir and (not notified):
                try:
                    os.remove(file_name)
                except:
                    pass
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
