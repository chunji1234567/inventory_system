import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from products.models import Item, Partner, MoveType, StockBalance, StockMove
from products.views.inventory import _role_filter_kwargs

ACTION_CHOICES = [
    (MoveType.INBOUND, "批量入库"),
    (MoveType.OUTBOUND, "批量出库"),
]
ACTION_TYPES = {choice for choice, _ in ACTION_CHOICES}
ACTION_LABELS = dict(ACTION_CHOICES)


def _serialize_items(allowed_warehouse_ids):
    items = list(
        Item.objects
        .select_related("warehouse", "unit")
        .filter(warehouse_id__in=allowed_warehouse_ids, is_active=True)
        .order_by("warehouse__name", "name")
    )
    item_ids = [item.id for item in items]
    balances = {}
    if item_ids:
        balances = {
            (balance.warehouse_id, balance.item_id): balance.on_hand
            for balance in StockBalance.objects.filter(
                warehouse_id__in=allowed_warehouse_ids,
                item_id__in=item_ids,
            )
        }
    serialized = []
    for item in items:
        warehouse_name = item.warehouse.name if item.warehouse else ""
        unit_name = item.unit.name if item.unit else ""
        on_hand = balances.get((item.warehouse_id, item.id), 0)
        serialized.append({
            "id": item.id,
            "name": item.name,
            "warehouse_id": item.warehouse_id,
            "warehouse_name": warehouse_name,
            "unit_name": unit_name,
            "on_hand": str(on_hand),
        })
    return items, serialized


def _clean_initial_rows(rows):
    clean_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean_rows.append({
            "client_id": row.get("client_id"),
            "warehouse_id": row.get("warehouse_id"),
            "item_id": row.get("item_id"),
            "quantity": row.get("quantity"),
            "reference": row.get("reference"),
            "note": row.get("note"),
            "partner_id": row.get("partner_id"),
        })
    return clean_rows


@login_required
def stock_import_start(request):
    role_context = _role_filter_kwargs(request.user)
    warehouses = role_context["warehouse"].order_by("name")
    if not warehouses.exists():
        messages.error(request, "当前账号没有可操作的仓库")
        return redirect(reverse("products:inventory_dashboard"))

    allowed_ids = list(warehouses.values_list("id", flat=True))
    warehouse_lookup = {w.id: w for w in warehouses}
    items, items_data = _serialize_items(allowed_ids)
    item_lookup = {item.id: item for item in items}

    partners = list(Partner.objects.filter(is_active=True).order_by("name"))
    partner_lookup = {partner.id: partner for partner in partners}

    initial_rows = []
    selected_action = request.POST.get("action_type") or MoveType.INBOUND

    if request.method == "POST":
        raw_payload = request.POST.get("payload") or "[]"
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            payload = []
            messages.error(request, "无法解析提交的数据，请重试")

        if not isinstance(payload, list):
            payload = []
            messages.error(request, "提交的数据格式不正确，请重试")

        if selected_action not in ACTION_TYPES:
            messages.error(request, "请选择入库或出库类型")

        normalized_rows = []
        outbound_requirements = defaultdict(int)
        errors = []

        for idx, entry in enumerate(payload, start=1):
            if not isinstance(entry, dict):
                errors.append(f"第 {idx} 行数据格式不正确")
                continue

            row_prefix = f"第 {idx} 行"

            try:
                warehouse_id = int(entry.get("warehouse_id"))
            except (TypeError, ValueError):
                errors.append(f"{row_prefix}：仓库无效")
                continue

            warehouse = warehouse_lookup.get(warehouse_id)
            if not warehouse:
                errors.append(f"{row_prefix}：仓库不存在或无权限")
                continue

            try:
                item_id = int(entry.get("item_id"))
            except (TypeError, ValueError):
                errors.append(f"{row_prefix}：物品无效")
                continue

            item = item_lookup.get(item_id)
            if not item or item.warehouse_id != warehouse_id:
                errors.append(f"{row_prefix}：物品不存在或不属于所选仓库")
                continue

            quantity_raw = entry.get("quantity")
            try:
                quantity_value = int(str(quantity_raw))
            except (TypeError, ValueError):
                errors.append(f"{row_prefix}：数量必须是整数")
                continue

            if quantity_value <= 0:
                errors.append(f"{row_prefix}：数量必须大于 0")
                continue

            partner_id = entry.get("partner_id")
            partner_obj = None
            if partner_id not in (None, ""):
                try:
                    partner_id = int(partner_id)
                except (TypeError, ValueError):
                    errors.append(f"{row_prefix}：合作方无效")
                    continue
                partner_obj = partner_lookup.get(partner_id)
                if not partner_obj:
                    errors.append(f"{row_prefix}：合作方不存在或已停用")
                    continue

            reference = (entry.get("reference") or "").strip()
            note = (entry.get("note") or "").strip()

            normalized_rows.append({
                "warehouse_id": warehouse_id,
                "warehouse_name": warehouse.name,
                "item_id": item_id,
                "item_name": item.name,
                "unit_name": item.unit.name if item.unit else "",
                "quantity": quantity_value,
                "reference": reference,
                "note": note,
                "partner_id": partner_obj.id if partner_obj else None,
            })

            if selected_action == MoveType.OUTBOUND:
                outbound_requirements[(warehouse_id, item_id)] += quantity_value

        if not normalized_rows and not errors:
            errors.append("请至少选择一条有效的操作记录")

        if normalized_rows and selected_action == MoveType.OUTBOUND:
            warehouse_ids = sorted({row["warehouse_id"] for row in normalized_rows})
            item_ids = sorted({row["item_id"] for row in normalized_rows})
            balances = {}
            if warehouse_ids and item_ids:
                balances = {
                    (bal.warehouse_id, bal.item_id): bal.on_hand
                    for bal in StockBalance.objects.filter(
                        warehouse_id__in=warehouse_ids,
                        item_id__in=item_ids,
                    )
                }
            for (warehouse_id, item_id), need in outbound_requirements.items():
                on_hand = balances.get((warehouse_id, item_id), 0)
                if on_hand < need:
                    warehouse_name = warehouse_lookup.get(warehouse_id).name
                    item_name = item_lookup.get(item_id).name
                    errors.append(
                        f"库存不足：{warehouse_name} - {item_name} 当前 {on_hand}，需 {need}"
                    )
                    normalized_rows = []
                    break

        if errors:
            for message_text in errors:
                messages.error(request, message_text)
        elif normalized_rows and selected_action in ACTION_TYPES:
            batch_reference = f"BATCH-{timezone.now().strftime('%Y%m%d%H%M%S')}-{request.user.id}"
            try:
                with transaction.atomic():
                    for row in normalized_rows:
                        qty_value = row["quantity"]
                        qty_value = qty_value if selected_action == MoveType.INBOUND else -qty_value
                        StockMove.objects.create(
                            move_type=selected_action,
                            warehouse_id=row["warehouse_id"],
                            item_id=row["item_id"],
                            quantity=qty_value,
                            reference=row["reference"] or batch_reference,
                            note=row["note"],
                            partner_id=row["partner_id"],
                        )
            except Exception:
                messages.error(request, "导入失败，请重试或联系管理员")
            else:
                messages.success(request, f"已成功导入 {len(normalized_rows)} 条记录")
                return redirect(reverse("products:inventory_dashboard"))

        initial_rows = _clean_initial_rows(payload)

    context = {
        "action_choices": ACTION_CHOICES,
        "warehouses": warehouses,
        "items_data": items_data,
        "partners": [{"id": partner.id, "name": partner.name} for partner in partners],
        "selected_action": selected_action,
        "initial_rows": initial_rows,
        "action_labels": ACTION_LABELS,
    }
    return render(request, "products/stock_import_upload.html", context)
