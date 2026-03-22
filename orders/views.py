import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from fulfillment.services.bot_coordinator import dispatch_friend_request
from shop.models import Product
from .models import Order
from .services.email import send_order_confirmation
from .services.mercadopago import create_preference, get_mp_sdk

logger = logging.getLogger(__name__)


@require_http_methods(['GET', 'POST'])
def checkout(request, item_id):
    product = get_object_or_404(Product, fortnite_item_id=item_id, is_available=True)

    if request.method == 'POST':
        epic_nickname = request.POST.get('epic_nickname', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()
        customer_contact = request.POST.get('customer_contact', '').strip()

        errors = {}
        if not epic_nickname:
            errors['epic_nickname'] = 'El nickname de Epic es obligatorio.'
        if not customer_contact:
            errors['customer_contact'] = 'El contacto (WhatsApp o Discord) es obligatorio.'

        if errors:
            return render(request, 'orders/checkout.html', {
                'product': product,
                'errors': errors,
                'form': request.POST,
            })

        order = Order.objects.create(
            product=product,
            product_snapshot={
                'name': product.name,
                'type': product.type,
                'image_url': product.image_url,
                'price_vbucks': product.price_vbucks,
                'price_cop': str(product.price_cop),
            },
            price_paid=product.price_cop,
            epic_nickname=epic_nickname,
            customer_email=customer_email,
            customer_contact=customer_contact,
        )

        try:
            preference = create_preference(order)
            # En sandbox usar sandbox_init_point, en producción usar init_point
            if settings.DEBUG:
                checkout_url = preference.get('sandbox_init_point')
            else:
                checkout_url = preference.get('init_point')
            return redirect(checkout_url)
        except Exception as e:
            logger.error(f"Error creando preferencia MP para orden {order.order_id}: {e}")
            # Si MP falla, mostramos la orden en estado pendiente
            return redirect('orders:order_status', order_id=order.order_id)

    return render(request, 'orders/checkout.html', {'product': product})


def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'orders/order_success.html', {'order': order})


def order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'orders/order_status.html', {'order': order})


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """
    Recibe notificaciones de pago de MercadoPago.
    MP envía dos tipos de notificaciones: IPN (legacy) y Webhooks (nuevo).
    Manejamos ambos.
    """
    # Validar firma si hay secret configurado
    if settings.MP_WEBHOOK_SECRET:
        if not _validate_mp_signature(request):
            logger.warning("Webhook MP: firma inválida")
            return HttpResponse(status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    topic = body.get('type') or request.GET.get('topic')
    resource_id = (
        body.get('data', {}).get('id') or
        request.GET.get('id') or
        body.get('id')
    )

    if topic not in ('payment', 'merchant_order'):
        # Ignorar notificaciones que no son de pago
        return HttpResponse(status=200)

    if not resource_id:
        return HttpResponse(status=200)

    try:
        _process_payment(str(resource_id))
    except Exception as e:
        logger.error(f"Error procesando webhook MP id={resource_id}: {e}")
        # Retornamos 200 para que MP no reintente infinitamente
        return HttpResponse(status=200)

    return HttpResponse(status=200)


def _process_payment(payment_id: str):
    sdk = get_mp_sdk()
    result = sdk.payment().get(payment_id)
    payment = result.get('response', {})

    status = payment.get('status')
    external_reference = payment.get('external_reference')  # nuestro order_id (UUID)

    if not external_reference:
        logger.warning(f"Pago {payment_id} sin external_reference")
        return

    try:
        order = Order.objects.get(order_id=external_reference)
    except Order.DoesNotExist:
        logger.warning(f"Webhook MP: orden {external_reference} no existe")
        return

    if status == 'approved':
        if order.status == 'pending_payment':
            order.status = 'paid'
            order.payment_id = str(payment_id)
            order.payment_confirmed_at = now()
            order.save()
            logger.info(f"Orden {order.order_id} marcada como pagada. Disparando bot...")
            send_order_confirmation(order)
            dispatch_friend_request(order)

    elif status in ('rejected', 'cancelled'):
        # Dejamos el pedido en pending_payment para que el cliente pueda reintentar
        logger.info(f"Pago {payment_id} rechazado/cancelado para orden {external_reference}")


def _validate_mp_signature(request) -> bool:
    """
    Valida la firma HMAC-SHA256 que MercadoPago envía en el header x-signature.
    Docs: https://www.mercadopago.com.co/developers/es/docs/your-integrations/notifications/webhooks
    """
    x_signature = request.headers.get('x-signature', '')
    x_request_id = request.headers.get('x-request-id', '')

    if not x_signature:
        return False

    # Extraer ts y v1 del header
    parts = dict(p.split('=', 1) for p in x_signature.split(',') if '=' in p)
    ts = parts.get('ts', '')
    v1 = parts.get('v1', '')

    if not ts or not v1:
        return False

    # Construir el manifest
    query_data_id = request.GET.get('data.id', '')
    manifest = f"id:{query_data_id};request-id:{x_request_id};ts:{ts};"

    expected = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(),
        manifest.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, v1)
