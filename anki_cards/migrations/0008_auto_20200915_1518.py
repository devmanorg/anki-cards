# Generated by Django 2.2.16 on 2020-09-15 12:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('anki_cards', '0007_auto_20200915_1329'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='basecard',
            name='answer',
        ),
        migrations.RemoveField(
            model_name='basecard',
            name='back',
        ),
        migrations.RemoveField(
            model_name='basecard',
            name='front',
        ),
    ]
