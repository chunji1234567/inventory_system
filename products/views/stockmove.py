from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

from products.models import Warehouse, Item, StockMove, StockBalance, MoveType


@login_required
def inbound_create(request):
    if request.method != "POST":
        return redirect(reverse("products:inventory_dashboard"))

    warehouse_id = request.POST.get("warehouse_id")
    item_id = request.POST.get("item_id")
    qty_str = (request.POST.get("quantity") or "").strip()
    reference = (request.POST.get("reference") or "").strip()
    note = (request.POST.get("note") or "").strip()

    try:
        qty = Decimal(qty_str)
        if qty <= 0:
            raise ValueError
    except Exception:
        messages.error(request, "入库失败：数量必须是 > 0 的数字")
        return redirect(reverse("products:inventory_dashboard"))

    warehouse = Warehouse.objects.filter(id=warehouse_id, is_active=True).first()
    item = Item.objects.filter(id=item_id, is_active=True).first()
    
    if not warehouse or not item:
        messages.error(request, "入库失败：仓库或物品不存在/未启用")
        return redirect(reverse("products:inventory_dashboard"))

    StockMove.objects.create(
        move_type=MoveType.INBOUND,
        warehouse=warehouse,
        item=item,
        quantity=qty,   # 入库：正数
        reference=reference,
        note=note,
    )
    messages.success(request, "入库成功")
    return redirect(reverse("products:inventory_dashboard"))


@login_required
def outbound_create(request):
    if request.method != "POST":
        return redirect(reverse("products:inventory_dashboard"))

    warehouse_id = request.POST.get("warehouse_id")
    item_id = request.POST.get("item_id")
    qty_str = (request.POST.get("quantity") or "").strip()
    reference = (request.POST.get("reference") or "").strip()
    note = (request.POST.get("note") or "").strip()

    # 1) 校验数量
    try:
        qty = Decimal(qty_str)
        if qty <= 0:
            raise ValueError
    except Exception:
        messages.error(request, "出库失败：数量必须是 > 0 的数字")
        return redirect(reverse("products:inventory_dashboard"))

    # 2) 校验仓库/物品存在
    warehouse = Warehouse.objects.filter(id=warehouse_id, is_active=True).first()
    item = Item.objects.filter(id=item_id, is_active=True).first()
    if not warehouse or not item:
        messages.error(request, "出库失败：仓库或物品不存在/未启用")
        return redirect(reverse("products:inventory_dashboard"))

    # 3) ✅ 负库存校验：查余额，不够就拒绝
    bal = StockBalance.objects.filter(warehouse=warehouse, item=item).first()
    on_hand = bal.on_hand if bal else Decimal("0")
    if on_hand < qty:
        messages.error(
            request,
            f"出库失败：库存不足。当前 {on_hand}，本次要出 {qty}"
        )
        return redirect(reverse("products:inventory_dashboard"))

    # 4) 通过校验：创建出库流水（quantity 为负数）
    StockMove.objects.create(
        move_type=MoveType.OUTBOUND,
        warehouse=warehouse,
        item=item,
        quantity=-qty,
        reference=reference,
        note=note,
    )

    messages.success(request, "出库成功")
    return redirect(reverse("products:inventory_dashboard"))


@login_required
def adjust_create(request):
    if request.method != "POST":
        return redirect(reverse("products:inventory_dashboard"))

    warehouse_id = request.POST.get("warehouse_id")
    item_id = request.POST.get("item_id")
    qty_str = (request.POST.get("quantity") or "").strip()
    reference = (request.POST.get("reference") or "").strip()
    note = (request.POST.get("note") or "").strip()

    try:
        qty = Decimal(qty_str)
        if qty == 0:
            raise ValueError
    except Exception:
        messages.error(request, "调整失败：数量必须是非 0 数字，可正可负")
        return redirect(reverse("products:inventory_dashboard"))

    warehouse = Warehouse.objects.filter(id=warehouse_id, is_active=True).first()
    item = Item.objects.filter(id=item_id).first()
    if not warehouse or not item:
        messages.error(request, "调整失败：仓库或物品不存在/未启用")
        return redirect(reverse("products:inventory_dashboard"))

    StockMove.objects.create(
        move_type=MoveType.ADJUST,
        warehouse=warehouse,
        item=item,
        quantity=qty,
        reference=reference,
        note=note,
    )

    messages.success(request, "库存已调整")
    return redirect(reverse("products:inventory_dashboard"))
