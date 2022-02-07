# Kuhn Poker Server Backend implementation

This repository contains the server-side implementation for the [Kuhn Poker client](https://github.com/tue-5ARA0-2021-Q3/poker-server-client). Your agent wil interact with the server for game-coordination and administration. You can start this server locally to start a game yourself and test your implementation. 

In order to locally run a game server, you need to create a new python virtual environment (either within your IDE or manually, see this [link](https://code.visualstudio.com/docs/python/environments#_create-a-virtual-environment) for the VSCode as an example):

```bash
# macOS/Linux
# You may need to run sudo apt-get install python3-venv first
python3 -m venv .venv

# Windows
# You can also use py -3 -m venv .venv
python -m venv .venv
```


After you've created you will need to activate the virtual environment:
```bash
# macOS/Linux
source ./venv/bin/activate

# Windows
.\venv\Scripts\activate
```

Then install the required packages:

```bash
# macOS/Linux
pip install -r requirements-linux.txt

# Windows
pip install -r requirements-windows.txt
```

Then generate the game protocol and setup the database: 

```bash
generate-proto.sh
migrate.sh
```

You can now start a local server instance:

```bash
python manage.py runserver --settings=configurations.dev.settings
```

Server by default will create several test player's tokens and will print it at startup. 
Here is an output example of 2 test players with `da1ff3c4-69c7-44a9-a217-8ec6c746d875` and 
`8b06fe61-e581-4ef7-b382-6916345052f6` tokens.

```bash
> python manage.py runserver --settings=configurations.dev.settings
Performing system checks...

Test player token: 5e527757-0187-4511-a7dd-825fe2014d0a
Test player token: f9265243-b208-48b4-9cb9-7a865b6baaed
```

Once the local server has been started you can use client application to play games with test tokens locally:

```
# Example for client application
python main.py --token 'da1ff3c4-69c7-44a9-a217-8ec6c746d875' --play 'bot'
```

# Bot players

By default local server instance enables bots, but does not have any bot implementations. To add a new bot create `bots` folder and add a subfolder with the corresponding agent implementation. You may use your own agent as a bot player or simply use skeleton code from the [`poker-server-client`](https://github.com/tue-5ARA0-2021-Q3/poker-server-client) repository that makes random actions.

# Docker Desktop

It is also possible to run local server instance with Docker. If you have [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running on your machine use the following command to start local server:

```bash
# First usage of this command is generally very slow. Subsequent usages will execute faster and will reuse cached docker image
docker-compose up
```

> **_NOTE:_** You may need to run `docker-compose up` twice for the first time to properly generate server database layout.

> **_NOTE:_** Initial Docker image installation and GRPC IO protocol build requires some extra RAM when using it within Docker environment. Make sure that Docker images has enough RAM in the Docker Desktop settings. 
  