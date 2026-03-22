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
