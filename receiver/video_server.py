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

class MzConfig:

    def __init__(self):
        self.post_key = self.get_env('POST_KEY', str(uuid()))
        self.ifttt_endpoint = self.get_env('IFTTT_ENDPOINT', '')
        self.ifttt_key = self.get_env('IFTTT_KEY')
        self.frame_url_base = self.get_env('URL_BASE')
        self.frames_dir = self.get_env('FRAMES_DIR', '/tmp/frames')
        self.save_dir = self.get_env('SAVE_DIR', '')
        self.yolo_conf_dir = self.get_env('YOLO_CONF_DIR', 'yolo')
        self.object_whitelist = self.get_env('OBJECT_WHITELIST', set())
        self.object_blacklist = self.get_env('OBJECT_BLACKLIST', set())

    # All environment variables begin with MZ_
    def get_env(self, name, default=None, val_type=str):
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

config = MzConfig()
log.debug(vars(config))
if config.post_key:
    print(f'The POST key is {config.post_key}')

routes = web.RouteTableDef()

NUM_FRAMES = 3

@routes.post('/video')
async def post_video(request: web.Request):
    # Validate key
    if request.headers.get('x-key', None) != config.post_key:
        return web.Response(status=403)
        
    try:
        kwargs = { 'ifttt_key': config.ifttt_key, 'frame_dir': config.frames_dir, 'frame_url_base': config.frame_url_base, 
                   'video_dir': config.save_dir, 'yolo_conf_dir': config.yolo_conf_dir, 'blacklist': config.object_blacklist, 'whitelist': config.object_whitelist }
        if config.ifttt_endpoint:
            kwargs['ifttt_endpoint'] = config.ifttt_endpoint
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

os.makedirs(config.frames_dir, exist_ok=True)
routes.static('/frames', config.frames_dir)

app = web.Application()
app.add_routes(routes)
web.run_app(app)
