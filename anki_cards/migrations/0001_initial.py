# Generated by Django 2.2.16 on 2020-09-10 15:21

from django.db import migrations, models
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BaseCard',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(blank=True, upload_to='', verbose_name='Изображения')),
                ('text_searching', models.TextField(blank=True, verbose_name='Поиск по тексту')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='BasicCard',
            fields=[
                ('basecard_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='anki_cards.BaseCard')),
                ('front', models.TextField(verbose_name='Фронтальная сторона')),
                ('back', models.TextField(verbose_name='Обратная строна ')),
            ],
            bases=('anki_cards.basecard',),
        ),
        migrations.CreateModel(
            name='InputCard',
            fields=[
                ('basecard_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='anki_cards.BaseCard')),
                ('front', models.TextField(verbose_name='Фронтальная сторона')),
                ('answer', models.TextField(verbose_name='Вопрос')),
                ('explanatioin', models.TextField(verbose_name='Объяснения')),
            ],
            bases=('anki_cards.basecard',),
        ),
        migrations.CreateModel(
            name='Deck',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Название колоды')),
                ('lft', models.PositiveIntegerField(editable=False)),
                ('rght', models.PositiveIntegerField(editable=False)),
                ('tree_id', models.PositiveIntegerField(db_index=True, editable=False)),
                ('level', models.PositiveIntegerField(editable=False)),
                ('parent', mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='anki_cards.Deck')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='basecard',
            name='deck',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decks', to='anki_cards.Deck', verbose_name='Колода'),
        ),
    ]
