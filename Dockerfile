FROM python:3.8-slim AS compile

LABEL org.opencontainers.image.authors="jan@hostvoid.net"
LABEL description="Docker image of dyphanbot"
LABEL version="1.0"


ARG DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -yqq --no-install-recommends \
    git \
 && rm -rf /var/lib/apt/lists/*

ENV HOME /dyphan
WORKDIR $HOME

ADD . .

RUN pip3 install --upgrade pip && \
    pip3 install .

CMD ["python3", "-m" , "dyphanbot"]
