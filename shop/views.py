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

    # ── 1. PAQUETES ──────────────────────────────────────────────
    bundles = list(products.filter(is_bundle=True).order_by('name'))
    if bundles:
        groups.append({'label': '📦 Paquetes', 'items': bundles, 'is_bundle_group': True})

    # ── 2. POR COLECCIÓN (ítems con set, sin ser bundle) ─────────
    items_with_set = products.filter(is_bundle=False, series_name__gt='').order_by('series_name', 'name')

    sets = {}
    for p in items_with_set:
        sets.setdefault(p.series_name, []).append(p)

    # Ordenar colecciones de mayor a menor cantidad de ítems
    for set_name, items in sorted(sets.items(), key=lambda x: (-len(x[1]), x[0])):
        groups.append({'label': set_name, 'items': items, 'is_bundle_group': False})

    # ── 3. SIN COLECCIÓN (agrupados por tipo) ────────────────────
    items_no_set = (
        products
        .filter(is_bundle=False, series_name='')
        .annotate(sort_order=TYPE_ORDER)
        .order_by('sort_order', 'name')
    )

    type_groups = {}
    for p in items_no_set:
        type_groups.setdefault(p.type, []).append(p)

    for type_key in sorted(type_groups.keys(), key=lambda t: TYPE_ORDER_DICT.get(t, 9)):
        label = TYPE_LABELS.get(type_key, type_key.capitalize())
        groups.append({'label': label, 'items': type_groups[type_key], 'is_bundle_group': False})

    return render(request, 'shop/catalog.html', {'groups': groups, 'total': total})


def product_detail(request, item_id):
    product = get_object_or_404(Product, fortnite_item_id=item_id, is_available=True)
    return render(request, 'shop/product_detail.html', {'product': product})
