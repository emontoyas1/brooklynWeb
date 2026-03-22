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

            # Bundle vs ítem individual
            bundle = entry.get('bundle')
            is_bundle = bundle is not None
            name = bundle['name'] if is_bundle else item['name']

            # Imagen: render de alta calidad > imagen del bundle > icon del ítem
            render_images = (
                (entry.get('newDisplayAsset') or {})
                .get('renderImages', [])
            )
            render_url = render_images[0]['image'] if render_images else ''
            if is_bundle:
                image_url = bundle.get('image') or render_url or item['images'].get('icon', '')
            else:
                image_url = render_url or item['images'].get('icon', '')

            # Set/colección del primer ítem
            item_set = item.get('set')
            series_name = item_set['value'] if item_set else ''

            # Tipo
            item_type = item.get('type', {}).get('value', '') if item.get('type') else ''

            # Sección de la tienda (layout)
            layout = entry.get('layout') or {}
            layout_name = layout.get('name', '')
            layout_rank = layout.get('rank', 9999)
            sort_priority = entry.get('sortPriority', 0) or 0

            price_vbucks = entry.get('finalPrice', entry.get('regularPrice', 0))
            price_cop = round(Decimal(price_vbucks) * VBUCKS_TO_COP)

            Product.objects.update_or_create(
                fortnite_item_id=item_id,
                defaults={
                    'name': name,
                    'type': item_type,
                    'price_vbucks': price_vbucks,
                    'price_cop': price_cop,
                    'image_url': image_url,
                    'is_available': True,
                    'is_bundle': is_bundle,
                    'series_name': series_name,
                    'layout_name': layout_name,
                    'layout_rank': layout_rank,
                    'sort_priority': sort_priority,
                    'last_seen_in_shop': now(),
                    'out_date': parse_datetime(entry['outDate']) if entry.get('outDate') else None,
                }
            )

        Product.objects.exclude(fortnite_item_id__in=seen_ids).update(is_available=False)
        self.stdout.write(f"Sincronizados {len(seen_ids)} ítems.")
