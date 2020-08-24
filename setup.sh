# /bin/sh

if [ ! -d "venv" ]; then 
    virtualenv venv -p python3
    source venv/bin/activate
    pip install django
    pip install djangogrpcframework
    pip install djangorestframework
    pip install grpcio
    pip install grpcio-tools
fi

source venv/bin/activate

python manage.py makemigrations
python manage.py migrate