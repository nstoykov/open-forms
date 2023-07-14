# Generated by Django 3.2.19 on 2023-07-04 11:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0082_rename_appointment_enabled_form_is_appointment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="form",
            name="is_appointment",
            field=models.BooleanField(
                default=False,
                help_text="Mark the form as an appointment form. Appointment forms do not support form designer steps.",
                verbose_name="appointment enabled",
            ),
        ),
    ]