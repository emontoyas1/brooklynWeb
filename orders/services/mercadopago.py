import mercadopago
from django.conf import settings


def get_mp_sdk():
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def create_preference(order):
    """
    Crea una preferencia de pago en MercadoPago y retorna la URL de checkout.
    Documentación: https://www.mercadopago.com.co/developers/es/docs/checkout-pro
    """
    sdk = get_mp_sdk()

    snapshot = order.product_snapshot
    base_url = settings.SITE_URL  # ej: https://tudominio.com o ngrok URL

    preference_data = {
        "items": [
            {
                "id": str(order.order_id),
                "title": snapshot.get('name', 'Cosmético Fortnite'),
                "quantity": 1,
                "unit_price": float(order.price_paid),
                "currency_id": "COP",
            }
        ],
        "payer": {
            "email": order.customer_email or "cliente@brooklynshop.co",
        },
        "back_urls": {
            "success": f"{base_url}/orders/{order.order_id}/success/",
            "failure": f"{base_url}/orders/{order.order_id}/",
            "pending": f"{base_url}/orders/{order.order_id}/",
        },
        "auto_return": "approved",
        "notification_url": f"{base_url}/webhooks/mercadopago/",
        "external_reference": str(order.order_id),
        "statement_descriptor": "BrooklynShop",
    }

    result = sdk.preference().create(preference_data)
    return result["response"]
