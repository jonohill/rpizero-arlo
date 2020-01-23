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
AZURE_ENDPOINT = os.environ['AZURE_ENDPOINT']
AZURE_KEY = os.environ['AZURE_API_KEY']
IFTTT_KEY = os.environ['IFTTT_KEY']
FRAME_URL_BASE = os.environ['ARLO_URL_BASE']
FRAMES_DIR = os.environ.get('ARLO_FRAMES_DIR', '/tmp/frames') or '/tmp/frames'
SAVE_DIR = os.environ.get('MZ_SAVE_DIR', None)

routes = web.RouteTableDef()

NUM_FRAMES = 3

@routes.post('/video')
async def post_video(request: web.Request):
    # Validate key
    if request.headers.get('x-key', None) != POST_KEY:
        return web.Response(status=403)
    
    # Validate duration param
    try:
        duration = int(request.query['duration'])
        if duration <= 0:
            raise ValueError()
    except:
        return web.json_response({'error': 'positive_duration_required'}, status=400)
        
    try:
        async with VideoNotifier(azure_endpoint=AZURE_ENDPOINT, azure_key=AZURE_KEY, 
            ifttt_key=IFTTT_KEY, frame_dir=FRAMES_DIR, frame_url_base=FRAME_URL_BASE, video_dir=SAVE_DIR) as notifier:
            await notifier.check_video(request.content, duration)
    except Exception as err:
        # TODO more specific failure
        log.debug(err)
        return web.json_response({'error': 'not_a_supported_video'}, status=400)

    return web.Response(status=204)

@routes.post('/vision/v2.1/analyze')
async def post_mock_azure(request: web.Request):
    try:
        log.debug('Mock request start')
        content = await request.read()
        log.debug(f'Mock - received content length {len(content)}, starts with {content[:4]}')
        with open(f'/tmp/{uuid()}.jpg', 'wb') as f:
            f.write(content)
        return web.json_response({
            'objects': [{
                'object': 'thing',
                'rectangle': {
                    'x': 100,
                    'y': 100,
                    'w': 100,
                    'h': 100
                }
            }]
        })
    except Exception as err:
        log.debug(f'Mock - exception {err}')
        raise err

os.makedirs(FRAMES_DIR, exist_ok=True)
routes.static('/frames', FRAMES_DIR)

app = web.Application()
app.add_routes(routes)
web.run_app(app)
