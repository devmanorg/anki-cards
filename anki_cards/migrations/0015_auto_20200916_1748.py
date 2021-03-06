# Generated by Django 2.2.11 on 2020-09-16 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anki_cards', '0014_auto_20200916_1745'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='deck',
            options={'verbose_name': 'Колода', 'verbose_name_plural': 'Колоды'},
        ),
        migrations.AlterField(
            model_name='deck',
            name='name',
            field=models.CharField(max_length=100, verbose_name='Название'),
        ),
        migrations.AlterUniqueTogether(
            name='deck',
            unique_together={('name', 'parent')},
        ),
    ]
