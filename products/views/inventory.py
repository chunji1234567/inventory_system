from collections import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from products.models import Warehouse, StockBalance, Item


@login_required
def inventory_dashboard(request):
    warehouse_id = (request.GET.get("warehouse_id") or "").strip()
    q = request.GET.get("q", "").strip()
    show_inactive = request.GET.get("show_inactive") == "1"

    inventory_items = Item.objects.select_related("warehouse").order_by("-created_at")

    if warehouse_id:
        inventory_items = inventory_items.filter(warehouse_id=warehouse_id)

    if q:
        inventory_items = inventory_items.filter(
            Q(name__icontains=q) |
            Q(warehouse__name__icontains=q)
        )

    if not show_inactive:
        inventory_items = inventory_items.filter(is_active=True)

    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    form_items = Item.objects.filter(is_active=True).order_by("name")

    all_balances = StockBalance.objects.select_related("warehouse", "item")
    balance_lookup = {}
    balance_data = {}
    for bal in all_balances:
        key = (bal.warehouse_id, bal.item_id)
        balance_lookup[key] = bal
        balance_data[f"{bal.warehouse_id}-{bal.item_id}"] = str(bal.on_hand)

    threshold = max(0, getattr(settings, "LOW_STOCK_ALERT_THRESHOLD", 0))

    low_stock_rows = []

    grouped = OrderedDict()
    for item in inventory_items:
        warehouse = item.warehouse
        wh_id = warehouse.id if warehouse else None
        group_key = wh_id or "__unassigned__"
        if group_key not in grouped:
            grouped[group_key] = {
                "warehouse": warehouse,
                "rows": [],
            }
        balance = balance_lookup.get((wh_id, item.id))
        quantity = balance.on_hand if balance else 0
        row_data = {
            "item": item,
            "on_hand": quantity,
            "updated_at": balance.updated_at if balance else None,
            "has_stock": quantity > 0,
            "is_low_stock": quantity < threshold,
        }
        grouped[group_key]["rows"].append(row_data)

        if row_data["is_low_stock"]:
            low_stock_rows.append({
                "item_name": item.name,
                "warehouse_name": warehouse.name if warehouse else "未分配仓库",
                "on_hand": quantity,
            })

    grouped_rows = sorted(
        grouped.values(),
        key=lambda grp: (grp["warehouse"].name if grp["warehouse"] else "")
    )

    return render(request, "products/inventory_dashboard.html", {
        "grouped_rows": grouped_rows,
        "warehouses": warehouses,
        "form_items": form_items,
        "selected_warehouse_id": warehouse_id,
        "q": q,
        "show_inactive": show_inactive,
        "balance_data": balance_data,
        "low_stock_threshold": threshold,
        "low_stock_rows": low_stock_rows,
    })
