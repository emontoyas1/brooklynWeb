from datetime import timedelta
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from orders.models import Order


class Command(BaseCommand):
    help = 'Marca como ready_to_gift los pedidos con 48h de amistad confirmada'

    def handle(self, *args, **options):
        threshold = now() - timedelta(hours=48)
        updated = Order.objects.filter(
            status='friendship_confirmed',
            friendship_confirmed_at__lte=threshold
        ).update(status='ready_to_gift', ready_to_gift_at=now())
        self.stdout.write(f"{updated} pedidos marcados como ready_to_gift.")
