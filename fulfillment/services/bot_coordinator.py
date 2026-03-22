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
    except requests.RequestException:
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
