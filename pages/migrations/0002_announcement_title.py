# Generated by Django 3.1.4 on 2022-01-24 13:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='title',
            field=models.TextField(default='default'),
            preserve_default=False,
        ),
    ]