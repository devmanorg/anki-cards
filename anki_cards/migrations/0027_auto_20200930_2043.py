# Generated by Django 2.2.16 on 2020-09-30 17:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anki_cards', '0026_basecard_status_card'),
    ]

    operations = [
        migrations.RenameField(
            model_name='basecard',
            old_name='status_card',
            new_name='card_status',
        )
    ]
