from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from products.models import Item, Unit, Warehouse


@login_required
def item_list(request):
    items = Item.objects.select_related("warehouse").order_by("name")
    warehouses = Warehouse.objects.order_by("name")
    return render(
        request,
        "products/item_list.html",
        {
            "items": items,
            "units": Unit.choices,
            "warehouses": warehouses,
        },
    )


@login_required
def item_create(request):
    if request.method != "POST":
        return redirect(reverse("products:item_list"))

    name = (request.POST.get("name") or "").strip()
    unit = (request.POST.get("unit") or "").strip()
    warehouse_id = (request.POST.get("warehouse_id") or "").strip()
    is_finished_good = request.POST.get("is_finished_good") == "on"

    if not name or not unit or not warehouse_id:
        messages.error(request, "新增失败：名称 / 单位 / 仓库不能为空")
        return redirect(reverse("products:item_list"))

    warehouse = Warehouse.objects.filter(id=warehouse_id).first()
    if warehouse is None:
        messages.error(request, "新增失败：请选择有效仓库")
        return redirect(reverse("products:item_list"))

    if Item.objects.filter(name=name).exists():
        messages.error(request, f"新增失败：物品名称已存在（{name}）")
        return redirect(reverse("products:item_list"))

    Item.objects.create(
        name=name,
        unit=unit,
        warehouse=warehouse,
        is_active=True,
        is_finished_good=is_finished_good,
    )
    messages.success(request, "物品已新增")
    return redirect(reverse("products:item_list"))


@login_required
def item_update(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:item_list"))

    item = get_object_or_404(Item, pk=pk)

    name = (request.POST.get("name") or "").strip()
    unit = (request.POST.get("unit") or "").strip()
    warehouse_id = (request.POST.get("warehouse_id") or "").strip()
    is_active = request.POST.get("is_active") == "on"
    is_finished_good = request.POST.get("is_finished_good") == "on"

    if not name or not unit or not warehouse_id:
        messages.error(request, "更新失败：名称 / 单位 / 仓库不能为空")
        return redirect(reverse("products:item_list"))

    warehouse = Warehouse.objects.filter(id=warehouse_id).first()
    if warehouse is None:
        messages.error(request, "更新失败：请选择有效仓库")
        return redirect(reverse("products:item_list"))

    if Item.objects.exclude(pk=item.pk).filter(name=name).exists():
        messages.error(request, f"更新失败：物品名称已存在（{name}）")
        return redirect(reverse("products:item_list"))

    item.name = name
    item.unit = unit
    item.warehouse = warehouse
    item.is_active = is_active
    item.is_finished_good = is_finished_good
    item.save(update_fields=["name", "unit", "warehouse", "is_active", "is_finished_good"])

    messages.success(request, "物品已更新")
    return redirect(reverse("products:item_list"))


@login_required
def item_toggle_active(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:item_list"))

    item = get_object_or_404(Item, pk=pk)
    item.is_active = not item.is_active
    item.save(update_fields=["is_active"])

    messages.success(
        request,
        f"物品已{'启用' if item.is_active else '停用'}"
    )
    return redirect(reverse("products:item_list"))
