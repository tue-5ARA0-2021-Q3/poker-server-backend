FROM python:3

ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements-linux.txt /code/

RUN pip install -r requirements-linux.txt

COPY . /code/

RUN bash generate-proto.sh