from agent import PokerAgent
from client.controller import Controller

import argparse

parser = argparse.ArgumentParser(description = 'Poker client CLI, with no arguments provided plays a local random game with token from '
                                               '"token_key.txt" file')

parser.add_argument('--token', help = 'Player\'s token', default = None)
parser.add_argument('--play', help = 'Existing game id, \'random\' for random match with real player, or \'bot\' to play against bot', default = 'random')
parser.add_argument('--cards', help = 'Number of cards used in a game', choices=[ '3', '4' ], default = '3', type = str)
parser.add_argument('--create', action = 'store_true', help = 'Create a new game', default = False)
parser.add_argument('--local', dest = 'server_local', action = 'store_true', help = 'Connect to a local server', default = False)
parser.add_argument('--global', dest = 'server_global', action = 'store_true', help = 'Connect to a default global server', default = False)
parser.add_argument('--server', help = 'Connect to a particular server')
parser.add_argument('--rename', help = 'Rename player', type = str)


def __main__():
    args = parser.parse_args()

    token = args.token

    if token is None:
        try:
            with open("token_key.txt", "r") as f:
                token = f.read(36)
        except FileNotFoundError:
            print('Token has not been specified. Either create a `token_key.txt` file or use `--token` CLI argument.')
            return
        except Exception:
            print('Error reading token from `token_key.txt` file. Ensure that token has a valid UUID structure and has not extra spaces before and after the token.')
            return

    server_address = 'localhost:50051'
    if args.server_local is True:
        server_address = 'localhost:50051'
    elif args.server_global is True:
        raise Exception('Global server play is unavailable for this bot')
    elif args.server is not None:
        server_address = args['server']

    client = Controller(token, server_address)

    if args.rename:
        print(client.rename(args.rename))
    elif args.create:
        print(client.create(args.cards))
    else:
        client.play(args.play, args.cards, lambda: PokerAgent())

if __name__ == '__main__':
    __main__()
