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

POSSIBLE_CARDS = [ 'A', 'K', 'Q', 'J' ]

# CARDS_DEALINGS = [KQ, KJ, QK, QJ, JK, JQ]
CARDS_DEALINGS = [KQ, KJ, QK, QJ, JK, JQ, AK, AQ, AJ, KA, QA, JA]

CHANCE = "CHANCE"

CHECK = "CHECK"
CALL = "CALL"
FOLD = "FOLD"
BET = "BET"
NEXT = "NEXT"
WIN = "WIN"
DEFEAT = "DEFEAT"

RESULTS_MAP = {
    QK: -1,
    JK: -1,
    JQ: -1,
    KQ: 1,
    KJ: 1,
    QJ: 1,
    AK: -1,
    AQ: -1,
    AJ: -1,
    KA: 1,
    QA: 1,
    JA: 1
}

A = 1
B = -A
