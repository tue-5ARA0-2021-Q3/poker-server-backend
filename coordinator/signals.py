import threading
import grpc
import logging
import time

from django.db.models.signals import post_save
from django.conf import settings
from django.dispatch import receiver
from coordinator.models import Tournament
from proto.game import game_pb2
from proto.game import game_pb2_grpc

@receiver(post_save, sender = Tournament, dispatch_uid = "on_tournament_create")
def on_tournament_create(sender, instance, created, raw, using, update_fields, **kwargs):
    # Once tournament has been created we initiate GRPC request to add a new coordinator for it automatically
    # We create a separate function for that and run it in a separate thread with a slight delay because database it locked at the moment
    def __on_tournament_create():
        response = None
        if created: 
            with grpc.insecure_channel(settings.GRPC_SERVER_ADDRPORT) as channel:
                stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
                response = stub.Tournament(game_pb2.TournamentRequest(
                    secret       = settings.COORDINATOR_TOURNAMENTS_SECRET, 
                    id           = str(instance.id),
                    request_type = game_pb2.TournamentRequest.TournamentRequestType.Create,
                    game_type    = instance.game_type,
                    capacity     = instance.capacity,
                    timeout      = instance.timeout,
                    allow_bots   = bool(instance.allow_bots)
                ))
        else:
            if instance.is_started == True:
                with grpc.insecure_channel(settings.GRPC_SERVER_ADDRPORT) as channel:
                    stub = game_pb2_grpc.GameCoordinatorControllerStub(channel)
                    response = stub.Tournament(game_pb2.TournamentRequest(
                        secret       = str(settings.COORDINATOR_TOURNAMENTS_SECRET), 
                        id           = str(instance.id),
                        request_type = game_pb2.TournamentRequest.TournamentRequestType.Start,
                    ))
        
        if (response is not None) and (response.error is not None):
            logging.error(f'Error during `post_save` handle for tournament creation: { response }')

    deffered = threading.Thread(target = __on_tournament_create)
    deffered.start()
    
