
# Types of Kuhn games
CARD3 = 1 # Game with 3 cards
CARD4 = 2 # Game with 4 cards

# Possible outcomes in any type of Kuhn game
KQ = "KQ"
KJ = "KJ"
QK = "QK"
QJ = "QJ"
JK = "JK"
JQ = "JQ"
AK = "AK"
AQ = "AQ"
AJ = "AJ"
KA = "KA"
QA = "QA"
JA = "JA"

KUHN_TYPES = {
    '3': CARD3,
    'CARD3': CARD3,
    '4': CARD4,
    'CARD4': CARD4
}

def resolve_kuhn_type(kuhn_type) -> int:
    try:
        return KUHN_TYPES[kuhn_type]
    except KeyError:
        raise Exception('Unknown Kuhn poker game type: {kuhn_type}')

KUHN_TYPE_TO_STR = {
    CARD3: '3',
    CARD4: '4'
}

POSSIBLE_CARDS = {
    CARD3: [ 'K', 'Q', 'J' ],
    CARD4: [ 'A', 'K', 'Q', 'J' ]
}

CARDS_DEALINGS = {
    CARD3: [ KQ, KJ, QK, QJ, JK, JQ ],
    CARD4: [ KQ, KJ, QK, QJ, JK, JQ, AK, AQ, AJ, KA, QA, JA ]
}

RESULTS_MAP = {
    QK: -1,
    JK: -1,
    JQ: -1,
    KQ: 1,
    KJ: 1,
    QJ: 1,
    AK: 1,
    AQ: 1,
    AJ: 1,
    KA: -1,
    QA: -1,
    JA: -1
}

CHANCE = "CHANCE"
CHECK = "CHECK"
CALL = "CALL"
FOLD = "FOLD"
BET = "BET"
NEXT = "NEXT"
WIN = "WIN"
DEFEAT = "DEFEAT"

A = 1
B = -A
