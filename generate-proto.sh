# /bin/sh

py -3 -m grpc_tools.protoc --proto_path=./ --python_out=./ --grpc_python_out=./ ./proto/game/game.proto