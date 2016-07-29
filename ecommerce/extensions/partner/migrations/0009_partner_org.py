# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='org',
            field=models.CharField(max_length=30, unique=True, null=True, blank=True),
        ),
    ]
