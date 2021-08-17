from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, INTEGER, TEXT
from bs4 import BeautifulSoup

from .utils import get_int_timestamp, calc_checksum

ANKI_FIELDS_DELIMITER = chr(0x1f)  # Used for Note.flds field.

Base = declarative_base()


# Database schema is described in Anki docs: https://github.com/ankidroid/Anki-Android/wiki/Database-Structure


class Revlog(Base):
    id = Column(INTEGER(), primary_key=True, nullable=False)
    cid = Column(INTEGER(), nullable=False)
    usn = Column(INTEGER(), nullable=False)
    ease = Column(INTEGER(), nullable=False)
    ivl = Column(INTEGER(), nullable=False)
    lastIvl = Column(INTEGER(), nullable=False)
    factor = Column(INTEGER(), nullable=False)
    time = Column(INTEGER(), nullable=False)
    type = Column(INTEGER(), nullable=False)

    __tablename__ = 'revlog'


class Card(Base):
    id = Column(INTEGER(), primary_key=True, nullable=False)
    nid = Column(INTEGER(), nullable=False, doc='Reference to note id.')
    did = Column(INTEGER(), nullable=False, default=0, doc='Reference to deck id.')
    ord = Column(INTEGER(), nullable=False, default=0)
    mod = Column(INTEGER(), nullable=False, default=get_int_timestamp, doc='last modified timestamp')
    usn = Column(INTEGER(), nullable=False, default=-1)
    type = Column(INTEGER(), nullable=False, default=0)
    queue = Column(INTEGER(), nullable=False, default=0)
    due = Column(INTEGER(), nullable=False, default=9)
    ivl = Column(INTEGER(), nullable=False, default=0)
    factor = Column(INTEGER(), nullable=False, default=0)
    reps = Column(INTEGER(), nullable=False, default=0)
    lapses = Column(INTEGER(), nullable=False, default=0)
    left = Column(INTEGER(), nullable=False, default=0)
    odue = Column(INTEGER(), nullable=False, default=0)
    odid = Column(INTEGER(), nullable=False, default=0)
    flags = Column(INTEGER(), nullable=False, default=0)
    data = Column(TEXT(), nullable=False, default='')

    __tablename__ = 'cards'


class Collection(Base):
    id = Column(INTEGER(), primary_key=True, nullable=False)
    crt = Column(INTEGER(), nullable=False, default=get_int_timestamp, doc='Timestamp of the collection creation date')
    mod = Column(INTEGER(), nullable=False, default=get_int_timestamp, doc='last modified timestamp')
    scm = Column(INTEGER(), nullable=False, default=get_int_timestamp, doc='time when "schema" was modified')
    ver = Column(INTEGER(), nullable=False, default=11)  # FIXME why 11? can be changed to 1 ?
    dty = Column(INTEGER(), nullable=False, default=0)
    usn = Column(INTEGER(), nullable=False, default=0)
    ls = Column(INTEGER(), nullable=False, default=0)
    conf = Column(TEXT(), nullable=False)
    models = Column(TEXT(), nullable=False)
    decks = Column(TEXT(), nullable=False)
    dconf = Column(TEXT(), nullable=False)
    tags = Column(TEXT(), nullable=False)

    __tablename__ = 'col'


class Note(Base):
    id = Column(INTEGER(), primary_key=True, nullable=False)
    guid = Column(TEXT(), nullable=False, doc='Global unique id for this note')
    mid = Column(INTEGER(), nullable=False, doc='Model id reference')
    mod = Column(INTEGER(), nullable=False, default=get_int_timestamp, doc='last modified timestamp')
    usn = Column(INTEGER(), nullable=False, default=-1)
    tags = Column(TEXT(), nullable=False, default='')
    flds = Column(TEXT(), nullable=False, doc='All card fields joined. Are delimited by special characted 0x1f.')
    sfld = Column(INTEGER(), nullable=False, doc='Single field cleared of html tags used for search and comparison.')
    csum = Column(INTEGER(), nullable=False, doc='Checksum for sfld field.')
    flags = Column(INTEGER(), nullable=False, default=0)
    data = Column(TEXT(), nullable=False, default='')

    __tablename__ = 'notes'

    def set_fields(self, *fields):
        self.flds = ANKI_FIELDS_DELIMITER.join(fields)
        self.update_searchable_fields()

    def update_searchable_fields(self):
        flds = self.flds or ''
        front, *_ = flds.split(ANKI_FIELDS_DELIMITER)
        note_searchable_field = BeautifulSoup(front, 'lxml').get_text()
        self.sfld = note_searchable_field
        self.csum = calc_checksum(note_searchable_field)


class Grave(Base):
    id = Column(INTEGER(), primary_key=True, nullable=False)
    usn = Column(INTEGER(), nullable=False)
    oid = Column(INTEGER(), nullable=False)
    type = Column(INTEGER(), nullable=False)

    __tablename__ = 'graves'
