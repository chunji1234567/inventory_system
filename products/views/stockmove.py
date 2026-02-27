from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from products.models import (
    Warehouse,
    Item,
    StockMove,
    StockBalance,
    MoveType,
    WarehouseType,
    Partner,
)
from products.views.inventory import _role_filter_kwargs


def _verify_form_token(request, key: str) -> bool:
    token = (request.POST.get("form_token") or "").strip()
    session_key = f"form_token_{key}"
    expected = request.session.get(session_key)
    if not token or not expected or token != expected:
        return False
    request.session.pop(session_key, None)
    return True


def _redirect_back(request):
    next_url = (request.POST.get("next") or "").strip()
    if not next_url:
        next_url = (request.META.get("HTTP_REFERER") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(reverse("products:inventory_dashboard"))


@login_required
def inbound_create(request):
    if request.method != "POST":
        return _redirect_back(request)

    if not _verify_form_token(request, "inbound"):
        messages.error(request, "请勿重复提交入库请求")
        return _redirect_back(request)

    role_context = _role_filter_kwargs(request.user)

    warehouse_id = request.POST.get("warehouse_id")
    item_id = request.POST.get("item_id")
    qty_str = (request.POST.get("quantity") or "").strip()
    reference = (request.POST.get("reference") or "").strip()
    note = (request.POST.get("note") or "").strip()
    partner_id = (request.POST.get("partner_id") or "").strip()

    try:
        qty = Decimal(qty_str)
        if qty <= 0:
            raise ValueError
    except Exception:
        messages.error(request, "入库失败：数量必须是 > 0 的数字")
        return _redirect_back(request)

    warehouse = (
        role_context["warehouse"]
        .filter(id=warehouse_id)
        .first()
    )
    item = Item.objects.filter(id=item_id, is_active=True, warehouse=warehouse).first()

    if not warehouse or not item:
        messages.error(request, "入库失败：仓库或物品不存在/未启用")
        return _redirect_back(request)

    partner = None
    if partner_id:
        partner = Partner.objects.filter(id=partner_id, is_active=True).first()
        if not partner:
            messages.error(request, "入库失败：合作方不存在或已停用")
            return _redirect_back(request)

    StockMove.objects.create(
        move_type=MoveType.INBOUND,
        warehouse=warehouse,
        item=item,
        quantity=qty,   # 入库：正数
        reference=reference,
        note=note,
        partner=partner,
    )
    messages.success(request, "入库成功")
    return _redirect_back(request)


@login_required
def outbound_create(request):
    if request.method != "POST":
        return _redirect_back(request)

    if not _verify_form_token(request, "outbound"):
        messages.error(request, "请勿重复提交出库请求")
        return _redirect_back(request)

    role_context = _role_filter_kwargs(request.user)

    warehouse_id = request.POST.get("warehouse_id")
    item_id = request.POST.get("item_id")
    qty_str = (request.POST.get("quantity") or "").strip()
    reference = (request.POST.get("reference") or "").strip()
    note = (request.POST.get("note") or "").strip()
    partner_id = (request.POST.get("partner_id") or "").strip()

    # 1) 校验数量
    try:
        qty = Decimal(qty_str)
        if qty <= 0:
            raise ValueError
    except Exception:
        messages.error(request, "出库失败：数量必须是 > 0 的数字")
        return _redirect_back(request)

    # 2) 校验仓库/物品存在
    warehouse = (
        role_context["warehouse"]
        .filter(id=warehouse_id)
        .first()
    )
    item = Item.objects.filter(id=item_id, is_active=True, warehouse=warehouse).first()
    if not warehouse or not item:
        messages.error(request, "出库失败：仓库或物品不存在/未启用")
        return _redirect_back(request)

    # 3) ✅ 负库存校验：查余额，不够就拒绝
    bal = StockBalance.objects.filter(warehouse=warehouse, item=item).first()
    on_hand = bal.on_hand if bal else Decimal("0")
    if on_hand < qty:
        messages.error(
            request,
            f"出库失败：库存不足。当前 {on_hand}，本次要出 {qty}"
        )
        return _redirect_back(request)

    # 4) 通过校验：创建出库流水（quantity 为负数）
    partner = None
    if partner_id:
        partner = Partner.objects.filter(id=partner_id, is_active=True).first()
        if not partner:
            messages.error(request, "出库失败：合作方不存在或已停用")
            return _redirect_back(request)

    StockMove.objects.create(
        move_type=MoveType.OUTBOUND,
        warehouse=warehouse,
        item=item,
        quantity=-qty,
        reference=reference,
        note=note,
        partner=partner,
    )

    messages.success(request, "出库成功")
    return _redirect_back(request)


@login_required
def adjust_create(request):
    if request.method != "POST":
        return _redirect_back(request)

    if not _verify_form_token(request, "adjust"):
        messages.error(request, "请勿重复提交库存调整")
        return _redirect_back(request)

    role_context = _role_filter_kwargs(request.user)

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
        return _redirect_back(request)

    warehouse = (
        role_context["warehouse"]
        .filter(id=warehouse_id)
        .first()
    )
    item = Item.objects.filter(id=item_id, warehouse=warehouse).first()
    if not warehouse or not item:
        messages.error(request, "调整失败：仓库或物品不存在/未启用")
        return _redirect_back(request)

    StockMove.objects.create(
        move_type=MoveType.ADJUST,
        warehouse=warehouse,
        item=item,
        quantity=qty,
        reference=reference,
        note=note,
    )

    messages.success(request, "库存已调整")
    return _redirect_back(request)
