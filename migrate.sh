# /bin/sh

python manage.py makemigrations coordinator --settings=configurations.dev.settings
python manage.py makemigrations --settings=configurations.dev.settings
python manage.py migrate coordinator --settings=configurations.dev.settings
python manage.py migrate --settings=configurations.dev.settings
