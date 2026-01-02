from django.db.models import Q
from django.shortcuts import render

from products.models import StockMove, Warehouse, Item, MoveType


def stockmove_list(request):
    warehouse_id = (request.GET.get("warehouse_id") or "").strip()
    item_id = (request.GET.get("item_id") or "").strip()
    move_type = (request.GET.get("move_type") or "ALL").strip().upper()
    allowed_types = {"ALL", MoveType.INBOUND, MoveType.OUTBOUND, MoveType.ADJUST}
    if move_type not in allowed_types:
        move_type = "ALL"
    q = (request.GET.get("q") or "").strip()

    moves = (
        StockMove.objects
        .select_related("warehouse", "item")
        .order_by("-created_at", "-id")
    )

    if warehouse_id:
        moves = moves.filter(warehouse_id=warehouse_id)

    if item_id:
        moves = moves.filter(item_id=item_id)

    if move_type == MoveType.INBOUND:
        moves = moves.filter(move_type=MoveType.INBOUND)
    elif move_type == MoveType.OUTBOUND:
        moves = moves.filter(move_type=MoveType.OUTBOUND)
    elif move_type == MoveType.ADJUST:
        moves = moves.filter(move_type=MoveType.ADJUST)

    if q:
        moves = moves.filter(
            Q(reference__icontains=q) |
            Q(note__icontains=q) |
            Q(item__sku__icontains=q) |
            Q(item__name__icontains=q) |
            Q(warehouse__name__icontains=q)
        )

    warehouses = Warehouse.objects.filter(is_active=True).order_by("name")
    items = Item.objects.filter(is_active=True).order_by("sku")
    move_type_options = [
        {"value": "ALL", "label": "全部", "active": move_type == "ALL"},
        {"value": MoveType.INBOUND, "label": "入库", "active": move_type == MoveType.INBOUND},
        {"value": MoveType.OUTBOUND, "label": "出库", "active": move_type == MoveType.OUTBOUND},
        {"value": MoveType.ADJUST, "label": "调整", "active": move_type == MoveType.ADJUST},
    ]

    return render(request, "products/stockmove_list.html", {
        "moves": moves,
        "warehouses": warehouses,
        "items": items,
        "warehouse_id": warehouse_id,
        "item_id": item_id,
        "q": q,
        "move_type": move_type,
        "move_type_options": move_type_options,
    })
