import textwrap

from .utils import read_css, get_int_timestamp

__all__ = [
    'create_model',
]


CARD_FIELDS = [
    # All fields are required by Anki Desktop even though most of them will be overriden by CSS
    {
        "name": "Front",
        "font": "Arial",  # not used by Anki requires this field
        "ord": 0,
        "rtl": False,
        "size": 20,  # not used by Anki requires this field
        "sticky": False,
    },
    {
        "name": "Input",
        "font": "Arial",
        "ord": 1,
        "rtl": False,
        "size": 20,
        "sticky": False,
    },
    {
        "name": "Explanation",
        "font": "Arial",  # not used by Anki requires this field
        "ord": 2,
        "rtl": False,
        "size": 20,  # not used by Anki requires this field
        "sticky": False,
    },
]


def create_model(model_id, deck_id, model_name='Devman lesson card with input'):
    backside_template = textwrap.dedent('''
    {{Front}}

    <hr id=answer>

    {{type:Input}}
    {{Explanation}}
    ''')

    return {
        "did": deck_id,  # Long specifying the id of the deck that cards are added to by default
        "id": model_id,
        "css": read_css(),
        "flds": CARD_FIELDS,
        "mod": get_int_timestamp(),
        "name": model_name,
        "req": [
            [
                0,
                "any",
                [
                    0,
                    1
                ]
            ]
        ],
        "sortf": 0,
        "tmpls": [
            {
                "afmt": backside_template,
                "bafmt": "",
                "bfont": "",
                "bqfmt": "",
                "bsize": 0,
                "did": None,
                "name": "Card 1",
                "ord": 0,
                "qfmt": "{{Front}}\n\n{{type:Input}}"
            }
        ],
        "type": 0,
        "usn": -1
    }
