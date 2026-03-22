from django.conf import settings
from django.db import models
from orders.models import Order


class Bot(models.Model):
    name = models.CharField(max_length=50)
    api_url = models.CharField(max_length=200)      # ej: http://127.0.0.1:8080
    api_token = models.CharField(max_length=200)
    friend_count = models.IntegerField(default=0)   # actualizar tras cada pedido
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.api_url})"


class BotAssignment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    bot = models.ForeignKey(Bot, on_delete=models.PROTECT)
    epic_account_id = models.CharField(max_length=100)   # account_id resuelto por el bot
    assigned_at = models.DateTimeField(auto_now_add=True)
    bot_response_code = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Asignación orden {self.order.order_id} → {self.bot.name}"


class FulfillmentNote(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota orden {self.order.order_id} — {self.created_at:%Y-%m-%d %H:%M}"
