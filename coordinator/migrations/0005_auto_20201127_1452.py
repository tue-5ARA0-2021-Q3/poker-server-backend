# Generated by Django 3.1 on 2020-11-27 14:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coordinator', '0004_player_public_token'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='name',
            field=models.CharField(default='Young Swan', max_length=128),
        ),
    ]
