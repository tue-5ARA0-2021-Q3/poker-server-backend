from client.client import create, getlist, play

import argparse

parser = argparse.ArgumentParser(description='Poker client CLI')

parser.add_argument('--token', help='Player\'s token')
parser.add_argument('--play', help='Player\'s token')
parser.add_argument('--list', action='store_true', help='Get player\'s list of games', default=False)
parser.add_argument('--create', action='store_true', help='Create a new game', default=False)

# foo()
args = parser.parse_args()

if args.token is not None:
    token = args.token
    if args.play:
        print(play(token, args.play))
    elif args.list:
        print(getlist(token))
    elif args.create:
        print(create(token))
    else:
        parser.print_help()
else:
    parser.print_help()