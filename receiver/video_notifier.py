import asyncio
import argparse
from video_recogniser import VideoRecogniser
import video_utils
import os
import logging
import aiohttp
from time import time

log = logging.getLogger(__name__)

INTERESTING_OBJECTS = {
    'person',
    'man',
    'woman',
    'animal',
    'cat',
    'dog',
    'bird',
    'vehicle',
    'car',
    'truck'
}
NOTIFICATION_TITLE = 'Camera Alert'
NOTIFICATION_MESSAGE = '{} spotted'

class VideoNotifier:

    def __init__(self, ifttt_key, azure_endpoint, azure_key, frame_dir, frame_url_base, ifttt_event='push_notification'):
        self.ifttt_key = ifttt_key
        self.azure_endpoint = azure_endpoint
        self.azure_key = azure_key
        self.frame_dir = frame_dir
        self.frame_url_base = frame_url_base
        self.ifttt_event = ifttt_event

    async def notify(self, http_session: aiohttp.ClientSession, ifttt_key, title, message, image_url=''):
        async with http_session.post(f'https://maker.ifttt.com/trigger/{self.ifttt_event}/with/key/{self.ifttt_key}',
            json={'value1': title, 'value2': message, 'value3': image_url}) as resp:
            log.debug(f'ifttt response: {await resp.text()}')

async def check_video(azure_endpoint, azure_key, ifttt_key, video_stream):
    start = time()
    notified = False
    unnotified_objects = INTERESTING_OBJECTS.copy()
    async with aiohttp.ClientSession() as http_session:
        async with VideoRecogniser(azure_endpoint, azure_key) as recogniser:
            async for vid_results in recogniser.check_video(video_stream):
                objects = vid_results['objects']
                if objects:
                    actionable = unnotified_objects & set(( o['label'] for o in objects ))
                    if actionable:
                        unnotified_objects -= actionable
                        object_names = ', '.join(actionable).capitalize()
                        
                        # Text only notification
                        await notify(http_session, ifttt_key, NOTIFICATION_MESSAGE.format(object_names), 'Photo incoming...')
                        if not notified:
                            log.info(f'Time to first notify: {time()-start}')
                            notified = True

                        # Rich notification
                        boxes = ( (p['x'], p['y'], p['w'], p['h']) for p in ( o['position'] for o in objects ) )
                        await video_utils.draw_boxes_on_image(vid_results['frame'], 'TODO', colour='red', *boxes)
                        
                        
                        log.debug(f'Image URL is {image_url}')
                        await notify(http_session, ifttt_key, 
                            NOTIFICATION_MESSAGE.format(object_names), '📸', image_url)
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

    asyncio.run(check_videos(AZURE_ENDPOINT, AZURE_API_KEY, IFTTT_KEY, args.videos_dir, args.state_file))
