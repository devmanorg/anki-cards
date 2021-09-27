import os
import sys
import uuid
import rollbar
from io import BytesIO
from gtts import gTTS, tts
from urllib.parse import urlencode
from contextlib import suppress


from django.contrib import admin
from django.shortcuts import redirect
from django.utils.safestring import mark_safe
from django import forms
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.html import format_html, escape
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.admin.utils import flatten_fieldsets
from django.db.models import Q
from django.utils import formats
from django.contrib.staticfiles.storage import staticfiles_storage

from mptt.admin import DraggableMPTTAdmin
from mptt.admin import TreeRelatedFieldListFilter
from taggit_helpers.admin import TaggitListFilter
from import_export.admin import ImportExportModelAdmin, ImportExportMixin
from import_export import resources
from taggit.models import Tag
from markupfield.fields import MarkupField
from markupfield.widgets import AdminMarkupTextareaWidget
from taggit.forms import TagWidget
from .models import Deck, BaseCard, BasicCard, EnglishCard, Sleng, Issue
from challenges.models import Lesson
from reviews.models import SolutionEnhancementTemplate


ANKI_MARKDOWN_HELP_TEXT = mark_safe('''\
    Markdown разметка в anki-карточках Девмана отличается от стандартной.
    <a href="https://gist.github.com/dvmn-tasks/f01781f7c1407c2d1d059ba823d8aaee">Подробнее</a>.
''')


def create_tag_condition(model, ids_queryset=None):
    # Inspired by taggit source code
    # https://github.com/jazzband/django-taggit/blob/master/taggit/models.py
    condition = (
        Q(taggit_taggeditem_items__content_type__app_label=model._meta.app_label) &
        Q(taggit_taggeditem_items__content_type__model=model._meta.model_name)
    )

    if ids_queryset is None:
        return condition

    return condition & Q(taggit_taggeditem_items__object_id__in=ids_queryset)


class CustomTagListFilter(admin.SimpleListFilter):
    title = 'Теги'
    parameter_name = 'tag'

    def lookups(self, request, model_admin):
        condition = create_tag_condition(BasicCard) | create_tag_condition(EnglishCard)
        tags = Tag.objects.filter(condition).distinct()
        return tuple([(tag.name, tag.name) for tag in sorted(tags)])

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(tags__name=self.value())


class BaseCardsResource(resources.ModelResource):
    card_type = resources.Field(column_name='card_type')
    tags = resources.Field(column_name='tags')
    basiccard_front = resources.Field(column_name='basiccard_front')
    basiccard_explanation = resources.Field(column_name='basiccard_explanation')

    class Meta:
        model = BaseCard
        import_id_fields = ('guid',)
        fields = (
            'guid',
            'deck__name',
            'deck__slug',
            'deck__parent',
            'lesson__slug',
            'tags',
            'solution_enhancement_template__slug',
            'card_type',
            'basiccard__answer',
            'published',
            'moderation_status',
            'moderator_notes',

            # TODO add support for englishcard export/import
            # 'englishcard__word',
            # 'englishcard__word_translation',
            # 'englishcard__phrase',
            # 'englishcard__phrase_translation',
            # 'englishcard__phrase_article_link',
        )

    def dehydrate_tags(self, card):
        # use prefetched tags data
        return ','.join([tag.name for tag in card.basiccard.tags.all()])

    def dehydrate_card_type(self, card):
        with suppress(ObjectDoesNotExist):
            return card.basiccard and 'basiccard'
        with suppress(ObjectDoesNotExist):
            return card.englishcard and 'englishcard'

    def dehydrate_basiccard_front(self, card):
        with suppress(ObjectDoesNotExist):
            return card.basiccard.front.raw
        return ''

    def dehydrate_basiccard_explanation(self, card):
        with suppress(ObjectDoesNotExist):
            return card.basiccard.explanation.raw
        return ''

    def before_import_row(self, row, **kwargs):
        row['added_by'] = kwargs['user'].id

    def import_field(self, field, obj, data, is_m2m=False):
        special_fields_map = {
            'basiccard_front': 'front',
            'basiccard__answer': 'answer',
            'basiccard_explanation': 'explanation',
        }
        if field.attribute in special_fields_map:
            field_name = special_fields_map[field.attribute]
            field_value = data[field.attribute]
            setattr(obj, field_name, field_value)
        elif field.column_name == 'tags':
            tags = data['tags'].split(',')
            obj.tags.add(*tags)
        elif field.attribute == 'deck__slug':
            with suppress(ObjectDoesNotExist):
                obj.deck = Deck.objects.get(slug=data['deck__slug'])
        elif field.attribute == 'lesson__slug':
            with suppress(ObjectDoesNotExist):
                obj.lesson = Lesson.objects.get(slug=data['lesson__slug'])
        elif field.attribute == 'solution_enhancement_template__slug':
            with suppress(ObjectDoesNotExist):
                template = SolutionEnhancementTemplate.objects.get(slug=data['solution_enhancement_template__slug'])
                obj.solution_enhancement_template = template
        else:
            # TODO add support for englishcard export/import
            # 'englishcard__word',
            # 'englishcard__word_translation',
            # 'englishcard__phrase',
            # 'englishcard__phrase_translation',
            # 'englishcard__phrase_article_link',
            super().import_field(field, obj, data, is_m2m=False)

    def get_instance(self, instance_loader, row):
        with suppress(ObjectDoesNotExist):
            if row['card_type'] == 'basiccard':
                return BasicCard.objects.get(guid=row['guid'])
            elif row['card_type'] == 'englishcard':
                return EnglishCard.objects.get(guid=row['guid'])


class DeckAdminResource(resources.ModelResource):
    class Meta:
        model = Deck
        import_id_fields = ('slug',)
        fields = (
            'name',
            'slug',
            'parent__slug',
        )

    # FIXME all deck parents should be forced to export

    def import_field(self, field, obj, data, is_m2m=False):
        if field.attribute == 'parent__slug' and data['parent__slug']:
            obj.parent = Deck.objects.get(slug=data['parent__slug'])
        else:
            super().import_field(field, obj, data, is_m2m=False)


@admin.register(Deck)
class DeckAdmin(ImportExportMixin, DraggableMPTTAdmin):
    resource_class = DeckAdminResource
    raw_id_fields = ['parent']
    list_display = [
        'tree_actions',
        'indented_title',
        'slug',
        'get_download_link',
    ]
    search_fields = [
        'name',
        'slug',
    ]
    fields = [
        'name',
        'slug',
        'parent',
        'get_download_link',
    ]
    readonly_fields = [
        'get_download_link',
    ]

    def get_download_link(self, obj: Deck) -> str:
        # Can not use common reverse function because .apkg suffix

        query = urlencode({
            'deck': obj.slug,
            'name': f'{obj.name}.apkg',
        })
        return format_html('''
            <div style="line-height: 22px;">
                <a href="/anki/cards.apkg?{}">Скачать колоду</a>
            </div>
        ''', query)
    get_download_link.short_description = 'Скачать'

    def get_export_queryset(self, request):
        return super().get_export_queryset(request).select_related('parent')


class BaseCardAddForm(forms.ModelForm):
    card_type = forms.ChoiceField(
        choices=(
            ('BasicCard', 'Обычная карточка'),
            ('EnglishCard', 'Карточки по Английскому'),
        )
    )

    class Meta:
        fields = ['card_type']
        model = BaseCard


def get_tags(base_card):
    with suppress(ObjectDoesNotExist):
        return base_card.basiccard.tags.all()

    with suppress(ObjectDoesNotExist):
        return base_card.englishcard.tags.all()

    return []


def get_anki_field_preview(rendered_html):
    rendered_html = rendered_html.strip()
    if not rendered_html:
        return 'пусто'

    css_url = staticfiles_storage.url('devman_anki_cards.css')
    content = f'''
        <link rel="stylesheet" href="{escape(css_url)}"/>
        <div class="card">
            {rendered_html}
        </div>
    '''

    return format_html('''
        <dvmn-text-snippet class="anki-preview" content="{}">
        </dvmn-text-snippet>
    ''', content)


@admin.register(BaseCard)
class BaseCardAdmin(ImportExportModelAdmin):
    resource_class = BaseCardsResource
    form = BaseCardAddForm
    list_filter = [
        'published',
        'moderation_status',
        ['created_by', admin.RelatedOnlyFieldListFilter],
        ['deck', TreeRelatedFieldListFilter],
        CustomTagListFilter,
    ]
    search_fields = [
        # BaseCard
        'lesson__slug',
        'lesson__title',
        'solution_enhancement_template__slug',
        'solution_enhancement_template__action',

        # BasicCard
        'basiccard__front',
        'basiccard__answer',
        'basiccard__explanation',
        'basiccard__tags__name',

        # EnglishCard
        'englishcard__word_translation',
        'englishcard__phrase',
        'englishcard__phrase_translation',
        'englishcard__article_link',
        'englishcard__slengs__word_with_synonyms',
        'englishcard__slengs__footnote_explanation',
    ]
    date_hierarchy = 'created_at'
    list_select_related = ['basiccard', 'englishcard', 'deck', 'solution_enhancement_template', 'lesson', 'created_by']
    list_display_links = [
        'get_card_shortname',
    ]
    list_display = [
        'get_card_shortname',
        'get_lesson_and_solution_enhancement_template',
        'published',
        'get_moderation_status',
        'show_creation_info',
        'get_card_text',
    ]
    list_per_page = 50

    class Media:
        css = {
            'all': [
                'admin/anki-cards-list-preview.css',
            ]
        }

    def get_export_queryset(self, request):
        return super().get_export_queryset(request).select_related('basiccard', 'englishcard', 'deck')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('basiccard__tags', 'englishcard__tags')

    def show_creation_info(self, obj):
        _date = obj.created_at.date()
        date_string = formats.date_format(_date, 'j E Y')
        return format_html('<small style="color: #6c757d;">{}<br>{}</small>', date_string, obj.created_by.username)
    show_creation_info.short_description = 'Создано'
    show_creation_info.admin_order_field = 'created_at'

    def get_moderation_status(self, obj):
        status_cards = {
            'improvements': {'stage': 'Нужны доработки', 'color': 'red'},
            'approved': {'stage': 'Одобрена', 'color': 'green'},
            'wait': {'stage': 'Ожидает проверки', 'color': '#ffba00'},
        }
        return mark_safe(
            f'<span style=color:{status_cards[obj.moderation_status]["color"]}>'
            f'{status_cards[obj.moderation_status]["stage"]}</span>'
        )
    get_moderation_status.short_description = 'Этап модерации'

    def get_card_text(self, obj):
        template = '<div class="anki-cards-list-preview">{}<div>'

        with suppress(ObjectDoesNotExist):
            card = obj.basiccard
            front_html = card.front if card.front else ''  # is already stripped by markdown renderer
            answer = card.answer if card.answer else ''
            explanation_html = card.explanation if card.explanation else ''  # is already stripped by markdown renderer

            card_html = f'{front_html} <pre class="answer"><code>{escape(answer)}</code></pre> {explanation_html}'
            return mark_safe(template.format(card_html))

        with suppress(ObjectDoesNotExist):
            card = obj.englishcard
            phrase_html = card.phrase if card.phrase else ''  # is already stripped by markdown renderer
            translation_html = card.phrase_translation if card.phrase_translation else ''  # is already stripped by markdown renderer
            card_html = f'{phrase_html} {translation_html}'
            return mark_safe(template.format(card_html))
        return 'пусто'
    get_card_text.short_description = 'Текст карточки'

    def get_lesson_and_solution_enhancement_template(self, obj):
        html_lines = []

        lesson_title = obj.lesson and obj.lesson.title or ''
        if lesson_title:
            lesson_html = format_html('<small style="color: #6c757d;">Урок:</small> <small>{}</small>', lesson_title)
            html_lines.append(lesson_html)

        enh_action = obj.solution_enhancement_template and obj.solution_enhancement_template.action or ''
        if enh_action:
            enh_html = format_html('<small style="color: #6c757d;">Улучшение:</small> <small>{}</small>', enh_action)
            html_lines.append(enh_html)

        tag_names = ', '.join(tag.name for tag in get_tags(obj))
        if tag_names:
            tag_line_html = format_html('<small style="color: #6c757d;">Теги:</small> <small>{}</small>', tag_names)
            html_lines.append(tag_line_html)

        return mark_safe('<br>'.join(html_lines))
    get_lesson_and_solution_enhancement_template.short_description = 'Урок, улучшалка, теги'

    def get_list_display(self, request):
        # workaround to replace `list_editable` class attribute with evaluated value
        if request.user.has_perm('anki_cards.editor'):
            self.list_editable = ['published']
        else:
            self.list_editable = []
        return self.list_display

    def save_model(self, request, obj, form, change):
        # add form should only redirect to new page without save to db
        if not change:
            return

        super().save_model(request, obj, form, change)

    def response_add(self, request, obj):
        if request.POST['card_type'] == 'BasicCard':
            url = reverse('admin:anki_cards_basiccard_add')
        else:
            url = reverse('admin:anki_cards_englishcard_add')
        return redirect(url)

    def get_card_shortname(self, obj):
        # returns title only, not link to support Django admin popups feature for raw_id_fields
        # redirect to BasicCard / EnglishCard change form is provided by def change_view
        card_name = f'{obj.id}. {obj.deck or "Без колоды"}'
        template = '<span style="white-space: nowrap;">{title}</span>'
        return format_html(template, title=card_name)
    get_card_shortname.short_description = 'Карточка'

    def change_view(self, request, object_id, **kwargs):
        card = get_object_or_404(BaseCard, id=object_id)

        with suppress(ObjectDoesNotExist):
            edit_url = reverse('admin:anki_cards_basiccard_change', args=(card.basiccard.id,))
            return HttpResponseRedirect(edit_url)

        with suppress(ObjectDoesNotExist):
            edit_url = reverse('admin:anki_cards_englishcard_change', args=(card.englishcard.id,))
            return HttpResponseRedirect(edit_url)

        return super().change_view(request, object_id, **kwargs)

    def has_delete_permission(self, request, obj=None):
        """Is used during cascade deletion of BasicCard or EnglishCard instance.
        
        Deletion of any BasicCard instance via admin UI will cause cascade deletion of every related records. BasicCard and BaseCard are related via
        OneToOneField, so UI will check permissions for both models before deletion. So two methods of different classes will be called:

        - BasicCardAdmin.has_delete_permission
        - BaseCard.has_delete_permission
        
        This method should return True, to permit deletion of ant child model instance: BasicCard, EnglishCard, whatever. 
        """

        if obj and not obj.published and obj.created_by == request.user:
            return True

        if obj and request.user.has_perm("anki_cards.editor"):
            return True

        return super().has_delete_permission(request, obj)


def check_moderation_needed(cd):
    if 'published' in cd and cd['moderation_status'] != 'approved' and cd['published']:
        raise ValidationError('Данная карточка не прошла проверку', code='moderation_required')


class AutofilledCreatedByFieldAdmin(admin.ModelAdmin):

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)
        if not obj.id:
            obj.created_by = request.user
        return obj


class BaseCardLimitedAccessAdmin(admin.ModelAdmin):
    """Ограничивает права на изменение карт.

    Код тесно связан с настройками прав пользователя. См dvmn/fixtures/management/commands/_users.py
    """

    def get_readonly_fields(self, request, obj=None):
        fields = {
            *getattr(self, 'readonly_fields', []),
            'created_by',
            'created_at',
        }
        if request.user.is_superuser:
            return fields

        is_editor = request.user.has_perm("anki_cards.editor")

        if not is_editor:
            fields.update({
                'published',
                'moderator_notes',
                'guid',
            })

        if obj and obj.published and not is_editor:
            fields.update({
                'tags',
                'lesson',
                'solution_enhancement_template',
            })

        if obj and not is_editor and (obj.published or obj.created_by != request.user):
            all_fields = flatten_fieldsets(self.get_fieldsets(request, obj))
            fields.update(all_fields)

        return fields

    def has_view_permission(self, request, obj=None):
        view_perm_found = any([
            # has_perm is always True if user.is_superuser
            request.user.has_perm("anki_cards.view_basecard"),
            request.user.has_perm(f"anki_cards.view_{self.model._meta.model_name}"),
            request.user.has_perm("anki_cards.editor"),
        ])

        return view_perm_found or super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and not obj.published and obj.created_by == request.user:
            return True

        delete_perm_found = any([
            # has_perm is always True if user.is_superuser
            request.user.has_perm("anki_cards.delete_basecard"),
            request.user.has_perm(f"anki_cards.delete_{self.model._meta.model_name}"),
            request.user.has_perm("anki_cards.editor"),
        ])

        return delete_perm_found or super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if not obj:  # add new item form
            add_perm_found = any([
                # has_perm is always True if user.is_superuser
                request.user.has_perm("anki_cards.add_basecard"),
                request.user.has_perm(f"anki_cards.add_{self.model._meta.model_name}"),
                request.user.has_perm("anki_cards.editor"),
            ])

            return add_perm_found or super().has_change_permission(request, obj)

        change_perm_found = any([
            # has_perm is always True if user.is_superuser
            request.user.has_perm("anki_cards.change_basecard"),
            request.user.has_perm(f"anki_cards.change_{self.model._meta.model_name}"),
            request.user.has_perm("anki_cards.editor"),
        ])

        if not obj.published and obj.created_by == request.user:
            return True

        return change_perm_found or super().has_change_permission(request, obj)


class BasicCardForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'front' in self.fields:  # depends on permissions
            self.fields['front'].help_text = ANKI_MARKDOWN_HELP_TEXT
        if 'explanation' in self.fields:  # depends on permissions
            self.fields['explanation'].help_text = ANKI_MARKDOWN_HELP_TEXT

    def clean(self):
        check_moderation_needed(self.cleaned_data)

        cd = self.cleaned_data
        if 'answer' in cd and 'explanation' in cd and not (cd['answer'] or cd['explanation']):
            self.add_error(None, 'Либо укажите ответ, либо заполните обратную сторону карточки.')

    class Meta:
        fields = '__all__'
        model = BasicCard
        widgets = {
            'answer': forms.TextInput(attrs={
                'style': 'font-size: 110%; line-height: 120%; font-family: monospace; width: 500px;',
            }),
            'tags': TagWidget(attrs={
                'style': 'font-size: 110%; line-height: 120%; font-family: monospace; width: 500px;',
            }),
        }


@admin.register(BasicCard)
class BasicCardAdmin(BaseCardLimitedAccessAdmin, AutofilledCreatedByFieldAdmin):
    raw_id_fields = ['deck', 'lesson', 'solution_enhancement_template']
    form = BasicCardForm
    change_form_template = 'admin/dvmn_change_form.html'
    formfield_overrides = {
        MarkupField: {'widget': AdminMarkupTextareaWidget(attrs={
            'rows': 15,
            'class': 'markdown-textarea js-textarea-with-tabs js-anki-md-textarea',
            'data-preview-classes': 'anki-preview',
        })},
    }
    fieldsets = [
        ['Состояние карточки', {
            'fields': [
                'published',
                'moderation_status',
                'moderator_notes',
            ],
        }],
        ['Где лежит', {
            'fields': [
                'deck',
                'lesson',
                'solution_enhancement_template',
                'tags',
            ],
        }],
        ['Прочее', {
            'classes': ['collapse', ],
            'fields': [
                'created_by',
                'created_at',
                'guid',
            ],
        }],
    ]

    editable_card_fieldset = {
        'fields': [
            'front',
            'answer',
            'explanation',
        ],
    }
    readonly_card_fieldset = {
        'fields': [
            'get_front_preview',
            'answer',
            'get_explanation_preview',
        ],
    }
    readonly_fields = [
        'get_front_preview',
        'get_explanation_preview',
    ]

    def get_fieldsets(self, request, obj=None):
        can_edit = self.has_change_permission(request, obj)
        card_fieldset = can_edit and self.editable_card_fieldset or self.readonly_card_fieldset
        return [
            ['Карточка', card_fieldset],
            *self.fieldsets,
        ]

    def get_front_preview(self, obj):
        return get_anki_field_preview(str(obj.front))
    get_front_preview.short_description = BasicCard._meta.get_field('front').verbose_name

    def get_explanation_preview(self, obj):
        return get_anki_field_preview(str(obj.explanation))
    get_explanation_preview.short_description = BasicCard._meta.get_field('explanation').verbose_name

    def response_post_save_add(self, request, obj):
        """Figure out where to redirect after the 'Save' button has been pressed when adding a new object."""
        cards_list_url = reverse(f'admin:anki_cards_basecard_changelist')
        return HttpResponseRedirect(cards_list_url)

    def response_post_save_change(self, request, obj):
        """Figure out where to redirect after the 'Save' button has been pressed."""
        cards_list_url = reverse(f'admin:anki_cards_basecard_changelist')
        return HttpResponseRedirect(cards_list_url)

    def changelist_view(self, request, **kwargs):
        cards_list_url = reverse(f'admin:anki_cards_basecard_changelist')
        return HttpResponseRedirect(cards_list_url)


class EnglishCardForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'phrase' in self.fields:  # depends on permissions
            self.fields['phrase'].help_text = ANKI_MARKDOWN_HELP_TEXT
        if 'phrase_translation' in self.fields:  # depends on permissions
            self.fields['phrase_translation'].help_text = ANKI_MARKDOWN_HELP_TEXT

    def clean(self):
        check_moderation_needed(self.cleaned_data)

    class Meta:
        fields = '__all__'
        model = EnglishCard
        widgets = {
            'phrase': AdminMarkupTextareaWidget(attrs={
                'rows': 1,
                'style': 'font-size: 110%; line-height: 120%; font-family: monospace; width: 500px;',
                'class': 'markdown-textarea js-anki-md-textarea',
                'data-preview-classes': 'anki-preview',
            }),
            'phrase_translation': AdminMarkupTextareaWidget(attrs={
                'rows': 5,
                'class': 'markdown-textarea js-textarea-with-tabs js-anki-md-textarea',
                'data-preview-classes': 'anki-preview',
            }),
            'tags': TagWidget(attrs={
                'style': 'font-size: 110%; line-height: 120%; font-family: monospace; width: 500px;',
            }),
        }


@admin.register(EnglishCard)
class EnglishCardAdmin(BaseCardLimitedAccessAdmin, AutofilledCreatedByFieldAdmin):
    form = EnglishCardForm
    change_form_template = 'admin/dvmn_change_form.html'
    raw_id_fields = ['deck', 'lesson', 'solution_enhancement_template']
    filter_horizontal = ['slengs']
    fieldsets = [
        ['Где лежит', {
            'fields': [
                'deck',
                'lesson',
                'solution_enhancement_template',
                'tags',
            ],
        }],
        ['Состояние карточки', {
            'fields': [
                'published',
                'moderation_status',
                'moderator_notes',
            ],
        }],
        ['Прочее', {
            'classes': ['collapse', ],
            'fields': [
                'created_by',
                'created_at',
                'guid',
            ],
        }],
    ]

    editable_card_fieldset = {
        'fields': [
            'word',
            'word_translation',
            'phrase',
            'phrase_translation',
            'article_link',
            'slengs',
        ],
    }
    readonly_card_fieldset = {
        'fields': [
            'word',
            'word_translation',
            'get_phrase_preview',
            'get_phrase_translation_preview',
            'get_clickable_article_link',
            'slengs',
        ],
    }
    readonly_fields = [
        'get_phrase_preview',
        'get_phrase_translation_preview',
    ]

    def get_fieldsets(self, request, obj=None):
        can_edit = self.has_change_permission(request, obj)
        card_fieldset = can_edit and self.editable_card_fieldset or self.readonly_card_fieldset
        return [
            ['Карточка', card_fieldset],
            *self.fieldsets,
        ]

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)
        try:
            acting_voice = gTTS(text=obj.phrase.raw, lang='en', slow=False)
            mp3_fp = BytesIO()
            acting_voice.write_to_fp(mp3_fp)
            if obj.acting_voice:
                os.remove(obj.acting_voice.path)
            obj.acting_voice.save(f'EnglishPhraseVoice_{str(uuid.uuid1())}.mp3', mp3_fp, save=False)
        except tts.gTTSError:
            rollbar.report_exc_info(sys.exc_info())
            rollbar.report_message("Can't convert phrase to speech", 'warning')
        return obj

    def get_phrase_preview(self, obj):
        return get_anki_field_preview(str(obj.phrase))
    get_phrase_preview.short_description = EnglishCard._meta.get_field('phrase').verbose_name

    def get_phrase_translation_preview(self, obj):
        return get_anki_field_preview(str(obj.phrase_translation))
    get_phrase_translation_preview.short_description = EnglishCard._meta.get_field('phrase_translation').verbose_name

    def get_clickable_article_link(self, obj):
        return format_html('<a href="{link}">{link}</a>', link=obj.article_link)
    get_clickable_article_link.short_description = EnglishCard._meta.get_field('article_link').verbose_name

    def response_post_save_add(self, request, obj):
        """Figure out where to redirect after the 'Save' button has been pressed when adding a new object."""
        cards_list_url = reverse(f'admin:anki_cards_basecard_changelist')
        return HttpResponseRedirect(cards_list_url)

    def response_post_save_change(self, request, obj):
        """Figure out where to redirect after the 'Save' button has been pressed."""
        cards_list_url = reverse(f'admin:anki_cards_basecard_changelist')
        return HttpResponseRedirect(cards_list_url)

    def changelist_view(self, request, **kwargs):
        cards_list_url = reverse(f'admin:anki_cards_basecard_changelist')
        return HttpResponseRedirect(cards_list_url)


class SlengForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'footnote_explanation' in self.fields:  # depends on permissions
            self.fields['footnote_explanation'].help_text = ANKI_MARKDOWN_HELP_TEXT


@admin.register(Sleng)
class SlengAdmin(admin.ModelAdmin):
    fields = [
        'word_with_synonyms',
        'footnote_explanation',
        'tags'
    ]
    list_filter = [
        TaggitListFilter,
    ]
    list_display = [
        'word_with_synonyms',
        'footnote_explanation',
        'get_tags'
    ]
    search_fields = [
        'word_with_synonyms',
        'footnote_explanation',
        'tags__name'
    ]
    form = SlengForm
    change_form_template = 'admin/dvmn_change_form.html'
    formfield_overrides = {
        MarkupField: {'widget': AdminMarkupTextareaWidget(attrs={
            'rows': 15,
            'class': 'markdown-textarea js-textarea-with-tabs js-anki-md-textarea',
            'data-preview-classes': 'anki-preview',
        })},
    }

    def get_tags(self, obj):
        # use prefetched tag data
        return ', '.join(tag.name for tag in obj.tags.all())
    get_tags.short_description = 'Теги'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = [
        'get_card_shortname',
        'description',
        'author',
        'created_at',
    ]
    ordering = [
        '-created_at',
    ]
    raw_id_fields = [
        'card',
        'author',
    ]

    def get_changeform_initial_data(self, request):
        return {'author': request.user}

    def get_card_shortname(self, obj):
        # returns title only, not link to support Django admin popups feature for raw_id_fields
        # redirect to BasicCard / EnglishCard change form is provided by def change_view
        if not obj.card:
            return '-'
        card_name = f'{obj.card.id}. {obj.card.deck or "Без колоды"}'
        template = '<span style="white-space: nowrap;">{title}</span>'
        return format_html(template, title=card_name)
    get_card_shortname.short_description = 'Карточка'
