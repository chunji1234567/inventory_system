from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from products.models import Item, Unit


def item_list(request):
    items = Item.objects.order_by("sku")
    return render(
        request,
        "products/item_list.html",
        {
            "items": items,
            "units": Unit.choices,
        },
    )


def item_create(request):
    if request.method != "POST":
        return redirect(reverse("products:item_list"))

    sku = (request.POST.get("sku") or "").strip()
    name = (request.POST.get("name") or "").strip()
    unit = (request.POST.get("unit") or "").strip()

    if not sku or not name or not unit:
        messages.error(request, "新增失败：SKU / 名称 / 单位不能为空")
        return redirect(reverse("products:item_list"))

    if Item.objects.filter(sku=sku).exists():
        messages.error(request, f"新增失败：SKU 已存在（{sku}）")
        return redirect(reverse("products:item_list"))

    Item.objects.create(
        sku=sku,
        name=name,
        unit=unit,
        is_active=True,
    )
    messages.success(request, "物品已新增")
    return redirect(reverse("products:item_list"))


def item_update(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:item_list"))

    item = get_object_or_404(Item, pk=pk)

    name = (request.POST.get("name") or "").strip()
    unit = (request.POST.get("unit") or "").strip()
    is_active = request.POST.get("is_active") == "on"

    if not name or not unit:
        messages.error(request, "更新失败：名称 / 单位不能为空")
        return redirect(reverse("products:item_list"))

    item.name = name
    item.unit = unit
    item.is_active = is_active
    item.save(update_fields=["name", "unit", "is_active"])

    messages.success(request, "物品已更新")
    return redirect(reverse("products:item_list"))


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
