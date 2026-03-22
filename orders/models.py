import uuid
from django.db import models
from shop.models import Product


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

    def __str__(self):
        return f"Orden {self.order_id} — {self.epic_nickname} ({self.status})"
