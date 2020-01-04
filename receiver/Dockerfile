FROM python:3.7-slim

ENV "AZURE_ENDPOINT"=
ENV "AZURE_API_KEY"=
ENV "IFTTT_KEY"=
ENV "ARLO_VIDEOS_DIR"=
ENV "ARLO_STATE_FILE"=
ENV "ARLO_MOUNT_DEVICE"=
ENV "ARLO_MOUNT_OPTIONS"=

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD [ "docker-entrypoint.sh" ]
