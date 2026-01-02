from django.contrib import admin
from .models import Warehouse, Item, StockMove, StockBalance


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)
    ordering = ("code",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "unit", "category", "is_active", "created_at")
    search_fields = ("sku", "name", "barcode")
    list_filter = ("unit", "is_active", "category")
    ordering = ("sku",)


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("created_at", "move_type", "warehouse", "item", "quantity", "unit_cost", "reference")
    list_filter = ("move_type", "warehouse")
    search_fields = ("item__sku", "item__name", "reference", "note")
    ordering = ("-created_at", "-id")

    # ✅ 禁止修改已有流水（只能新增）
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    # ✅ 可选：也禁止批量编辑（actions）
    actions = None


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "item", "on_hand", "updated_at")
    list_filter = ("warehouse",)
    search_fields = ("item__sku", "item__name")
    ordering = ("warehouse__code", "item__sku")

    # ✅ 禁止手动改余额（余额应由流水自动算出来）
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
