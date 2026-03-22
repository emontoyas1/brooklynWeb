# Brooklyn Web — Contexto completo para el agente

## Qué es este proyecto

Tienda web para vender cosméticos de Fortnite. El cliente compra en la web, el sistema envía automáticamente una solicitud de amistad desde un bot de Fortnite, y cuando se cumplen las condiciones (amistad confirmada + 48 horas), el operador entrega el regalo manualmente desde Fortnite.

**Repositorio del bot:** https://github.com/emontoyas1/brooklynFortniteBot  
**Proyecto web (a crear):** `brooklynWeb` — separado del bot

---

## Infraestructura actual

- **VPS:** disponible, corriendo el bot (`brooklynFortniteBot`)
- **Bot:** Python 3.11, `rebootpy`, expone API HTTP local en `127.0.0.1:8080`
- **Dominio:** pendiente de comprar (requerido para HTTPS y webhooks de pago)
- **Bots planificados:** 4 o más, todos en el mismo VPS en puertos distintos (8080, 8081, 8082, 8083...)
- **Volumen inicial:** menos de 10 pedidos/día

---

## Stack tecnológico decidido

| Capa | Tecnología |
|---|---|
| Backend web | Django + PostgreSQL |
| ORM | psycopg (psycopg3) |
| Variables de entorno | python-dotenv |
| Servidor producción | Gunicorn + Nginx |
| Catálogo de ítems | Fortnite-API.com (`/v2/shop/br`) |
| Pagos | MercadoPago (Colombia — acepta PSE, Nequi, tarjetas locales) |
| Tareas programadas | cron + Django management commands (sin Celery por ahora) |
| Panel admin | Django Admin (sin panel custom en v1) |

---

## Apps Django a crear

```
brooklynWeb/
├── shop/          # catálogo, sincronización Item Shop, vista pública
├── orders/        # checkout, estados de pedido, webhook de pago
└── fulfillment/   # bot coordinator, asignación, cron de 48h
```

---

## Modelos de base de datos

### `Bot` (app: fulfillment)
```python
class Bot(models.Model):
    name = models.CharField(max_length=50)
    api_url = models.CharField(max_length=200)      # ej: http://127.0.0.1:8080
    api_token = models.CharField(max_length=200)
    friend_count = models.IntegerField(default=0)   # actualizar tras cada pedido
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
```

### `Product` (app: shop)
```python
class Product(models.Model):
    fortnite_item_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=50)          # outfit, pickaxe, emote, etc.
    price_vbucks = models.IntegerField()
    price_cop = models.DecimalField(max_digits=10, decimal_places=0)
    image_url = models.URLField()
    is_available = models.BooleanField(default=True)
    last_seen_in_shop = models.DateTimeField(null=True)
```

### `Order` (app: orders) — tabla central
```python
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Pendiente de pago'),
        ('paid', 'Pagado'),
        ('friend_request_sent', 'Solicitud enviada'),
        ('awaiting_acceptance', 'Esperando aceptación'),
        ('friendship_confirmed', 'Amistad confirmada'),
        ('ready_to_gift', 'Listo para regalar'),
        ('delivered', 'Entregado'),
        ('failed_nickname', 'Nickname no encontrado'),
        ('failed_privacy', 'Privacidad bloqueada'),
        ('no_bot_available', 'Sin bot disponible'),
        ('retry_pending', 'Reintento pendiente'),
    ]

    order_id = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_payment')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_snapshot = models.JSONField()           # CRÍTICO: guarda nombre, imagen y precio al momento de compra
    price_paid = models.DecimalField(max_digits=10, decimal_places=0)

    epic_nickname = models.CharField(max_length=100)
    customer_email = models.EmailField(blank=True)
    customer_contact = models.CharField(max_length=200, blank=True)  # WhatsApp o Discord

    payment_provider = models.CharField(max_length=50, default='mercadopago')
    payment_id = models.CharField(max_length=200, blank=True)
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)

    friend_request_sent_at = models.DateTimeField(null=True, blank=True)
    friendship_confirmed_at = models.DateTimeField(null=True, blank=True)  # lo confirma el admin manualmente
    ready_to_gift_at = models.DateTimeField(null=True, blank=True)         # lo marca el cron tras 48h
    delivered_at = models.DateTimeField(null=True, blank=True)

    bot_response_json = models.JSONField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

> **Nota importante:** `friend_request_sent_at` ≠ `friendship_confirmed_at`. El conteo de 48 horas empieza desde `friendship_confirmed_at`, no desde el envío de la solicitud.

### `BotAssignment` (app: fulfillment) — pieza clave nueva
```python
class BotAssignment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    bot = models.ForeignKey(Bot, on_delete=models.PROTECT)
    epic_account_id = models.CharField(max_length=100)   # account_id resuelto por el bot
    assigned_at = models.DateTimeField(auto_now_add=True)
    bot_response_code = models.CharField(max_length=50, blank=True)
```

> Este modelo es crítico con 4+ bots. Sin él no sabes desde qué cuenta entregar el regalo, porque el cliente es amigo de *un bot específico*, no de todos.

### `FulfillmentNote` (app: fulfillment)
```python
class FulfillmentNote(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## Arquitectura del Bot Coordinator

Archivo: `fulfillment/services/bot_coordinator.py`

```python
import requests
from django.utils.timezone import now
from fulfillment.models import Bot, BotAssignment
from orders.models import Order

def get_available_bot():
    """Retorna el bot activo con menos amigos. Límite: 240 (margen antes del límite de Fortnite)."""
    return Bot.objects.filter(
        is_active=True,
        friend_count__lt=240
    ).order_by('friend_count').first()

def dispatch_friend_request(order: Order):
    bot = get_available_bot()

    if not bot:
        order.status = 'no_bot_available'
        order.save()
        # TODO: enviar alerta al admin (email o log)
        return

    try:
        response = requests.post(
            f"{bot.api_url}/api/friend-requests",
            headers={"Authorization": f"Bearer {bot.api_token}"},
            json={"nickname": order.epic_nickname, "order_id": str(order.order_id)},
            timeout=30
        )
        data = response.json()
    except requests.RequestException as e:
        order.status = 'retry_pending'
        order.save()
        return

    # Guardar asignación
    BotAssignment.objects.create(
        order=order,
        bot=bot,
        epic_account_id=data.get('account_id', ''),
        bot_response_code=data.get('error_code', '')
    )

    # Mapear código HTTP a estado de orden
    status_map = {
        200: 'friend_request_sent',
        404: 'failed_nickname',
        403: 'failed_privacy',
        409: 'awaiting_acceptance',   # ya es amigo o solicitud ya enviada
        503: 'retry_pending',
        502: 'retry_pending',
    }
    order.status = status_map.get(response.status_code, 'retry_pending')
    order.friend_request_sent_at = now()
    order.bot_response_json = data
    order.save()

    # Actualizar conteo del bot
    bot.friend_count += 1
    bot.last_used = now()
    bot.save()
```

---

## Flujo completo de un pedido

```
1. Cliente elige ítem en la tienda (sincronizado desde Fortnite-API.com)
2. Cliente llena checkout: epic_nickname, contacto, acepta condiciones de entrega
3. Frontend redirige a MercadoPago
4. Cliente paga
5. MercadoPago llama POST /webhooks/mercadopago/
6. Backend valida firma del webhook
7. Backend marca order.status = 'paid', guarda payment_confirmed_at
8. Backend llama dispatch_friend_request(order)
9. Bot Coordinator selecciona bot con menos amigos (< 240)
10. Backend llama POST {bot.api_url}/api/friend-requests
11. Bot resuelve nickname → account_id y envía solicitud de amistad
12. Backend guarda BotAssignment y actualiza status según respuesta
13. Admin revisa pedidos con status 'awaiting_acceptance'
14. Admin verifica en Fortnite que el cliente aceptó
15. Admin hace clic en "Confirmar amistad" en Django Admin → guarda friendship_confirmed_at
16. Cron cada 15 min revisa: friendship_confirmed_at + 48h ≤ ahora → status = 'ready_to_gift'
17. Admin entra a Fortnite, manda el regalo desde el bot asignado (ver BotAssignment)
18. Admin marca order.status = 'delivered'
```

---

## Sincronización del catálogo

Archivo: `shop/management/commands/sync_item_shop.py`

```python
import requests
from django.utils.timezone import now
from django.core.management.base import BaseCommand
from shop.models import Product

class Command(BaseCommand):
    help = 'Sincroniza la Item Shop diaria de Fortnite'

    def handle(self, *args, **options):
        r = requests.get("https://fortnite-api.com/v2/shop/br", timeout=30)
        r.raise_for_status()
        data = r.json()['data']

        all_entries = data.get('featured', {}).get('entries', []) + \
                      data.get('daily', {}).get('entries', [])

        seen_ids = []

        for entry in all_entries:
            if not entry.get('items'):
                continue
            item = entry['items'][0]
            item_id = item['id']
            seen_ids.append(item_id)

            Product.objects.update_or_create(
                fortnite_item_id=item_id,
                defaults={
                    'name': item['name'],
                    'type': item['type']['value'],
                    'price_vbucks': entry.get('regularPrice', 0),
                    'image_url': item['images']['icon'],
                    'is_available': True,
                    'last_seen_in_shop': now(),
                }
            )

        # Marcar como no disponibles los que no aparecieron hoy
        Product.objects.exclude(fortnite_item_id__in=seen_ids).update(is_available=False)
        self.stdout.write(f"Sincronizados {len(seen_ids)} ítems.")
```

---

## Cron jobs (crontab del VPS)

```bash
# Sincronizar tienda diaria de Fortnite (00:15 UTC — cuando Epic rota la tienda)
15 0 * * * /home/brooklyn/brooklynWeb/.venv/bin/python manage.py sync_item_shop >> /var/log/brooklyn/sync_shop.log 2>&1

# Revisar pedidos listos para regalar (cada 15 minutos)
*/15 * * * * /home/brooklyn/brooklynWeb/.venv/bin/python manage.py check_ready_to_gift >> /var/log/brooklyn/ready_gift.log 2>&1
```

Archivo: `orders/management/commands/check_ready_to_gift.py`

```python
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
```

---

## Django Admin (configuración mínima para operar)

Archivo: `orders/admin.py`

```python
from django.contrib import admin
from django.utils.timezone import now
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'epic_nickname', 'status', 'created_at', 'friendship_confirmed_at', 'ready_to_gift_at']
    list_filter = ['status', 'payment_provider']
    search_fields = ['epic_nickname', 'customer_email', 'order_id']
    readonly_fields = ['order_id', 'created_at', 'bot_response_json']
    actions = ['confirm_friendship', 'mark_delivered']

    @admin.action(description="Confirmar amistad (inicia conteo de 48h)")
    def confirm_friendship(self, request, queryset):
        queryset.filter(status='awaiting_acceptance').update(
            status='friendship_confirmed',
            friendship_confirmed_at=now()
        )

    @admin.action(description="Marcar como entregado")
    def mark_delivered(self, request, queryset):
        queryset.filter(status='ready_to_gift').update(
            status='delivered',
            delivered_at=now()
        )
```

Archivo: `fulfillment/admin.py`

```python
from django.contrib import admin
from .models import Bot, BotAssignment

@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_url', 'friend_count', 'is_active', 'last_used']
    list_editable = ['is_active']

@admin.register(BotAssignment)
class BotAssignmentAdmin(admin.ModelAdmin):
    list_display = ['order', 'bot', 'epic_account_id', 'assigned_at']
```

---

## Páginas públicas (v1)

| Página | URL | Descripción |
|---|---|---|
| Inicio | `/` | Hero + CTA |
| Catálogo | `/shop/` | Ítems disponibles hoy (sincronizados) |
| Detalle | `/shop/<id>/` | Ítem individual + botón comprar |
| Checkout | `/checkout/<id>/` | Formulario: nickname, contacto, confirmación |
| Éxito | `/orders/<uuid>/success/` | Confirmación post-pago |
| Estado | `/orders/<uuid>/` | Estado del pedido en tiempo real |

**No crear cuentas de usuario en v1.** Compra como invitado. El UUID de la orden sirve como identificador del pedido para el cliente.

---

## Checkpoint de seguridad

- `API_TOKEN` del bot nunca en el frontend ni en JS del navegador
- `.env` y `device_auths.json` en `.gitignore`
- Webhook de MercadoPago: validar firma `X-Signature` antes de procesar
- Solo puertos 80/443 públicos en Nginx; el bot corre en 127.0.0.1 (privado)
- HTTPS obligatorio en producción (sin él MercadoPago no envía webhooks)

---

## Variables de entorno necesarias (.env)

```env
# Django
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=tudominio.com

# Base de datos
DB_NAME=brooklyn_web
DB_USER=brooklyn
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# Bots (uno por bot)
BOT_1_URL=http://127.0.0.1:8080
BOT_1_TOKEN=
BOT_2_URL=http://127.0.0.1:8081
BOT_2_TOKEN=
# ... etc

# MercadoPago
MP_ACCESS_TOKEN=
MP_WEBHOOK_SECRET=

# Fortnite API
FORTNITE_API_KEY=   # fortnite-api.com — opcional, aumenta rate limit
```

---

## Despliegue en VPS (orden de pasos)

```bash
# 1. Crear entorno
python3.11 -m venv .venv
source .venv/bin/activate
pip install django psycopg[binary] python-dotenv requests gunicorn

# 2. Crear proyecto Django
django-admin startproject brooklynWeb .
python manage.py startapp shop
python manage.py startapp orders
python manage.py startapp fulfillment

# 3. Migraciones
python manage.py makemigrations
python manage.py migrate

# 4. Cargar bots iniciales en BD
python manage.py shell
# >>> Bot.objects.create(name="Bot1", api_url="http://127.0.0.1:8080", api_token="...")

# 5. Primera sincronización de tienda
python manage.py sync_item_shop

# 6. Gunicorn como servicio systemd
# 7. Nginx como reverse proxy
# 8. Certbot para HTTPS
# 9. Configurar crontab
```

---

## Lo que NO hacer en v1

- No Celery/Redis (overkill para < 10 pedidos/día — usar cron simple)
- No cuentas de usuario (compra como invitado)
- No panel admin custom (usar Django Admin)
- No automatizar la entrega del regalo (es manual desde Fortnite)
- No intentar leer el Item Shop en tiempo real desde el frontend (sincronizar una vez al día)
- No exponer el bot directamente al navegador
- No subir `.env` ni `device_auths.json` al repositorio

---

## Próximo paso inmediato

Crear el proyecto Django con las tres apps, definir los modelos exactamente como están en este documento y correr las migraciones. Una vez que la BD esté lista, todo lo demás (coordinator, webhook, cron) tiene dónde anclar.
