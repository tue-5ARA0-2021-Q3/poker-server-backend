
# Player communicates with a lobby with `KuhnGameLobbyPlayerMessage` object
# It has a `player_token` field and a corresponding `action` field in a form of a string
# Lobby has to check if `action` contains an available valid action later on
class KuhnGameLobbyPlayerMessage(object):

    def __init__(self, player_token, action):
        self.player_token = player_token
        self.action       = action

    def __str__(self):
        return f'message(player = { self.player_token }, action = { self.action })'


# `KuhnGameLobbyPlayer` is a simple wrapper around a player
# `player_token` speaks for itself
# `bank` current bank of the player
# `channel` is a primary communication channel between lobby and the player
class KuhnGameLobbyPlayer(object):

    def __init__(self, token: str, bank: int, channel):
        self.player_token = token
        self.bank         = bank
        self.channel      = channel

    def send_message(self, message):
        self.channel.put(message)
        self.channel.join()
            