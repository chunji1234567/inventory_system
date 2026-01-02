from django.db.models import Q
from django.shortcuts import render

from products.models import Warehouse, StockBalance, Item


def inventory_dashboard(request):
    warehouse_code = request.GET.get("warehouse", "").strip()
    q = request.GET.get("q", "").strip()
    show_inactive = request.GET.get("show_inactive") == "1"

    balances = (
        StockBalance.objects
        .select_related("warehouse", "item")
        .order_by("warehouse__code", "item__sku")
    )

    if warehouse_code:
        balances = balances.filter(warehouse__code=warehouse_code)

    if q:
        balances = balances.filter(Q(item__sku__icontains=q) | Q(item__name__icontains=q))

    warehouses = Warehouse.objects.filter(is_active=True).order_by("code")
    items = Item.objects.filter(is_active=True).order_by("sku")
    if not show_inactive:
        balances = balances.filter(item__is_active=True)

    all_balances = StockBalance.objects.select_related("warehouse", "item").all()
    balance_map = {
        f"{b.warehouse_id}-{b.item_id}": str(b.on_hand)  # str 保证 Decimal 可 JSON
        for b in all_balances
    }
    return render(request, "products/inventory_dashboard.html", {
        "balances": balances,
        "warehouses": warehouses,
        "items": items,
        "selected_warehouse": warehouse_code,
        "q": q,
        "show_inactive": show_inactive,
        "balance_map": balance_map,
    })
