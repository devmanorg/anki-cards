from .utils import get_int_timestamp


def create_deck(deck_id, deck_name):
    return {
        "id": deck_id,
        "name": deck_name,
        "conf": 1,
        "mod": get_int_timestamp(),

        "browserCollapsed": False,
        "collapsed": False,
        "desc": "",
        "dyn": 0,
        "extendNew": 0,
        "extendRev": 0,
        "lrnToday": [
            0,
            0
        ],
        "newToday": [
            0,
            0
        ],
        "revToday": [
            0,
            0
        ],
        "timeToday": [
            0,
            0
        ],
        "usn": -1
    }
