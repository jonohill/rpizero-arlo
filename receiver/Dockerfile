FROM python:3.7

ENV "ARLO_HTTP_KEY"=
ENV "AZURE_ENDPOINT"=
ENV "AZURE_API_KEY"=
ENV "IFTTT_KEY"=
ENV "ARLO_URL_BASE"=
ENV "ARLO_FRAMES_DIR"=

RUN apt-get update && apt-get install -y ffmpeg

EXPOSE 8080

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD [ "python", "video_server.py" ]
