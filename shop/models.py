from django.db import models


class Product(models.Model):
    fortnite_item_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=50)          # outfit, pickaxe, emote, etc.
    price_vbucks = models.IntegerField()
    price_cop = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    image_url = models.URLField()
    is_available = models.BooleanField(default=True)
    last_seen_in_shop = models.DateTimeField(null=True)
    out_date = models.DateTimeField(null=True, blank=True)
    series_name = models.CharField(max_length=100, blank=True)  # Set/collab: "MCU Avengers", "Balenciaga Fit"
    is_bundle = models.BooleanField(default=False)              # True si es un paquete multi-ítem
    layout_name = models.CharField(max_length=200, blank=True)  # Nombre de la sección en la tienda: "MCU Avengers"
    layout_rank = models.IntegerField(default=9999)             # Orden de la sección en la tienda
    sort_priority = models.IntegerField(default=0)              # Orden del ítem dentro de su sección

    def __str__(self):
        return f"{self.name} ({self.type})"
