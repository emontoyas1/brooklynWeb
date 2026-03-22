import requests
from decimal import Decimal
from django.conf import settings
from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
from django.core.management.base import BaseCommand
from shop.models import Product

VBUCKS_TO_COP = Decimal('16.2')  # 100 V-Bucks = 1,620 COP


class Command(BaseCommand):
    help = 'Sincroniza la Item Shop diaria de Fortnite'

    def handle(self, *args, **options):
        headers = {}
        if settings.FORTNITE_API_KEY:
            headers['Authorization'] = settings.FORTNITE_API_KEY

        r = requests.get("https://fortnite-api.com/v2/shop", headers=headers, timeout=30)
        r.raise_for_status()
        entries = r.json()['data']['entries']

        seen_ids = []

        for entry in entries:
            if not entry.get('brItems'):
                continue
            item = entry['brItems'][0]
            item_id = item['id']
            seen_ids.append(item_id)

            price_vbucks = entry.get('finalPrice', entry.get('regularPrice', 0))
            price_cop = round(Decimal(price_vbucks) * VBUCKS_TO_COP)

            Product.objects.update_or_create(
                fortnite_item_id=item_id,
                defaults={
                    'name': item['name'],
                    'type': item['type']['value'],
                    'price_vbucks': price_vbucks,
                    'price_cop': price_cop,
                    'image_url': item['images'].get('icon', ''),
                    'is_available': True,
                    'last_seen_in_shop': now(),
                    'out_date': parse_datetime(entry['outDate']) if entry.get('outDate') else None,
                }
            )

        Product.objects.exclude(fortnite_item_id__in=seen_ids).update(is_available=False)
        self.stdout.write(f"Sincronizados {len(seen_ids)} ítems.")
