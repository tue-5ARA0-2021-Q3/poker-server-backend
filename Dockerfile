FROM python:3

ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements-linux.txt /code/requirements-linux.txt

RUN pip install --only-binary grpcio,grpcio-tools,matplotlib,protobuf -r requirements-linux.txt
RUN pip install psycopg2

COPY . /code/

RUN bash generate-proto.sh