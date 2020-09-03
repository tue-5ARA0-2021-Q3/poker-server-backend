from client.client import Client

import argparse

parser = argparse.ArgumentParser(description='Poker client CLI')

parser.add_argument('--token', help='Player\'s token')
parser.add_argument('--play', help='Player\'s token')
parser.add_argument('--list', action='store_true', help='Get player\'s list of games', default=False)
parser.add_argument('--create', action='store_true', help='Create a new game', default=False)

# foo()
args = parser.parse_args()

class MyPokerAgent(object):

    def __init__(self):
        self.moves_count = 0

    def make_action(self, state):
        history           = state.history()
        available_actions = state.available_actions()
        # card = state.get_current_card()
        print('Moves history', history)
        print('Available actions', available_actions)
        if self.moves_count == 3:
            return 'end'
        self.moves_count = self.moves_count + 1
        return 'continue'

    def end(self, state):
        print('Moves history after the end: ', state.history())

if args.token is not None:
    token = args.token
    client = Client(token)
    if args.play:
        client.play(args.play, MyPokerAgent())
    elif args.list:
        print(client.get_list())
    elif args.create:
        print(client.create())
    else:
        parser.print_help()
else:
    parser.print_help()