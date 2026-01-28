from collections import OrderedDict
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.core.paginator import Paginator

from products.models import Warehouse, StockBalance, Item, WarehouseType, Unit


def _issue_form_token(request, key: str) -> str:
    token = uuid.uuid4().hex
    request.session[f"form_token_{key}"] = token
    return token


def _role_filter_kwargs(user):
    def in_group(names):
        return user.groups.filter(name__in=names).exists()

    if user.is_superuser or in_group({"admin", "ADMIN"}):
        return {
            "warehouse": Warehouse.objects.filter(is_active=True),
            "warehouse_filter": {},
        }

    if in_group({"finished", "FINISHED"}):
        return {
            "warehouse": Warehouse.objects.filter(
                is_active=True,
                warehouse_type__in=[WarehouseType.FINISHED, WarehouseType.BOTH],
            ),
            "warehouse_filter": {
                "warehouse__warehouse_type__in": [WarehouseType.FINISHED, WarehouseType.BOTH],
            },
        }

    if in_group({"raw", "RAW"}):
        return {
            "warehouse": Warehouse.objects.filter(
                is_active=True,
                warehouse_type__in=[WarehouseType.RAW, WarehouseType.BOTH],
            ),
            "warehouse_filter": {
                "warehouse__warehouse_type__in": [WarehouseType.RAW, WarehouseType.BOTH],
            },
        }

    return {
        "warehouse": Warehouse.objects.filter(is_active=True),
        "warehouse_filter": {},
    }


@login_required
def inventory_dashboard(request):
    warehouse_id = (request.GET.get("warehouse_id") or "").strip()
    q = request.GET.get("q", "").strip()
    show_inactive = request.GET.get("show_inactive") == "1"

    role_context = _role_filter_kwargs(request.user)

    inventory_items = Item.objects.select_related("warehouse").order_by("-created_at")
    if role_context["warehouse_filter"]:
        inventory_items = inventory_items.filter(**role_context["warehouse_filter"])

    if warehouse_id:
        inventory_items = inventory_items.filter(warehouse_id=warehouse_id)

    if q:
        inventory_items = inventory_items.filter(
            Q(name__icontains=q) |
            Q(warehouse__name__icontains=q)
        )

    if not show_inactive:
        inventory_items = inventory_items.filter(is_active=True)

    warehouses = role_context["warehouse"].order_by("name")
    allowed_warehouse_ids = list(warehouses.values_list("id", flat=True))
    form_items = (
        Item.objects
        .filter(is_active=True, warehouse_id__in=allowed_warehouse_ids)
        .order_by("name")
    )
    management_items = (
        Item.objects
        .select_related("warehouse")
        .filter(warehouse_id__in=allowed_warehouse_ids)
        .order_by("name")
    )
    if role_context["warehouse_filter"]:
        management_items = management_items.filter(**role_context["warehouse_filter"])

    unit_choices = [(unit.pk, unit.name) for unit in Unit.objects.filter(is_active=True).order_by("name")]

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

    flat_rows = []
    for group in grouped.values():
        for row in group["rows"]:
            flat_rows.append({
                "warehouse": group["warehouse"],
                "row": row,
            })

    paginator = Paginator(flat_rows, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    page_grouped = OrderedDict()
    for entry in page_obj.object_list:
        warehouse = entry["warehouse"]
        row = entry["row"]
        key = warehouse.id if warehouse else None
        if key not in page_grouped:
            page_grouped[key] = {
                "warehouse": warehouse,
                "rows": [],
            }
        page_grouped[key]["rows"].append(row)

    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")
    query_string = query_params.urlencode()

    form_tokens = {
        "inbound": _issue_form_token(request, "inbound"),
        "outbound": _issue_form_token(request, "outbound"),
        "adjust": _issue_form_token(request, "adjust"),
    }

    return render(request, "products/inventory_dashboard.html", {
        "page_obj": page_obj,
        "grouped_rows": page_grouped.values(),
        "warehouses": warehouses,
        "form_items": form_items,
        "selected_warehouse_id": warehouse_id,
        "q": q,
        "show_inactive": show_inactive,
        "balance_data": balance_data,
        "low_stock_threshold": threshold,
        "low_stock_rows": low_stock_rows,
        "form_tokens": form_tokens,
        "items": management_items,
        "units": unit_choices,
        "query_string": query_string,
    })
