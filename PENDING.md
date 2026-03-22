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
   - `dispatch_friend_request` se llama (revisa logs en terminal)
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

---

### 6. Repositorio en GitHub
```bash
git init
git add .
git commit -m "Initial commit: Django setup, models, admin, shop, checkout, MP integration"
git remote add origin https://github.com/TU_USUARIO/brooklynWeb.git
git push -u origin main
```
Sin repo no hay forma de hacer `git pull` en el VPS 2 para desplegar.

---

## 🟢 Mejoras (no bloquean el lanzamiento)

### 7. Tema visual personalizado
El diseño actual es funcional (oscuro, estilo Fortnite) pero genérico.
**Lo que se puede personalizar:**
- Logo / nombre de la tienda
- Paleta de colores (variables CSS en `templates/base.html`)
- Fuente (reemplazar `'Segoe UI'` por una de Google Fonts)
- Imágenes de hero en la landing (`templates/shop/home.html`)
- Banner de promociones

**Cómo:** Todo el CSS global está en `templates/base.html` en variables `:root {}`.

### 8. Ajuste de precios individual
Actualmente todos los precios se calculan automáticamente (vbucks × 16.2).
Si se quiere un precio diferente para un ítem específico, se puede editar
`price_cop` directamente en Django Admin (`/admin/shop/product/`).

**Mejora futura:** Agregar un campo `price_override` para que el sync no pise
los precios editados manualmente.

### 9. Descripción en detalle de producto
La API de Fortnite devuelve `item['description']` (ej: "Wherever she goes trouble follows.")
pero no la guardamos ni mostramos. Se puede agregar al modelo y al template de detalle.

### 10. Rareza del ítem
La API devuelve `item['rarity']['displayValue']` (Common, Uncommon, Rare, Epic, Legendary, Icon Series).
Se podría guardar y mostrar como badge de color en las tarjetas del catálogo.

### 11. Video showcase
La API devuelve `item['showcaseVideo']` (ID de YouTube).
Se podría embeber en la página de detalle del producto.

### 12. Email de confirmación al cliente
Cuando `order.status` cambia a `'paid'`, enviar un email con:
- Número de pedido (UUID)
- Nombre del ítem
- Instrucciones de qué hacer (esperar solicitud de amistad, aceptarla)
Requiere configurar `EMAIL_BACKEND` en settings y un proveedor SMTP (ej: SendGrid, Mailgun).

### 13. Notificación al admin cuando hay pedido nuevo
Un email o mensaje de Telegram cuando llega un pago confirmado.
Útil para reaccionar rápido si el bot falla.

### 14. Reintentos automáticos
Si un pedido queda en `retry_pending`, actualmente no hay mecanismo automático.
Se podría agregar un tercer management command `retry_failed_orders.py`
que reintente `dispatch_friend_request` en pedidos con ese estado.

### 15. Página 404 y 500 personalizadas
Actualmente Django muestra sus páginas de error genéricas.
Se pueden agregar `templates/404.html` y `templates/500.html`.

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
| MercadoPago probado en sandbox | ⏳ Pendiente (falta cédula para crear cuenta) |
| Bots reales conectados | ⏳ Pendiente (falta registrarlos en BD de producción) |
| Repositorio GitHub | ⏳ Pendiente |
| Dominio | ⏳ Pendiente (por comprar) |
| VPS 2 configurado | ⏳ Pendiente |
| HTTPS | ⏳ Pendiente (necesita dominio primero) |
| Tema visual personalizado | ⏳ Para después del lanzamiento |
