# Generated by Django 2.2.11 on 2020-09-16 14:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anki_cards', '0013_auto_20200916_1740'),
    ]

    operations = [
        migrations.AlterField(
            model_name='basiccard',
            name='explanation',
            field=models.TextField(blank=True, verbose_name='Обратная сторона'),
        ),
    ]
