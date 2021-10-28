# Kuhn Poker Server Backend implementation

This repository contains the server-side implementation for the Kuhn Poker client. Your agent wil interact with the server for game-coordination and administration. You can start this server locally to start a game yourself and test your implementation.

In order to locally run a game server create a new virtual environment with PyCharm, and activate the virtual environment:
```
.venv\Scripts\activate
```

Then install the required packages:
```
pip install -r requirements.txt
```

Then generate the game protocol and setup the database: 
```
.\generate-proto.sh
.\migrate.sh
```

You can now start a local server instance:
```
py -3 manage.py grpcrunserver --dev
```