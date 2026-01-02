from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from products.forms import WarehouseForm
from products.models import Warehouse


@login_required
def warehouse_list(request):
    warehouses = Warehouse.objects.order_by("name")
    return render(request, "products/warehouse_list.html", {"warehouses": warehouses})


@login_required
def warehouse_create(request):
    if request.method != "POST":
        return redirect(reverse("products:warehouse_list"))

    form = WarehouseForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "仓库已新增")
    else:
        messages.error(request, f"新增失败：{form.errors.as_text()}")
    return redirect(reverse("products:warehouse_list"))


@login_required
def warehouse_edit(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:warehouse_list"))

    obj = get_object_or_404(Warehouse, pk=pk)
    form = WarehouseForm(request.POST, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, "仓库已更新")
    else:
        messages.error(request, f"更新失败：{form.errors.as_text()}")
    return redirect(reverse("products:warehouse_list"))


@login_required
def warehouse_toggle_active(request, pk: int):
    if request.method != "POST":
        return redirect(reverse("products:warehouse_list"))

    obj = get_object_or_404(Warehouse, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])

    messages.success(
        request,
        f"仓库已{'启用' if obj.is_active else '停用'}"
    )
    return redirect(reverse("products:warehouse_list"))
