# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-02-02 09:25
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wip', '0006_auto_20160118_1344'),
    ]

    operations = [
        migrations.RenameModel('Fetched', 'PageVersion'),
        migrations.RenameModel('Translated', 'TranslatedVersion'),
    ]
