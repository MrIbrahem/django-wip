# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-08-18 14:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wip', '0029_string_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='string',
            name='is_fragment',
            field=models.BooleanField(default=False),
        ),
    ]
