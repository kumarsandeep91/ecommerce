# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0004_auto_20150609_1215'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalstockrecord',
            name='changed_by',
        ),
        migrations.RemoveField(
            model_name='stockrecord',
            name='changed_by',
        ),
    ]
