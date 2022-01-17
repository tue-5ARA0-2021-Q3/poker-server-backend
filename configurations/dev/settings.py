from backend.settings import *

# This settings are for dev version of a local poker server
# Note that setting on an actual server used for assignments might (and will) be different

GENERATE_TEST_PLAYERS = 2

CARD_GENERATED_IMAGE_SIZE = 32
CARD_GENERATED_IMAGE_NOISE_LEVEL = 0.15
CARD_GENERATED_IMAGE_ROTATE_MAX_ANGLE = 15

COORDINATOR_REVEAL_CARDS = False
COORDINATOR_WAITING_TIMEOUT = 10  # 10 sec
COORDINATOR_CONNECTION_TIMEOUT = 5  # 5 sec
COORDINATOR_INTERVAL_CHECK = 60 # 60 sec

KUHN_GAME_INITIAL_BANK = 5
KUHN_ALLOW_BOTS = True
KUHN_BOT_FOLDER = './bots'

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
        },
        'service.coordinator': {
            'handlers': [ 'console', 'file' ],
            'level': 'DEBUG'
        }
    }
}
