FROM python:3

ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY . /code/

RUN pip install --only-binary grpcio,grpcio-tools,matplotlib,protobuf -r requirements-linux.txt
RUN bash generate-proto.sh