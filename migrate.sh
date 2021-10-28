# /bin/sh

py -3 manage.py makemigrations
py -3 manage.py migrate --run-syncdb