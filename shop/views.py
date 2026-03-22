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


def home(request):
    featured = Product.objects.filter(is_available=True).order_by('?')[:6]
    return render(request, 'shop/home.html', {'featured': featured})


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


def catalog(request):
    products = (
        Product.objects
        .filter(is_available=True)
        .annotate(sort_order=TYPE_ORDER)
        .order_by('sort_order', 'name')
    )

    # Agrupar por tipo para el template
    groups = []
    current_type = None
    current_items = []
    for p in products:
        if p.type != current_type:
            if current_items:
                groups.append({'label': TYPE_LABELS.get(current_type, current_type.capitalize()), 'items': current_items})
            current_type = p.type
            current_items = [p]
        else:
            current_items.append(p)
    if current_items:
        groups.append({'label': TYPE_LABELS.get(current_type, current_type.capitalize()), 'items': current_items})

    return render(request, 'shop/catalog.html', {'groups': groups, 'total': products.count()})


def product_detail(request, item_id):
    product = get_object_or_404(Product, fortnite_item_id=item_id, is_available=True)
    return render(request, 'shop/product_detail.html', {'product': product})
