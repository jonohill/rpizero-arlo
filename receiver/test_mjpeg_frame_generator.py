
import unittest
from mjpeg_frame_generator import generate_jpegs
from asyncio import StreamReader
from codecs import encode

class TestMjpegFrameGenerator(unittest.IsolatedAsyncioTestCase):

    async def test_all(self):

        # Cases to cover:
        #         0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
        # Chunks: <       1      ><       2      ><       3      ><       4      ><       5      ><       6      ><       7      ><       8      >
        # Images: <s      1          e><s        2                  e><s       3                 e><s       4                   e><s      5       
        #           boundary mid chunk^^                             ^^image spans chunks        ^^marker spans chunks           ^^on boundary   ^^early eof

        SOI = b'\xff\xd8'
        EOI = b'\xff\xd9'

        reader = StreamReader(16)

        jpeg_lengths = [21, 31, 29, 31, 16] # see diagram above
        num_jpegs = len(jpeg_lengths)
        for length in jpeg_lengths[:-1]:
            reader.feed_data(SOI + bytearray(length - 4) + EOI)
        reader.feed_data(SOI + bytearray(jpeg_lengths[-1] - 2))
        reader.feed_eof()

        jpegs = []
        try:
            async for jpeg in generate_jpegs(reader):
                jpeg_bytes = b''
                async for chunk in jpeg:
                    jpeg_bytes += chunk
                jpegs.append(jpeg_bytes)

            self.assertEqual(len(jpegs), num_jpegs, 'number of jpegs wrong')
            for n, jpeg, length in zip(range(1, num_jpegs+1), jpegs, jpeg_lengths):
                self.assertTrue(jpeg.startswith(SOI), 'missing SOI for jpeg {n}')
                if n != num_jpegs:
                    self.assertTrue(jpeg.endswith(EOI), 'missing EOI for jpeg {n}')
                self.assertEqual(len(jpeg), length, f'wrong length for jpeg {n}')
        except Exception as err:
            for n, jpeg in enumerate(jpegs):
                print(f'Jpeg {n+1}: {encode(jpeg, "hex")}')
            raise err


if __name__ == "__main__":
    unittest.main()
