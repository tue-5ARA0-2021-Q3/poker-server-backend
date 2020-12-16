from typing import List


class ClientGameRoundState(object):

    def __init__(self, game_id, round_id):
        self._game_id = game_id
        self._round_id = round_id
        self._card = None
        self._turn_order = None
        self._moves_history = []
        self._available_actions = []
        self._outcome = None
        self._cards = None
        self._result = None

    def get_game_id(self):
        return self._game_id

    def get_round_id(self):
        return self._round_id

    def set_card(self, card):
        self._card = card

    def get_card(self):
        return self._card

    def set_turn_order(self, order):
        self._turn_order = order

    def get_turn_order(self):
        return self._turn_order

    def add_move_history(self, move):
        self._moves_history.append(move)

    def moves_history(self):
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

    def set_result(self, result):
        self._result = result

    def get_result(self):
        return self._result

    def set_cards(self, cards):
        self._cards = cards

    def get_cards(self):
        return self._cards


class ClientGameState(object):

    def __init__(self, game_id, player_id, player_bank):
        self._game_id = game_id
        self._player_id = player_id
        self._player_bank = player_bank
        self._rounds = []

    def get_game_id(self):
        return self._game_id

    def get_player_id(self):
        return self._player_id

    def get_player_bank(self):
        return self._player_bank

    def get_rounds(self):
        return list(filter(lambda r: len(r.moves_history()) != 0, self._rounds))

    def get_last_round_state(self) -> ClientGameRoundState:
        return self._rounds[-1]

    def update_bank(self, outcome):
        self._player_bank = self._player_bank + int(outcome)

    def start_new_round(self):
        self._rounds.append(ClientGameRoundState(self.get_game_id(), len(self._rounds) + 1))
