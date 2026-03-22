# Tareas pendientes — BrooklynShop

---

## 🔴 Bloqueantes (sin esto el negocio no puede operar)

### 1. Credenciales MercadoPago
**Qué falta:** El dueño necesita crear cuenta en MercadoPago con cédula (mayor de edad).
**Pasos cuando esté listo:**
1. Crear cuenta en mercadopago.com.co
2. Ir a Developers → crear app "brooklynShop"
3. Copiar Access Token sandbox (`TEST-...`) → pegar en `.env` como `MP_ACCESS_TOKEN`
4. Para producción: usar el token real (`APP_USR-...`)

**El código ya está escrito** en `orders/services/mercadopago.py` y `orders/views.py`.
Solo falta el token.

---

### 2. Probar flujo completo de pago (sandbox)
**Qué falta:** Verificar que el ciclo completo funciona antes de lanzar.
**Pasos:**
1. Tener `MP_ACCESS_TOKEN=TEST-...` en `.env`
2. Instalar ngrok: https://ngrok.com/download
3. Correr `ngrok http 8000` → copiar URL
4. Poner `SITE_URL=https://xxxx.ngrok.io` en `.env`
5. Registrar webhook en panel MP → `https://xxxx.ngrok.io/webhooks/mercadopago/`
6. Hacer una compra de prueba con tarjeta sandbox de MP:
   - https://www.mercadopago.com.co/developers/es/docs/your-integrations/test/cards
7. Verificar que:
   - `order.status` pasa a `'paid'`
   - El email de confirmación llega al cliente (revisar consola en dev)
   - `dispatch_friend_request` se llama (revisar logs en terminal)
   - `BotAssignment` se crea en BD

---

### 3. Conectar bots reales
**Qué falta:** Registrar los bots en la base de datos de producción.
```python
# Correr en el shell de producción:
python manage.py shell
>>> from fulfillment.models import Bot
>>> Bot.objects.create(name="Bot1", api_url="http://127.0.0.1:8080", api_token="TOKEN_DEL_VPS")
>>> Bot.objects.create(name="Bot2", api_url="http://127.0.0.1:8081", api_token="TOKEN_DEL_VPS")
# ... etc
```
Los tokens deben coincidir con los que usa `brooklynFortniteBot` en el VPS 1.

---

## 🟡 Despliegue (necesario para que sea accesible al público)

### 4. Dominio
- Comprar dominio (ej: brooklynshop.co)
- Apuntar DNS al VPS 2
- Sin dominio no hay HTTPS, y sin HTTPS MercadoPago no envía webhooks en producción

### 5. VPS 2 — configuración inicial
**Nginx** (`/etc/nginx/sites-available/brooklynweb`):
```nginx
server {
    listen 80;
    server_name tudominio.com www.tudominio.com;

    location /static/ {
        alias /home/brooklyn/brooklynWeb/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Gunicorn como servicio** (`/etc/systemd/system/brooklynweb.service`):
```ini
[Unit]
Description=BrooklynShop Gunicorn
After=network.target

[Service]
User=brooklyn
WorkingDirectory=/home/brooklyn/brooklynWeb
EnvironmentFile=/home/brooklyn/brooklynWeb/.env
ExecStart=/home/brooklyn/brooklynWeb/.venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:8000 \
    brooklynWeb.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable brooklynweb
sudo systemctl start brooklynweb
```

**HTTPS con Certbot:**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com -d www.tudominio.com
```

**Crontab** (`crontab -e`):
```
15 0 * * * /home/brooklyn/brooklynWeb/.venv/bin/python /home/brooklyn/brooklynWeb/manage.py sync_item_shop >> /var/log/brooklyn/sync_shop.log 2>&1
*/15 * * * * /home/brooklyn/brooklynWeb/.venv/bin/python /home/brooklyn/brooklynWeb/manage.py check_ready_to_gift >> /var/log/brooklyn/ready_gift.log 2>&1
```

**Configurar email en producción** (después de crear cuenta en brevo.com):
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu@email.com
EMAIL_HOST_PASSWORD=tu_clave_smtp_brevo
DEFAULT_FROM_EMAIL=BrooklynShop <noreply@tudominio.com>
```

---

## 🟢 Mejoras (no bloquean el lanzamiento)

### 6. Logo y personalización visual
Animaciones ya implementadas. Queda pendiente:
- Agregar logo de la tienda cuando esté listo (en `templates/base.html`, reemplazar texto del nav)
- Fuente personalizada (reemplazar `'Segoe UI'` por una de Google Fonts en `base.html`)
- Imágenes de hero en la landing (`templates/shop/home.html`)
- Banner de promociones

**Cómo:** Variables CSS globales en `templates/base.html` en `:root {}`.

---

### 7. Ajuste de precios individual (`price_override`)
**Problema actual:** Si se edita `price_cop` manualmente en Admin, el siguiente `sync_item_shop`
lo pisa y lo calcula de nuevo automáticamente.

**Solución:** Agregar campo `price_override` al modelo `Product`:
```python
# shop/models.py
price_override = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
```
Y en `sync_item_shop.py`, respetar el override:
```python
price_cop = product.price_override if product.price_override else round(Decimal(price_vbucks) * VBUCKS_TO_COP)
```
Requiere migración.

---

### 8. Descripción del ítem en detalle de producto
La API de Fortnite devuelve `item['description']` (ej: "Wherever she goes trouble follows.")
pero no se guarda ni muestra.

**Qué agregar:**
- Campo `description = models.TextField(blank=True)` en `shop/models.py`
- En `sync_item_shop.py`: `description = entry.get('description', '')`
- En `templates/shop/product_detail.html`: mostrar debajo del nombre

Requiere migración.

---

### 9. Rareza del ítem (badge de color)
La API devuelve `item['rarity']['displayValue']` (Common, Uncommon, Rare, Epic, Legendary, Icon Series).

**Qué agregar:**
- Campo `rarity = models.CharField(max_length=50, blank=True)` en `shop/models.py`
- En `sync_item_shop.py`: `rarity = entry.get('rarity', {}).get('value', '')`
- Badge de color en las tarjetas del catálogo y en el detalle

Colores sugeridos por rareza:
| Rareza | Color |
|---|---|
| common | gris |
| uncommon | verde |
| rare | azul |
| epic | morado |
| legendary | naranja |
| icon | cian |

Requiere migración.

---

### 10. Video showcase en detalle de producto
La API devuelve `item['showcaseVideo']` (ID de YouTube).

**Qué agregar:**
- Campo `showcase_video = models.CharField(max_length=20, blank=True)` en `shop/models.py`
- En `sync_item_shop.py`: `showcase_video = entry.get('showcaseVideo', '') or ''`
- En `templates/shop/product_detail.html`: embed de YouTube si existe el campo

Requiere migración.

---

### 11. Notificación al admin cuando llega un pedido
Un aviso inmediato cuando `order.status` cambia a `'paid'`.
Útil para reaccionar rápido si el bot falla o el cliente necesita ayuda.

**Opciones:**
- **Email al admin** — más sencillo, usar `send_mail` con `ADMIN_EMAIL` en `.env`
- **Telegram** — más rápido, requiere crear un bot con BotFather y un `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`

**Dónde agregarlo:** en `orders/views.py`, función `_process_payment`, junto al `send_order_confirmation`.

---

### 12. Reintentos automáticos de pedidos fallidos
Si un pedido queda en `retry_pending` (bot falló al enviar la solicitud de amistad),
actualmente no hay mecanismo automático para reintentarlo.

**Solución:** Crear `orders/management/commands/retry_failed_orders.py`:
```python
# Reintenta dispatch_friend_request en pedidos con status='retry_pending'
# Agregar al crontab: */30 * * * * python manage.py retry_failed_orders
```

---

### 13. Páginas de error personalizadas (404 y 500)
Actualmente Django muestra sus páginas genéricas en producción (`DEBUG=False`).

**Qué crear:**
- `templates/404.html` — página "no encontrado" con estilo BrooklynShop
- `templates/500.html` — página "error del servidor"

Ambas deben extender `base.html` y tener un botón para volver a la tienda.
**Nota:** Solo se ven con `DEBUG=False`.

---

## Estado general del proyecto

| Bloque | Estado |
|---|---|
| Setup Django + modelos + migraciones | ✅ Completo |
| Django Admin operativo | ✅ Completo |
| Bot Coordinator | ✅ Completo |
| Management commands (sync + check) | ✅ Completo |
| Tienda pública (catálogo, detalle, checkout) | ✅ Completo |
| Precio COP auto-calculado | ✅ Completo |
| Integración MercadoPago (código) | ✅ Código listo |
| Animaciones CSS/JS | ✅ Completo |
| Email de confirmación al cliente | ✅ Código listo (falta credencial Brevo en producción) |
| Repositorio GitHub | ✅ https://github.com/emontoyas1/brooklynWeb |
| MercadoPago probado en sandbox | ⏳ Pendiente (falta cédula para crear cuenta) |
| Bots reales conectados | ⏳ Pendiente (falta registrarlos en BD de producción) |
| Dominio | ⏳ Pendiente (por comprar) |
| VPS 2 configurado | ⏳ Pendiente |
| HTTPS | ⏳ Pendiente (necesita dominio primero) |
| Logo / fuente personalizada | ⏳ Pendiente (sin logo aún) |
| price_override en sync | ⏳ Pendiente |
| Descripción del ítem | ⏳ Pendiente |
| Rareza del ítem | ⏳ Pendiente |
| Video showcase | ⏳ Pendiente |
| Notificación al admin | ⏳ Pendiente |
| Reintentos automáticos | ⏳ Pendiente |
| Páginas 404 y 500 personalizadas | ⏳ Pendiente |
