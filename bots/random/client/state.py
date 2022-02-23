class ClientGameRoundState(object):
    """
    ClientGameRoundState tracks the state of the current round, from deal to showdown. Attributes should be accessed
    through their corresponding getter and setter methods. For the PokerBot assignment you should not modify the setter
    methods yourself (only test them).

    Attributes
    ----------
    _coordinator_id : str
        Unique game coordinator identifier (token), duplicate from ClientGameState._coordinator_id
    _round_id : int
        Round counter, starts from 1
    _card : str, in ['J', 'Q', 'K', '?']
        Current card in hand; '?' means the exact card rank is unknown and has to be recognized from _card_image
    _card_image : Image
        Current card image in hand
    _turn_order : int, in [ 1, 2 ]
        Player turn position for the current round, player '1' acts first
    _moves_history : list of str
        Previously made actions of both players. Actions in the list alternate between players, i.e., the first element
        is the first action of player '1', and the second element is the first action of player '2', etc. The last
        element of _moves_history is the last action made by your opponent. If you're the first to move, _moves_history
        will be empty.
    _available_actions : list of str, where str in subset of ['BET', 'CHECK', 'FOLD', 'CALL']
        Available actions this turn, e.g., on the first move, _available_actions = ['BET', 'CHECK', 'FOLD'].
    _outcome : str
        Amount of chips won this round. Negative values indicate a loss.
    _cards : str
        Cards at showdown for both players, concatenated in player order. I.e., 'KJ' indicates player '1' holds a 'K',
        and player '2' holds a 'J'. If the opposing player folds, a question-mark is returned for that player's card;
        i.e. 'K?' indicates the card for player '2' was not revealed at showdown.
    """

    def __init__(self, coordinator_id, round_id):
        self._coordinator_id = coordinator_id
        self._round_id = round_id
        self._card = None
        self._card_image = None
        self._turn_order = None
        self._moves_history = []
        self._available_actions = []
        self._outcome = None
        self._cards = None

    def get_coordinator_id(self):
        return self._coordinator_id

    def get_round_id(self):
        return self._round_id

    def set_card(self, card):
        self._card = card

    def get_card(self):
        return self._card

    def set_card_image(self, card_image):
        self._card_image = card_image

    def get_card_image(self):
        return self._card_image

    def set_turn_order(self, order):
        self._turn_order = order

    def get_turn_order(self):
        return self._turn_order

    def add_move_history(self, move):
        self._moves_history.append(move)

    def set_moves_history(self, moves_history):
        self._moves_history = moves_history

    def get_moves_history(self):
        return self._moves_history

    def set_available_actions(self, available_actions):
        self._available_actions = available_actions

    def get_available_actions(self):
        return self._available_actions

    def is_ended(self):
        return self.get_outcome() is not None

    def set_outcome(self, outcome):
        self._outcome = outcome

    def get_outcome(self):
        return self._outcome

    def set_cards(self, cards):
        self._cards = cards

    def get_cards(self):
        return self._cards


class ClientGameState(object):
    """
    A ClientGameState object tracks a specific game between two players. A game consists of multiple rounds from deal
    to showdown. Attributes should be accessed through their corresponding getter and setter methods. For the PokerBot
    assignment you should not modify the setter methods yourself (only test them).

    Attributes
    ----------
    _coordinator_id : str
        Game coordinator identifier token
    _player_token : str
        Unique player identifier token
    _player_bank : int
        Amount of player credit chips
    _rounds : list of ClientGameRoundState
        Tracks the individual rounds played in this game
    """

    def __init__(self, coordinator_id, player_token, player_bank):
        self._coordinator_id = coordinator_id
        self._player_token = player_token
        self._player_bank = player_bank
        self._rounds = []

    def get_coordinator_id(self):
        return self._coordinator_id

    def get_player_token(self):
        return self._player_token

    def get_player_bank(self):
        return self._player_bank

    def get_rounds(self):
        return list(filter(lambda r: len(r.moves_history()) != 0, self._rounds))

    def get_last_round_state(self) -> ClientGameRoundState:
        return self._rounds[-1]

    def update_bank(self, outcome):
        self._player_bank = self._player_bank + int(outcome)

    def start_new_round(self):
        self._rounds.append(ClientGameRoundState(self.get_coordinator_id(), len(self._rounds) + 1))
