# Generated by Django 3.2.23 on 2023-12-06 09:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0064_auto_20231206_0921"),
        ("forms", "0098_update_default_value_components_prefill"),
    ]

    operations = [
        migrations.AddField(
            model_name="form",
            name="theme",
            field=models.ForeignKey(
                blank=True,
                help_text="Apply a specific appearance configuration to the form. If left blank, then the globally configured default is applied.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="config.theme",
                verbose_name="form theme",
            ),
        ),
    ]
