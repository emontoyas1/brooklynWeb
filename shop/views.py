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
    products = (
        Product.objects
        .filter(is_available=True)
        .order_by('layout_rank', '-sort_priority', 'name')
    )
    total = products.count()

    # Agrupar por sección de la tienda (layout_name), respetando el orden de Fortnite
    sections = {}
    section_rank = {}
    for p in products:
        key = p.layout_name or 'Otros'
        sections.setdefault(key, []).append(p)
        section_rank[key] = p.layout_rank

    groups = [
        {'label': name, 'items': items}
        for name, items in sorted(sections.items(), key=lambda x: section_rank[x[0]])
    ]

    return render(request, 'shop/catalog.html', {'groups': groups, 'total': total})


def product_detail(request, item_id):
    product = get_object_or_404(Product, fortnite_item_id=item_id, is_available=True)
    return render(request, 'shop/product_detail.html', {'product': product})
