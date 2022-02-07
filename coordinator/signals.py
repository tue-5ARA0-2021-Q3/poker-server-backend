from django.db.models.signals import post_save
from django.dispatch import receiver
from coordinator.models import Tournament
from coordinator.models import Tournament, GameCoordinatorTypes
from coordinator.services import GameCoordinatorService
from coordinator.kuhn.kuhn_coordinator import KuhnCoordinator, KuhnCoordinatorEventTypes, KuhnCoordinatorMessage
import threading

@receiver(post_save, sender = Tournament, dispatch_uid = "on_tournament_create")
def on_tournament_create(sender, instance, created, raw, using, update_fields, **kwargs):
    # Once tournament has been created we add a new coordinator for it automatically
    if created:
        GameCoordinatorService.logger.debug(f'Creating coordinator instance for Tournament { instance.id }')

        coordinator = GameCoordinatorService.add_coordinator(KuhnCoordinator(
            coordinator_type = GameCoordinatorTypes.TOURNAMENT_PLAYERS_WITH_BOTS if instance.allow_bots else GameCoordinatorTypes.TOURNAMENT_PLAYERS,
            game_type        = instance.game_type,
            capacity         = instance.capacity,
            timeout          = instance.timeout + 10,
            is_private       = False
        ))

        Tournament.objects.filter(id = instance.id).update(coordinator_id = coordinator.id)

        def __start_tournament():
            tournament = Tournament.objects.get(id = instance.id)
            if not tournament.is_started:
                GameCoordinatorService.logger.info(f'Starting tournament { instance.id } automatically.')
                tournament.is_started = True
                tournament.save(update_fields = [ 'is_started' ])
                

        rmcoordinator = threading.Timer(instance.timeout, __start_tournament)
        rmcoordinator.start()
    else:
        # Check if tournament has been update with `is_started` = True
        if instance.is_started == True:
            with GameCoordinatorService.lock:
                if instance.coordinator != None and str(instance.coordinator.id) in GameCoordinatorService.coordinators:
                    coordinator = GameCoordinatorService.coordinators[ str(instance.coordinator.id) ]
                    if not coordinator.is_ready():
                        coordinator.waiting_room.mark_as_ready()
                        GameCoordinatorService.logger.info(f'Tournament { instance.id } has been started.')
