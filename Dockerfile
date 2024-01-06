FROM python:3.8-slim AS compile
LABEL maintainer="https://github.com/buzzbyte"

ARG BUILD_DATE
ARG VCS_REF
ARG BUILD_VERSION

LABEL org.label-schema.schema-version="1.0"
LABEL org.label-schema.build-date=$BUILD_DATE
LABEL org.label-schema.name="dyphan/dyphanbot"
LABEL org.label-schema.description="An expandable Discord bot! Written in Python using Pycord. Still in early stages."
LABEL org.label-schema.url="https://dyphanbot.github.io/"
LABEL org.label-schema.vcs-url="https://github.com/buzzbyte/DyphanBot"
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.version=$BUILD_VERSION
LABEL org.label-schema.docker.cmd="docker run -v ~/dyphan:/dyphan/.dyphan -d dyphan/dyphanbot"

ARG DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -yqq --no-install-recommends \
    git ffmpeg\
 && rm -rf /var/lib/apt/lists/*

ENV HOME /dyphan
WORKDIR $HOME

ADD . .

RUN pip3 install --upgrade pip && \
    pip3 install .

CMD ["python3", "-m" , "dyphanbot"]
