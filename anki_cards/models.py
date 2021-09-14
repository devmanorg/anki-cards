import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone

from mptt.models import MPTTModel, TreeForeignKey
from markupfield.fields import MarkupField
from taggit.managers import TaggableManager

from challenges.models import Lesson
from reviews.models import SolutionEnhancementTemplate
from devman.markdown import render_anki_markdown
from dvmn_users.models import DvmnUser


STAGE_MODERATION_CHOICES = [
    ('improvements', 'Нужны доработки'),
    ('wait', 'Ожидает проверки'),
    ('approved', 'Одобрена'),
]


class Deck(MPTTModel):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField(max_length=64, unique=True)
    parent = TreeForeignKey('self',
                            on_delete=models.CASCADE,
                            null=True,
                            blank=True,
                            related_name='children',
                            verbose_name='Родитель')

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Колода'
        verbose_name_plural = 'Колоды'
        unique_together = [
            ['name', 'parent']
        ]

    class MPTTMeta:
        order_insertion_by = ['name']


class Sleng(models.Model):
    word_with_synonyms = models.CharField('Слово + синонимы', max_length=200)
    footnote_explanation = MarkupField(
        'Пояснение в сноске', markup_type='anki_markdown',
        markup_choices=[('anki_markdown', render_anki_markdown)]
    )
    tags = TaggableManager(
        verbose_name='Теги',
        help_text='Добавьте тэги для быстрого поиска',
        blank=True
    )

    class Meta:
        verbose_name = 'Сленг'
        verbose_name_plural = 'Сленги'

    def __str__(self):
        return f'{self.word_with_synonyms}'


def generate_card_guid():
    return str(uuid.uuid1())


class BaseCard(models.Model):
    """Use multi-table inheritance to provide same changelist page in admin UI for cards of any type."""

    guid = models.CharField(
        max_length=36,  # 36 symbols are common uuid hash length.
        unique=True,
        db_index=True,
        default=generate_card_guid,
        help_text='Globally unique id, almost certainly used for syncing'
    )
    deck = models.ForeignKey(Deck,
                             related_name='cards',
                             verbose_name='Колода',
                             on_delete=models.SET_NULL,
                             blank=True,
                             null=True)
    lesson = models.ForeignKey(Lesson,
                               on_delete=models.CASCADE,
                               verbose_name='Урок',
                               related_name='basecards',
                               blank=True,
                               null=True)
    solution_enhancement_template = models.ForeignKey(
        SolutionEnhancementTemplate,
        on_delete=models.CASCADE,
        verbose_name='Улушение из код ревью',
        related_name='basecards',
        blank=True,
        null=True
    )
    tags = TaggableManager(
        verbose_name='Теги',
        help_text='Добавьте тэги для быстрого поиска',
        blank=True
    )
    moderation_status = models.CharField(
        'Этап модерации',
        max_length=40,
        choices=STAGE_MODERATION_CHOICES,
        default='wait',
        db_index=True,
    )
    moderator_notes = models.TextField('Замечания редактора', blank=True)
    published = models.BooleanField('Опубликовано', default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Создано',
        related_name='basecards',
    )
    created_at = models.DateTimeField('создано', default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Карточка'
        verbose_name_plural = 'Карточки'
        permissions = (
            ('editor', 'can edit cards and add cards to deck'),
        )


class BasicCard(BaseCard):
    front = MarkupField(
        'Фронтальная сторона', markup_type='anki_markdown',
        markup_choices=[('anki_markdown', render_anki_markdown)]
    )
    answer = models.TextField(
        'Правильный ответ', blank=True,
        help_text='Что укажет пользователь в поле ввода. ' +
                  'Если пусто, то в карточке вместо поля ввода будет Кнопка "Показать ответ".')
    explanation = MarkupField(
        'Объяснение ответа', markup_type='anki_markdown', blank=True,
        markup_choices=[('anki_markdown', render_anki_markdown)]
    )

    class Meta:
        verbose_name = 'Карточка с вводом'
        verbose_name_plural = 'Карточки с вводом'

    def __str__(self):
        return f'Карточка номер {self.id}'


class EnglishCard(BaseCard):
    word = models.CharField(max_length=100, verbose_name='Слово', blank=True)
    # back side of anki
    word_translation = models.CharField(max_length=100, verbose_name='Перевод слова')
    # front side of anki
    phrase = MarkupField(
        'Фраза (подлежащее + сказуемое)', markup_type='anki_markdown',
        markup_choices=[('anki_markdown', render_anki_markdown)],
    )
    # back side of anki
    phrase_translation = MarkupField(
        'Перевод фразы', markup_type='anki_markdown',
        markup_choices=[('anki_markdown', render_anki_markdown)],
    )
    # back side of anki
    article_link = models.URLField(max_length=300, verbose_name='Ссылка на статью', blank=True)
    acting_voice = models.FileField(upload_to='acting_voices', blank=True)
    slengs = models.ManyToManyField(Sleng, verbose_name='Сленг', blank=True)

    class Meta:
        verbose_name = 'Карточка по Английскому'
        verbose_name_plural = 'Карточки по Английскому'

    def __str__(self):
        return f'Англо-Карточка номер {self.id}'


class Issue(models.Model):
    card = models.ForeignKey(
        BaseCard,
        related_name='issues',
        verbose_name='Карточка',
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )
    description = models.TextField('Текст', blank=True)
    created_at = models.DateTimeField('Создано', default=timezone.now, db_index=True)
    author = models.ForeignKey(
        DvmnUser,
        related_name='issues',
        verbose_name='Автор',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = 'Тикет'
        verbose_name_plural = 'Тикеты'
