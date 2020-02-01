import numpy
import argparse
import time
import cv2
import cv_utils
import os
import asyncio
import threading
import tempfile
from shutil import rmtree
import sys
import logging
from uuid import uuid4 as uuid

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class YoloRecogniser:

    def __init__(self, frame_save_dir=None, confidence=0.5, threshold=0.3):
        self._frame_save_dir = frame_save_dir
        self.confidence = confidence
        self.threshold = threshold

        self._net_lock = threading.Lock()

    def load(self, config_dir):
        get_path = lambda file: os.path.join(config_dir, file)
        with open(get_path('coco.names')) as f:
            self._labels = [ l.strip() for l in f.read().strip().split('\n') ]

        with self._net_lock:
            self._net = net = cv2.dnn.readNetFromDarknet(get_path('yolov3.cfg'), get_path('yolov3.weights'))
            ln = net.getLayerNames()
            self.layer_names = [ ln[i[0] - 1] for i in net.getUnconnectedOutLayers() ]

    async def recognise_video_stream(self, video_bytes_generator):

        loop = asyncio.get_running_loop()
        results = []

        def recognise_frame(frame):
            boxes = []
            confidences = []
            class_ids = []

            frame_h, frame_w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
            with self._net_lock:
                self._net.setInput(blob)
                outputs = self._net.forward(self.layer_names)
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = numpy.argmax(scores)
                    confidence = scores[class_id]

                    if confidence > self.confidence:
                        box = detection[0:4] * numpy.array([frame_w, frame_h, frame_w, frame_h])
                        x, y, w, h = box.astype('int')
                        # Re-calculate x,y as top left rather than centre of box
                        x = int(x - (w / 2))
                        y = int(y - (h / 2))
                        
                        boxes.append([x, y, int(w), int(h)])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)

            idxs = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence, self.threshold)
            objects = set()
            if len(idxs) > 0:
                for i in idxs.flatten():
                    x, y, w, h = boxes[i]
                    red = (0, 0, 255)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), red, 2)
                    objects |= { self._labels[class_ids[i]] }
                if self._frame_save_dir:
                    frame_file =  str(uuid()) + '.jpg'
                    cv2.imwrite(os.path.join(self._frame_save_dir, frame_file), frame)

            if objects:
                if self._frame_save_dir:
                    return { 'frame': frame_file, 'objects': objects }
                else:
                    return { 'objects': objects }
            else:
                return None

        async for frame in cv_utils.get_realtime_frames(video_bytes_generator):
            results = await loop.run_in_executor(None, recognise_frame, frame)
            if results:
                yield results
