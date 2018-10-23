FROM nvidia/cuda-ppc64le:9.2-devel

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-install-suggests \
    python3

ADD . /opt/openvprof

ENV PATH /opt/openvprof/scripts:"$PATH"
