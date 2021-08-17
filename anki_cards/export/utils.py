import json
import hashlib
import zipfile
from contextlib import contextmanager
from os import path
import time

from sqlalchemy.orm import Session


TEST_TEXT = """$ echo a > a.txt
$ echo b > a.txt
$ cat a.txt

Что выведет в консоль?
"""


def calc_checksum(text):
    binary_text = text.encode('utf-8')
    hash_object = hashlib.sha1(binary_text)
    hex_dig = hash_object.hexdigest()
    decimal_dig = int(hex_dig[:8], 16)
    return decimal_dig


@contextmanager
def session_scope(bind=None):
    """Provide a transactional scope around a series of operations."""
    # Copied from official SQLAlchemy doc https://docs.sqlalchemy.org/en/13/orm/session_basics.html
    session = Session(bind=bind)
    try:
        yield session
        session.commit()
    except:  # noqa722
        session.rollback()
        raise
    finally:
        session.close()


def export_anki_db(db_path, media_pathes, apkg_path='new.apkg'):
    with zipfile.ZipFile(apkg_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        archive.write(db_path, 'collection.anki2')
        media = {}
        if media_pathes:
            for index, media_path in enumerate(media_pathes):
                _, file_name = path.split(media_path)
                # Записываем файл в .apkg
                archive.write(media_path, str(index))
                # Проставляем индекс : названия файла.mp3
                media.update({index: file_name})
        archive.writestr("media", json.dumps(media))


def read_css():
    current_path = path.dirname(path.dirname(path.abspath(__file__)))
    css_path = path.join(current_path, 'static/devman_anki_cards.css')
    with open(css_path, 'r') as f:
        return f.read()


def get_int_timestamp():
    return int(time.time())


if __name__ == '__main__':
    assert calc_checksum(TEST_TEXT) == 3664706699, 'Wrong hash!'
