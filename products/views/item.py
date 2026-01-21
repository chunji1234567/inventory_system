from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from products.models import Item, Unit, Warehouse
from products.views.inventory import _role_filter_kwargs


@login_required
def item_create(request):
    if request.method != "POST":
        return redirect(reverse("products:inventory_dashboard"))

    name = (request.POST.get("name") or "").strip()
    unit_id = (request.POST.get("unit") or "").strip()
    warehouse_id = (request.POST.get("warehouse_id") or "").strip()
    is_active = request.POST.get("is_active") == "on"

    if not name or not unit_id or not warehouse_id:
        messages.error(request, "新增失败：名称 / 单位 / 品类不能为空")
        return redirect(reverse("products:inventory_dashboard"))

    unit = Unit.objects.filter(pk=unit_id, is_active=True).first()
    if unit is None:
        messages.error(request, "新增失败：请选择有效单位")
        return redirect(reverse("products:inventory_dashboard"))

    role_context = _role_filter_kwargs(request.user)
    warehouse = Warehouse.objects.filter(id=warehouse_id)
    if role_context["warehouse_filter"]:
        warehouse = warehouse.filter(**role_context["warehouse_filter"])
    warehouse = warehouse.first()
    if warehouse is None:
        messages.error(request, "新增失败：请选择有效品类")
        return redirect(reverse("products:inventory_dashboard"))

    if Item.objects.filter(name=name).exists():
        messages.error(request, f"新增失败：物品名称已存在（{name}）")
        return redirect(reverse("products:inventory_dashboard"))

    Item.objects.create(
        name=name,
        unit=unit,
        warehouse=warehouse,
        is_active=is_active,
    )
    messages.success(request, "物品已新增")
    return redirect(reverse("products:inventory_dashboard"))


@login_required
def item_update(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:inventory_dashboard"))

    item = get_object_or_404(Item, pk=pk)

    name = (request.POST.get("name") or "").strip()
    unit_id = (request.POST.get("unit") or "").strip()
    warehouse_id = (request.POST.get("warehouse_id") or "").strip()
    is_active = request.POST.get("is_active") == "on"

    if not name or not unit_id or not warehouse_id:
        messages.error(request, "更新失败：名称 / 单位 / 品类不能为空")
        return redirect(reverse("products:inventory_dashboard"))

    unit = Unit.objects.filter(pk=unit_id, is_active=True).first()
    if unit is None:
        messages.error(request, "更新失败：请选择有效单位")
        return redirect(reverse("products:inventory_dashboard"))

    role_context = _role_filter_kwargs(request.user)
    warehouse = Warehouse.objects.filter(id=warehouse_id)
    if role_context["warehouse_filter"]:
        warehouse = warehouse.filter(**role_context["warehouse_filter"])
    warehouse = warehouse.first()
    if warehouse is None:
        messages.error(request, "更新失败：请选择有效品类")
        return redirect(reverse("products:inventory_dashboard"))

    if Item.objects.exclude(pk=item.pk).filter(name=name).exists():
        messages.error(request, f"更新失败：物品名称已存在（{name}）")
        return redirect(reverse("products:inventory_dashboard"))

    item.name = name
    item.unit = unit
    item.warehouse = warehouse
    item.is_active = is_active
    item.save(update_fields=["name", "unit", "warehouse", "is_active"])

    messages.success(request, "物品已更新")
    return redirect(reverse("products:inventory_dashboard"))


@login_required
def item_toggle_active(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:inventory_dashboard"))

    item = get_object_or_404(Item, pk=pk)
    item.is_active = not item.is_active
    item.save(update_fields=["is_active"])

    messages.success(
        request,
        f"物品已{'启用' if item.is_active else '停用'}"
    )
    return redirect(reverse("products:inventory_dashboard"))
