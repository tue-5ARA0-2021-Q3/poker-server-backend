from backend.settings import *

# This settings are for dev version of a local poker server
# Note that setting on an actual server used for assignments might (and will) be different

CARD_GENERATED_IMAGE_SIZE = 64
CARD_GENERATED_IMAGE_NOISE_LEVEL = 0.05
CARD_GENERATED_IMAGE_ROTATE_MAX_ANGLE = 45

LOBBY_REVEAL_CARDS = False
LOBBY_INITIAL_BANK = 5
LOBBY_WAITING_TIMEOUT = 5  # 5 sec
LOBBY_CONNECTION_TIMEOUT = 600  # 5 min

GENERATE_TEST_PLAYERS = 2

ALLOW_BOTS = True
BOT_FOLDER = './bots'
BOT_CREATION_DELAY = 0.0 # 0.0 sec

