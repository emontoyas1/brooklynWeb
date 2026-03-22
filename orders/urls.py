from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/<str:item_id>/', views.checkout, name='checkout'),
    path('orders/<uuid:order_id>/', views.order_status, name='order_status'),
    path('orders/<uuid:order_id>/success/', views.order_success, name='order_success'),
    path('webhooks/mercadopago/', views.webhook_mercadopago, name='webhook_mercadopago'),
]
