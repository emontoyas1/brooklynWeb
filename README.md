# BrooklynShop

Tienda web para vender cosméticos de Fortnite en Colombia. El cliente compra en la web, un bot de Fortnite envía una solicitud de amistad automáticamente, y el operador entrega el regalo manualmente desde Fortnite después de 48 horas de amistad confirmada.

**Contexto completo del negocio:** `source/brooklyn_web_context.md`
**Tareas pendientes:** `PENDING.md`

---

## Arquitectura general

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENTE (Navegador)                 │
│  /  →  /shop/  →  /shop/<id>/  →  /checkout/<id>/      │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────┐
│                     VPS 2 — brooklynWeb                 │
│  Django 6 + Gunicorn + Nginx                            │
│                                                         │
│  ┌─────────┐  ┌──────────┐  ┌─────────────────────┐    │
│  │  shop   │  │  orders  │  │     fulfillment      │    │
│  │ catálogo│  │ checkout │  │  bot_coordinator.py  │    │
│  │  sync   │  │ webhook  │  │  BotAssignment       │    │
│  └─────────┘  └──────────┘  └──────────┬───────────┘    │
│                                         │ HTTP POST      │
│  PostgreSQL (producción)                │                │
│  SQLite     (desarrollo)                │                │
└─────────────────────────────────────────┼───────────────┘
                                          │
┌─────────────────────────────────────────▼───────────────┐
│                     VPS 1 — brooklynFortniteBot         │
│  Python + rebootpy                                      │
│  Bot 1: 127.0.0.1:8080                                  │
│  Bot 2: 127.0.0.1:8081                                  │
│  Bot 3: 127.0.0.1:8082                                  │
│  Bot 4: 127.0.0.1:8083                                  │
│  API: POST /api/friend-requests                         │
└─────────────────────────────────────────────────────────┘

Pagos externos:
  Cliente → MercadoPago → webhook POST /webhooks/mercadopago/ → brooklynWeb
Catálogo externo:
  cron → fortnite-api.com/v2/shop → sync_item_shop → Product (BD)
```

---

## Flujo completo de un pedido

```
1.  Cliente elige ítem en /shop/
2.  Llena /checkout/<id>/: epic_nickname, contacto, acepta condiciones
3.  POST crea Order con status='pending_payment' y product_snapshot
4.  Backend llama create_preference(order) → MercadoPago devuelve URL de pago
5.  Cliente redirige a MercadoPago (sandbox_init_point en DEV, init_point en PROD)
6.  Cliente paga con PSE / Nequi / Daviplata / tarjeta
7.  MercadoPago llama POST /webhooks/mercadopago/ con el payment id
8.  Backend valida firma X-Signature (si MP_WEBHOOK_SECRET está configurado)
9.  Backend consulta el pago a la API de MP con sdk.payment().get(id)
10. Si status='approved': order.status='paid', guarda payment_confirmed_at
11. Llama dispatch_friend_request(order) → selecciona bot con menos amigos (<240)
12. POST {bot.api_url}/api/friend-requests → {nickname, order_id}
13. Bot resuelve nickname → account_id, envía solicitud de amistad
14. Guarda BotAssignment (qué bot atendió este pedido — crítico para el regalo)
15. order.status = 'friend_request_sent' / 'failed_nickname' / 'failed_privacy' / etc.

--- Intervención manual del admin ---
16. Admin verifica en Fortnite que el cliente aceptó
17. Django Admin → acción "Confirmar amistad"
    → order.status='friendship_confirmed', guarda friendship_confirmed_at

--- Cron automático cada 15 min ---
18. check_ready_to_gift: si friendship_confirmed_at + 48h ≤ ahora
    → order.status='ready_to_gift', guarda ready_to_gift_at

--- Intervención manual del admin ---
19. Admin abre Fortnite, entra a la cuenta del bot indicado en BotAssignment
20. Envía el regalo manualmente
21. Django Admin → acción "Marcar como entregado"
    → order.status='delivered', guarda delivered_at
```

> **Por qué BotAssignment es crítico:** El cliente es amigo de *un bot específico*, no de todos. Sin este registro no sabes desde qué cuenta Fortnite enviar el regalo.

> **Por qué product_snapshot:** Si el ítem sale de la tienda y se borra de Product, la orden debe seguir mostrando el nombre, imagen y precio que tenía al momento de la compra.

---

## Estructura del proyecto

```
brooklynWeb/
├── brooklynWeb/                    # Configuración Django
│   ├── settings.py                 # Lee todo desde .env con python-dotenv
│   ├── urls.py                     # Router principal
│   ├── wsgi.py / asgi.py
├── shop/                           # App: catálogo
│   ├── models.py                   # Product
│   ├── views.py                    # home, catalog (agrupado por tipo), product_detail
│   ├── urls.py                     # /, /shop/, /shop/<item_id>/
│   └── management/commands/
│       └── sync_item_shop.py       # Sincroniza Fortnite-API → BD (cron diario)
├── orders/                         # App: pedidos y pagos
│   ├── models.py                   # Order (tabla central)
│   ├── views.py                    # checkout, order_status, order_success, webhook_mercadopago
│   ├── admin.py                    # OrderAdmin: confirm_friendship, mark_delivered
│   ├── urls.py                     # /checkout/, /orders/, /webhooks/mercadopago/
│   ├── services/
│   │   └── mercadopago.py          # create_preference(order) → URL de pago MP
│   └── management/commands/
│       └── check_ready_to_gift.py  # Marca ready_to_gift tras 48h (cron cada 15min)
├── fulfillment/                    # App: bots y entrega
│   ├── models.py                   # Bot, BotAssignment, FulfillmentNote
│   ├── admin.py                    # BotAdmin (list_editable is_active), BotAssignmentAdmin
│   └── services/
│       └── bot_coordinator.py      # get_available_bot, dispatch_friend_request
├── templates/
│   ├── base.html                   # Layout general (tema oscuro estilo Fortnite)
│   ├── shop/
│   │   ├── home.html               # Landing con hero + pasos + productos destacados
│   │   ├── catalog.html            # Catálogo agrupado por tipo con encabezados
│   │   └── product_detail.html     # Detalle + precio COP + badge outDate + botón comprar
│   └── orders/
│       ├── checkout.html           # Formulario: nickname, email, contacto, términos
│       ├── order_success.html      # Confirmación post-pago con pasos siguientes
│       ├── order_status.html       # Estado del pedido con timeline de 5 pasos
│       └── _status_body.html       # Partial reutilizable del timeline
├── source/
│   └── brooklyn_web_context.md     # Documento de arquitectura original del proyecto
├── .env                            # Variables de entorno (NO subir a git)
├── .gitignore
├── requirements.txt
├── PENDING.md                      # Tareas pendientes
└── manage.py
```

---

## Modelos de base de datos

### Product (app: shop)
```python
fortnite_item_id  CharField unique    # ID de Fortnite ej: CID_663_Athena...
name              CharField
type              CharField           # outfit, emote, pickaxe, backpack, glider, wrap, shoe, sidekick
price_vbucks      IntegerField        # Precio original en V-Bucks
price_cop         DecimalField        # Calculado: vbucks × 16.2 (100 VB = 1,620 COP)
image_url         URLField            # images.icon de Fortnite-API
is_available      BooleanField        # False si no está en la tienda hoy
last_seen_in_shop DateTimeField null
out_date          DateTimeField null  # Fecha en que sale de la tienda (mostrar en detalle)
```

### Order (app: orders) — tabla central
```python
order_id                UUIDField unique auto   # Identificador público del pedido
status                  CharField choices       # Ver estados abajo
product                 FK → Product PROTECT
product_snapshot        JSONField               # Copia de name/image/price al momento de compra
price_paid              DecimalField            # Precio en COP que pagó el cliente
epic_nickname           CharField               # Nombre exacto en Fortnite
customer_email          EmailField blank
customer_contact        CharField blank         # WhatsApp o Discord
payment_provider        CharField default='mercadopago'
payment_id              CharField blank         # ID del pago en MercadoPago
payment_confirmed_at    DateTimeField null
friend_request_sent_at  DateTimeField null
friendship_confirmed_at DateTimeField null      # Admin lo confirma manualmente
ready_to_gift_at        DateTimeField null      # Cron lo marca tras 48h
delivered_at            DateTimeField null
bot_response_json       JSONField null          # Respuesta cruda del bot
admin_notes             TextField blank
created_at              DateTimeField auto
```

**Estados de Order:**
```
pending_payment → paid → friend_request_sent → awaiting_acceptance
    → friendship_confirmed → ready_to_gift → delivered

Errores: failed_nickname | failed_privacy | no_bot_available | retry_pending
```

> Las 48h se cuentan desde `friendship_confirmed_at`, NO desde `friend_request_sent_at`.

### Bot (app: fulfillment)
```python
name          CharField
api_url       CharField    # http://127.0.0.1:8080
api_token     CharField    # Token Bearer para autenticar con el bot
friend_count  IntegerField # Se incrementa con cada solicitud enviada
is_active     BooleanField # Editable desde listado en Admin
last_used     DateTimeField null
```

### BotAssignment (app: fulfillment)
```python
order           OneToOne → Order CASCADE
bot             FK → Bot PROTECT
epic_account_id CharField    # account_id que resolvió el bot para el nickname
assigned_at     DateTimeField auto
bot_response_code CharField blank
```

### FulfillmentNote (app: fulfillment)
```python
order       FK → Order CASCADE related_name='notes'
note        TextField
created_by  FK → User SET_NULL null
created_at  DateTimeField auto
```

---

## URLs

| URL | Vista | Descripción |
|---|---|---|
| `/` | `shop:home` | Landing con hero, pasos y 6 ítems aleatorios |
| `/shop/` | `shop:catalog` | Catálogo agrupado: Skins → Emotes → Picos → ... |
| `/shop/<item_id>/` | `shop:product_detail` | Detalle + precio COP + badge "se va el DD/MM" |
| `/checkout/<item_id>/` | `orders:checkout` | Formulario de compra (GET/POST) |
| `/orders/<uuid>/` | `orders:order_status` | Seguimiento del pedido con timeline |
| `/orders/<uuid>/success/` | `orders:order_success` | Confirmación post-pago |
| `/webhooks/mercadopago/` | `orders:webhook_mercadopago` | Recibe notificaciones de MP (csrf_exempt) |
| `/admin/` | Django Admin | Panel de operación del negocio |

---

## Lógica clave

### Precio en COP
```python
# sync_item_shop.py
VBUCKS_TO_COP = Decimal('16.2')   # 100 V-Bucks = 1,620 COP
price_cop = round(Decimal(price_vbucks) * VBUCKS_TO_COP)
```
El precio se calcula automáticamente al sincronizar. Se puede editar manualmente en Django Admin si se necesita un precio diferente.

### Selección de bot (bot_coordinator.py)
```python
# Selecciona el bot activo con menos amigos (límite: 240)
Bot.objects.filter(is_active=True, friend_count__lt=240).order_by('friend_count').first()
```
Con múltiples bots, siempre se usa el menos cargado. Si todos superan 240 → `order.status = 'no_bot_available'`.

### Webhook MercadoPago (orders/views.py)
- Endpoint: `POST /webhooks/mercadopago/` — CSRF exempt
- Valida firma HMAC-SHA256 con `MP_WEBHOOK_SECRET` si está configurado
- Consulta el pago a la API de MP con `sdk.payment().get(id)`
- Si `status='approved'` y orden en `pending_payment` → marca como pagado y dispara bot
- Si `status='rejected'` → deja en `pending_payment` para reintento

### Catálogo ordenado por tipo (shop/views.py)
```python
TYPE_ORDER = Case(
    When(type='outfit',   then=1),
    When(type='emote',    then=2),
    When(type='pickaxe',  then=3),
    When(type='backpack', then=4),
    When(type='glider',   then=5),
    When(type='wrap',     then=6),
    When(type='shoe',     then=7),
    When(type='sidekick', then=8),
    default=9,
)
```
La vista agrupa los productos en dicts `{label, items}` antes de pasarlos al template, porque los templates de Django no soportan variables mutables en bucles.

---

## Variables de entorno (.env)

```env
# Django
SECRET_KEY=           # Generar: py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DEBUG=True            # False en producción
ALLOWED_HOSTS=localhost,127.0.0.1
ENVIRONMENT=development   # 'production' en VPS 2

# URL base (ngrok en desarrollo, dominio real en producción)
SITE_URL=http://127.0.0.1:8000

# Base de datos (solo se usa si ENVIRONMENT=production)
DB_NAME=brooklyn_web
DB_USER=brooklyn
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# Bots de Fortnite (VPS 1)
BOT_1_URL=http://127.0.0.1:8080
BOT_1_TOKEN=
BOT_2_URL=http://127.0.0.1:8081
BOT_2_TOKEN=
BOT_3_URL=http://127.0.0.1:8082
BOT_3_TOKEN=
BOT_4_URL=http://127.0.0.1:8083
BOT_4_TOKEN=

# MercadoPago
MP_ACCESS_TOKEN=      # TEST-... en sandbox, APP_USR-... en producción
MP_WEBHOOK_SECRET=    # Secreto del webhook configurado en el panel de MP

# Fortnite API
FORTNITE_API_KEY=     # fortnite-api.com — ya configurada
```

---

## Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Backend | Django | 6.0.3 |
| Runtime | Python | 3.12.10 |
| BD desarrollo | SQLite | (sin configuración) |
| BD producción | PostgreSQL | — |
| ORM PostgreSQL | psycopg3 | 3.3.3 |
| Variables de entorno | python-dotenv | 1.2.2 |
| HTTP requests | requests | 2.32.5 |
| Pagos | mercadopago SDK | 2.3.0 |
| Servidor producción | Gunicorn + Nginx | — |
| Catálogo | Fortnite-API.com | `/v2/shop` |
| Tareas programadas | cron + management commands | — |
| Panel admin | Django Admin | — |

---

## Setup local (primera vez)

```powershell
# 1. El .venv ya existe con Python 3.12. Activarlo:
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Generar SECRET_KEY y ponerla en .env
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Migraciones
python manage.py migrate

# 5. Sincronizar catálogo de Fortnite
python manage.py sync_item_shop

# 6. Crear superusuario
python manage.py createsuperuser

# 7. Correr servidor
python manage.py runserver
# → http://127.0.0.1:8000/        tienda pública
# → http://127.0.0.1:8000/admin/  panel de operación
```

---

## Comandos de operación

```bash
# Sincronizar catálogo con Fortnite (cron diario a las 00:15 UTC)
python manage.py sync_item_shop

# Revisar pedidos listos para regalar (cron cada 15 min)
python manage.py check_ready_to_gift

# Cargar un bot en la BD (solo la primera vez en producción)
python manage.py shell
>>> from fulfillment.models import Bot
>>> Bot.objects.create(name="Bot1", api_url="http://127.0.0.1:8080", api_token="TOKEN_AQUI")
```

---

## Probar MercadoPago en sandbox (cuando esté listo)

```
1. Crear cuenta en mercadopago.com.co (requiere ser mayor de edad con cédula)
2. Ir a: mercadopago.com.co/developers/panel → crear app "brooklynShop"
3. Credenciales de prueba → copiar Access Token (empieza con TEST-...)
4. Pegar en .env: MP_ACCESS_TOKEN=TEST-...
5. Instalar ngrok: https://ngrok.com/download
6. Correr: ngrok http 8000 → copiar URL (ej: https://abc123.ngrok.io)
7. Pegar en .env: SITE_URL=https://abc123.ngrok.io
8. En panel MP → Webhooks → agregar: https://abc123.ngrok.io/webhooks/mercadopago/
9. Tarjetas de prueba MP: https://www.mercadopago.com.co/developers/es/docs/your-integrations/test/cards
```

---

## Cron en producción (VPS 2)

```bash
# Editar crontab:
crontab -e

# Sincronizar tienda (00:15 UTC — cuando Epic rota la tienda)
15 0 * * * /home/brooklyn/brooklynWeb/.venv/bin/python /home/brooklyn/brooklynWeb/manage.py sync_item_shop >> /var/log/brooklyn/sync_shop.log 2>&1

# Revisar pedidos listos para regalar (cada 15 minutos)
*/15 * * * * /home/brooklyn/brooklynWeb/.venv/bin/python /home/brooklyn/brooklynWeb/manage.py check_ready_to_gift >> /var/log/brooklyn/ready_gift.log 2>&1
```

---

## Despliegue en VPS 2 (orden de pasos)

```bash
# 1. Clonar repo
git clone https://github.com/TU_USUARIO/brooklynWeb.git /home/brooklyn/brooklynWeb
cd /home/brooklyn/brooklynWeb

# 2. Entorno virtual
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Crear .env con ENVIRONMENT=production y credenciales reales
#    (SECRET_KEY nueva, DB_PASSWORD, MP_ACCESS_TOKEN real, SITE_URL con dominio)

# 4. Base de datos PostgreSQL
sudo -u postgres createuser brooklyn
sudo -u postgres psql -c "ALTER USER brooklyn WITH PASSWORD 'TU_PASSWORD';"
sudo -u postgres createdb brooklyn_web --owner brooklyn

# 5. Migraciones y estáticos
python manage.py migrate
python manage.py collectstatic

# 6. Primer sync del catálogo
python manage.py sync_item_shop

# 7. Gunicorn como servicio systemd
# 8. Nginx como reverse proxy
# 9. Certbot para HTTPS (obligatorio para webhooks de MercadoPago)
# 10. Configurar crontab (ver sección anterior)
```

> Ver `PENDING.md` para el script completo de Nginx + Gunicorn.
