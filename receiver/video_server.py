from aiohttp import web
from uuid import uuid4 as uuid
import aiohttp
import logging
import os
from time import time
from video_notifier import VideoNotifier
from pprint import pformat

log = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get('LOGLEVEL', 'WARNING').upper())

# TODO what do we call this thing
try:
    POST_KEY = os.environ['ARLO_HTTP_KEY'] or str(uuid())
except:
    POST_KEY = str(uuid())
    print(f'The POST key is {POST_KEY}')
IFTTT_ENDPOINT = os.environ.get('IFTTT_ENDPOINT', None)
IFTTT_KEY = os.environ['IFTTT_KEY']
FRAME_URL_BASE = os.environ['ARLO_URL_BASE']
FRAMES_DIR = os.environ.get('ARLO_FRAMES_DIR', '/tmp/frames') or '/tmp/frames'
SAVE_DIR = os.environ.get('MZ_SAVE_DIR', None)
YOLO_CONF_DIR = os.environ.get('MZ_YOLO_CONF_DIR', 'yolo')

routes = web.RouteTableDef()

NUM_FRAMES = 3

@routes.post('/video')
async def post_video(request: web.Request):
    # Validate key
    if request.headers.get('x-key', None) != POST_KEY:
        return web.Response(status=403)
        
    try:
        kwargs = { 'ifttt_key': IFTTT_KEY, 'frame_dir': FRAMES_DIR, 'frame_url_base': FRAME_URL_BASE, 
                   'video_dir': SAVE_DIR, 'yolo_conf_dir': YOLO_CONF_DIR }
        if IFTTT_ENDPOINT:
            kwargs['ifttt_endpoint'] = IFTTT_ENDPOINT
        async with VideoNotifier(**kwargs) as notifier:
            await notifier.check_video(request.content)
    except Exception as err:
        # TODO more specific failure
        log.debug(err)
        return web.json_response({'error': 'not_a_supported_video'}, status=400)

    return web.Response(status=204)

@routes.post('/trigger/{event}/with/key/{key}')
async def post_mock_ifttt(request: web.Request):
    try:
        log.debug('Mock ifttt start')
        content = await request.read()
        log.debug(f'Mock ifttt - received "{content}"')
        return web.Response(text=f'Congratulations! You\'ve fired the {request.match_info["event"]} event')
    except Exception as err:
        log.debug(f'Mock - exception {err}')
        raise err

os.makedirs(FRAMES_DIR, exist_ok=True)
routes.static('/frames', FRAMES_DIR)

app = web.Application()
app.add_routes(routes)
web.run_app(app)
