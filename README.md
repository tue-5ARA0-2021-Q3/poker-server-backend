# Kuhn Poker Server Backend implementation

This repository contains the server-side implementation for the Kuhn Poker client. Your agent wil interact with the server for game-coordination and administration. You can start this server locally to start a game yourself and test your implementation.

In order to locally run a game server create a new virtual environment with PyCharm, and activate the virtual environment:
```
.\venv\Scripts\activate
```

Then install the required packages:
```
pip install -r requirements.txt
```

Then generate the game protocol and setup the database: 
```
generate-proto.sh
migrate.sh
```

You can now start a local server instance:
```
python manage.py grpcrunserver --dev --settings=configurations.dev.settings
```

Server by default will create 2 test player's tokens and will print it at startup. 
Here is an output example of 2 test players with `da1ff3c4-69c7-44a9-a217-8ec6c746d875` and 
`8b06fe61-e581-4ef7-b382-6916345052f6` tokens.

```
...
Player test@test: da1ff3c4-69c7-44a9-a217-8ec6c746d875
Player test@test: 8b06fe61-e581-4ef7-b382-6916345052f6
...
```

Once the local server has been started you can use client application to play games with test tokens locally:

```
# Example for client application
python main.py --token 'da1ff3c4-69c7-44a9-a217-8ec6c746d875'
```

# Public Docker image (Advanced)

It is also possible to run local server instance with Docker. 
If you have Docker and Docker Compose installed on your machine use the following command to start local server:

```
docker-compose up
```

Note: you may need to run `docker-compose up` twice for the first time to properly generate server database layout.
  