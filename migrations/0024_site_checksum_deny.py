# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-05-21 22:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wip', '0023_auto_20160404_1710'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='checksum_deny',
            field=models.TextField(blank=True, help_text=b'Patterns identifying lines in body not affecting page checksum', null=True, verbose_name=b'Exclude from checksum'),
        ),
    ]
