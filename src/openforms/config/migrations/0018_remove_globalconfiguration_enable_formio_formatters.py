# Generated by Django 3.2.12 on 2022-03-08 14:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0017_auto_20220215_1715"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="globalconfiguration",
            name="enable_formio_formatters",
        ),
    ]
