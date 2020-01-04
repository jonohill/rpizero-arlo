import asyncio
from asyncio import StreamReader
import logging

log = logging.getLogger(__name__)

async def generate_jpegs(mjpeg_streamreader: StreamReader):

    buffer = b'' # Usually empty, but filled when image ends part way through a chunk (so contains start of next image)
    try:
        limit = mjpeg_streamreader._limit
    except:
        limit = 4096

    lock = asyncio.Lock()

    async def read():
        data = await mjpeg_streamreader.read(limit)
        if not data:
            raise EOFError()
        return data

    async def generate_jpeg_bytes():
        nonlocal buffer
        try:
            # Ref https://web.archive.org/web/20190610101631/http://imrannazar.com/Let's-Build-a-JPEG-Decoder:-File-Structure
            START_MARKER_VALUE = b'\xd8'
            END_MARKER_VALUE = b'\xd9'
            MARKER = b'\xff'
            START_MARKER = MARKER + START_MARKER_VALUE
            END_MARKER = MARKER + END_MARKER_VALUE

            sof = False
            try:

                # Find start of image
                while True:
                    data = buffer
                    _, sep, image = data.partition(START_MARKER)
                    if sep:
                        buffer = START_MARKER + image
                        break
                    if data.endswith(MARKER):
                        buffer = MARKER
                    buffer = await read()

                sof = True
                
                # Find end of image
                while True:
                    data = buffer
                    image, sep, remainder = data.partition(END_MARKER)
                    if sep: # EOI found
                        yield image + END_MARKER
                        buffer = remainder
                        break
                    if data.endswith(MARKER):
                        buffer = data + await read()
                        continue
                    yield data
                    buffer = await read()

            except EOFError:
                # EOF before locating end of image
                if buffer and sof:
                    yield buffer

        finally:
            lock.release()

    while True:
        # Only check for and create a new generator when the previous has been fully consumed.
        # It's a linear stream so we can only know if we can create another generator once the previous has finished.
        await lock.acquire()
        
        if (not mjpeg_streamreader.at_eof()) or buffer:
            try:                    
                # Prepopulate buffer to know for sure there remains data in the stream
                # before creating a generator
                if not buffer:
                    buffer = await read()
            except EOFError:
                pass

            if buffer:
                yield generate_jpeg_bytes()
            else:
                lock.release()
        else:
            break

# if __name__ == "__main__":
#     logging.basicConfig(level='DEBUG')

#     async def main():
#         sr = StreamReader()
#         with open('../arlo-sample.mjpg', 'rb') as f:
#             sr.feed_data(f.read())
#         sr.feed_eof()
        
#         num = 1
#         async for jpeg in generate_jpegs(sr):
#             with open(f'/tmp/{num}.jpg', 'wb') as f:
#                 async for chunk in jpeg:
#                     f.write(chunk)
#             num += 1

#     asyncio.run(main())
