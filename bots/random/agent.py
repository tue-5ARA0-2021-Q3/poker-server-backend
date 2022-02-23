import random

from client.state import ClientGameRoundState, ClientGameState


class PokerAgent(object):

    def __init__(self):
        pass

    def make_action(self, state: ClientGameState, round: ClientGameRoundState) -> str:
        return random.choice(round.get_available_actions())

    def on_image(self, image):
        pass 

    def on_error(self, error):
        pass

    def on_game_start(self):
        pass

    def on_new_round_request(self, state: ClientGameState):
        pass

    def on_round_end(self, state: ClientGameState, round: ClientGameRoundState):
        pass

    def on_game_end(self, state: ClientGameState, result: str):
        pass
