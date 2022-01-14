from backend.settings import *

# This settings are for dev version of a local poker server
# Note that setting on an actual server used for assignments might (and will) be different

CARD_GENERATED_IMAGE_SIZE = 32
CARD_GENERATED_IMAGE_NOISE_LEVEL = 0.15
CARD_GENERATED_IMAGE_ROTATE_MAX_ANGLE = 15

LOBBY_REVEAL_CARDS = False
LOBBY_INITIAL_BANK = 5
LOBBY_WAITING_TIMEOUT = 5  # 5 sec
LOBBY_CONNECTION_TIMEOUT = 600  # 5 min

GENERATE_TEST_PLAYERS = 2

ALLOW_BOTS = True
BOT_FOLDER = './bots'
BOT_CREATION_DELAY = 0.0 # 0.0 sec

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[{levelname}][{asctime}]: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'default'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'filename': 'server.log',
            'formatter': 'default'
        }
    },
    'loggers': {
        'kuhn.coordinator': {
            'handlers': [ 'console', 'file' ],
            'level': 'DEBUG'
        },
        'kuhn.waiting': {
            'handlers': [ 'console', 'file' ],
            'level': 'DEBUG'
        }
    }
}
