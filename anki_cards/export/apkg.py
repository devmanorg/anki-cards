import json
import textwrap
import tempfile
from itertools import count
from sqlalchemy import create_engine
from urllib.parse import urljoin

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.conf import settings
from django.utils.html import escape

from .anki2_models import Base, Card, Collection, Note
from .utils import session_scope, export_anki_db
from .decks import create_deck
from . import lesson_card_with_input
from . import lesson_card_english

__all__ = [
    'export_cards',
]

FEEDBACK_LINK_TEMPLATE = textwrap.dedent('''
    <a class="feedback-link" href="{feedback_form_url}?card={card_id}">Сообщить о проблеме</a>
''')


def generate_decks_attrs(cards):
    """Return list of tuples used to export decks to anki2 format.

    ::return:: [(deck_id, deck_index, dumped_deck, root_deck_id)]
    """
    yield [
        # Default deck should be specified by anyway
        None,  # deck id for Django ORM
        1,  # deck id for Anki2 SQLite database
        create_deck(1, 'Default'),  # dict prepared to export to Anki2 SQLite database
        None,  # Django ORM id of root deck if exist
    ]

    generated_decks_ids = {None}
    counter = count(start=2)

    for card in cards:
        if card.deck_id in generated_decks_ids:
            continue

        deck_ancestors = card.deck.get_ancestors(include_self=True)
        root_deck = deck_ancestors[0]

        deck_full_name_chunks = []
        for ancestor in deck_ancestors:
            deck_full_name_chunks.append(ancestor.name)

            if ancestor.id in generated_decks_ids:
                continue

            anki2_index = next(counter)
            deck_full_name = '::'.join(deck_full_name_chunks)

            yield [
                ancestor.id,  # deck id for Django ORM
                anki2_index,  # deck id for Anki2 SQLite database
                create_deck(anki2_index, deck_full_name),  # dict prepared to export to Anki2 SQLite database
                root_deck.id,  # Django ORM id of root deck if exist
            ]
            generated_decks_ids.add(ancestor.id)


def generate_models_attrs(root_decks_indexes, englishcard_flag=False):
    counter = count(start=1)

    for root_deck_index in root_decks_indexes:
        # FIXME Multiple different models can be added here per each root deck. Add more yields
        model_index = next(counter)
        if englishcard_flag:
            yield [
                'lesson_card_english',  # slug of card type for inner usage
                root_deck_index,
                model_index,
                lesson_card_english.create_model(model_id=model_index, deck_id=root_deck_index)
            ]
        else:
            yield [
                'lesson_card_with_input',  # slug of card type for inner usage
                root_deck_index,
                model_index,
                lesson_card_with_input.create_model(model_id=model_index, deck_id=root_deck_index)
            ]


def export_cards(result_apkg_filepath, cards_query):
    type_of_cards = 'BasicCard'
    # prepare decks
    decks_attrs = list(generate_decks_attrs(cards_query))
    serialized_decks = {deck_index: serialized_deck for _, deck_index, serialized_deck, _ in decks_attrs}
    deck_id_to_index = {deck_id: deck_index for deck_id, deck_index, *_ in decks_attrs}

    # prepare separate set of models for each root deck
    roots_indexes = {deck_id_to_index[root_deck_id] for *_, root_deck_id in decks_attrs if root_deck_id}
    try:
        models_attrs = list(generate_models_attrs(roots_indexes))
    except ObjectDoesNotExist:
        type_of_cards = 'EnglishCard'
        models_attrs = list(generate_models_attrs(roots_indexes, englishcard_flag=True))
    serialized_models = {model_index: serialized_model for *_, model_index, serialized_model in models_attrs}

    # link decks with available models
    card_type_to_model_index = {}
    root_to_models = {root_index: (slug, model_index) for slug, root_index, model_index, _ in models_attrs}
    for deck_id, deck_index, _, root_deck_id in decks_attrs:
        if deck_id is None:
            continue  # skip Default deck
        root_index = deck_id_to_index[root_deck_id]
        slug, model_index = root_to_models[root_index]
        card_type_to_model_index[(slug, deck_id)] = model_index

    feedback_form_url = urljoin(settings.SITE_ROOT_URL, reverse('anki_feedback'))

    with tempfile.NamedTemporaryFile(suffix='.anki2') as db_file:
        engine = create_engine(f"sqlite:///{db_file.name}")
        with engine.connect() as connection:
            Base.metadata.create_all(connection)

            with session_scope(connection) as session:
                collection = Collection(
                    conf='{}',
                    models=json.dumps(serialized_models),
                    decks=json.dumps(serialized_decks),
                    dconf='{}',
                    tags='{}',
                )
                session.add(collection)
                session.commit()
                media_pathes = []

                for card in cards_query:
                    if type_of_cards == 'BasicCard':
                        model_index = card_type_to_model_index[('lesson_card_with_input', card.deck_id)]
                    else:
                        model_index = card_type_to_model_index[('lesson_card_english', card.deck_id)]
                    note = Note(guid=card.guid, mid=model_index)
                    try:
                        # Append feedback link to card bottom
                        # Alternatively can be done with layout editing inside function
                        # lesson_card_with_input.create_model, but will require progress reset for AnkiDroid app
                        link = FEEDBACK_LINK_TEMPLATE.format(
                            feedback_form_url=escape(feedback_form_url),
                            card_id=escape(str(card.id))
                        )

                        explanation = card.basiccard.explanation.rendered + link
                        note.set_fields(
                            card.basiccard.front.rendered,  # use prerendered markdown prepared by django-markupfield
                            card.basiccard.answer,  # leave empty string '' to hide input field on Anki Desktop
                            explanation,  # use prerendered markdown prepared by django-markupfield
                        )
                    except card.DoesNotExist:
                        media_pathes.append(card.englishcard.acting_voice.path)
                        _, acting_voice_file = card.englishcard.acting_voice.name.split('/')
                        front = f'''{card.englishcard.word}
                                    {card.englishcard.phrase}
                                    [sound:{acting_voice_file}]
                                '''
                        back = f''' {card.englishcard.phrase_translation}
                                    {card.englishcard.word_translation}
                                '''
                        note.set_fields(front, back)

                    session.add(note)
                    session.commit()

                    anki2_card = Card(
                        nid=note.id,
                        did=deck_id_to_index[card.deck_id],
                    )
                    session.add(anki2_card)
                    session.commit()

        export_anki_db(db_file.name, media_pathes, result_apkg_filepath)
