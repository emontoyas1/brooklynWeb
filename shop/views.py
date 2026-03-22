from django.shortcuts import render, get_object_or_404
from django.db.models import Case, When, IntegerField
from .models import Product

TYPE_ORDER = Case(
    When(type='outfit',   then=1),
    When(type='emote',    then=2),
    When(type='pickaxe',  then=3),
    When(type='backpack', then=4),
    When(type='glider',   then=5),
    When(type='wrap',     then=6),
    When(type='shoe',     then=7),
    When(type='sidekick', then=8),
    default=9,
    output_field=IntegerField(),
)

TYPE_ORDER_DICT = {
    'outfit': 1, 'emote': 2, 'pickaxe': 3, 'backpack': 4,
    'glider': 5, 'wrap': 6, 'shoe': 7, 'sidekick': 8,
}

TYPE_LABELS = {
    'outfit':   '👤 Skins',
    'emote':    '💃 Bailes y emotes',
    'pickaxe':  '⛏️ Picos',
    'backpack': '🎒 Mochilas',
    'glider':   '🪂 Planeadores',
    'wrap':     '🎨 Wraps',
    'shoe':     '👟 Zapatos',
    'sidekick': '🐾 Mascotas',
}


def home(request):
    featured = Product.objects.filter(is_available=True).order_by('?')[:6]
    return render(request, 'shop/home.html', {'featured': featured})


def catalog(request):
    products = Product.objects.filter(is_available=True)
    total = products.count()
    groups = []

    # ── 1. PAQUETES primero ───────────────────────────────────────
    bundles = list(products.filter(is_bundle=True).order_by('name'))
    if bundles:
        groups.append({'label': '📦 Paquetes', 'items': bundles, 'is_bundle': True})

    # ── 2. RESTO agrupado por tipo ────────────────────────────────
    rest = (
        products
        .filter(is_bundle=False)
        .annotate(sort_order=TYPE_ORDER)
        .order_by('sort_order', 'name')
    )

    type_groups = {}
    for p in rest:
        type_groups.setdefault(p.type, []).append(p)

    for type_key in sorted(type_groups.keys(), key=lambda t: TYPE_ORDER_DICT.get(t, 9)):
        label = TYPE_LABELS.get(type_key, type_key.capitalize())
        groups.append({'label': label, 'items': type_groups[type_key], 'is_bundle': False})

    return render(request, 'shop/catalog.html', {'groups': groups, 'total': total})


def product_detail(request, item_id):
    product = get_object_or_404(Product, fortnite_item_id=item_id, is_available=True)
    return render(request, 'shop/product_detail.html', {'product': product})
