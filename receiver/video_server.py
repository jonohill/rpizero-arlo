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

# All environment variables begin with MZ_
def get_env(name, default=None, val_type=str):
    if type(default) != str and val_type == str:
        val_type = type(default)
    env_name = 'MZ_' + name
    val = os.environ.get(env_name, default) or default
    if val is None:
        raise KeyError(f'Environment variable "{env_name}" is required')
    if type(val) == str:
        if val_type == list or val_type == set:
            val = [ v.strip() for v in val.strip().split(',') ]
        if val_type == set:
            val = set(val)
    return val

POST_KEY = get_env('POST_KEY', str(uuid()))
if POST_KEY:
    print(f'The POST key is {POST_KEY}')
IFTTT_ENDPOINT = get_env('IFTTT_ENDPOINT', '')
IFTTT_KEY = get_env('IFTTT_KEY')
FRAME_URL_BASE = get_env('URL_BASE')
FRAMES_DIR = get_env('FRAMES_DIR', '/tmp/frames')
SAVE_DIR = get_env('SAVE_DIR', '')
YOLO_CONF_DIR = get_env('YOLO_CONF_DIR', 'yolo')
OBJECT_WHITELIST = get_env('OBJECT_WHITELIST', set())
OBJECT_BLACKLIST = get_env('OBJECT_BLACKLIST', set())

routes = web.RouteTableDef()

NUM_FRAMES = 3

@routes.post('/video')
async def post_video(request: web.Request):
    # Validate key
    if request.headers.get('x-key', None) != POST_KEY:
        return web.Response(status=403)
        
    try:
        kwargs = { 'ifttt_key': IFTTT_KEY, 'frame_dir': FRAMES_DIR, 'frame_url_base': FRAME_URL_BASE, 
                   'video_dir': SAVE_DIR, 'yolo_conf_dir': YOLO_CONF_DIR, 'blacklist': OBJECT_BLACKLIST, 'whitelist': OBJECT_WHITELIST }
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
