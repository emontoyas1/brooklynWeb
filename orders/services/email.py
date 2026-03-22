import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_order_confirmation(order) -> None:
    """
    Envía email de confirmación al cliente cuando el pago es aprobado.
    Si el cliente no dejó email, no hace nada.
    """
    if not order.customer_email:
        return

    subject = f"✅ Pedido confirmado — {order.product_snapshot.get('name', 'tu ítem')}"

    context = {
        'order': order,
        'item_name': order.product_snapshot.get('name', ''),
        'item_image': order.product_snapshot.get('image_url', ''),
        'price_cop': order.price_paid,
        'order_url': f"{settings.SITE_URL}/orders/{order.order_id}/",
    }

    html_body = render_to_string('orders/emails/order_confirmation.html', context)
    text_body = (
        f"¡Pago confirmado! Tu pedido de {context['item_name']} está en proceso.\n\n"
        f"Número de pedido: {order.order_id}\n"
        f"Precio pagado: ${order.price_paid} COP\n\n"
        f"Próximos pasos:\n"
        f"1. Recibirás una solicitud de amistad en Fortnite desde nuestra cuenta bot.\n"
        f"2. Acepta la solicitud lo antes posible.\n"
        f"3. Después de 48 horas de amistad te enviamos el regalo.\n\n"
        f"Seguimiento: {context['order_url']}\n\n"
        f"— BrooklynShop"
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send()
        logger.info(f"Email de confirmación enviado a {order.customer_email} para orden {order.order_id}")
    except Exception as e:
        # El email nunca debe bloquear el flujo del pedido
        logger.error(f"Error enviando email para orden {order.order_id}: {e}")
