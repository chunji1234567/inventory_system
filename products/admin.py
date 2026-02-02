from django.contrib import admin
from .models import Warehouse, Item, StockMove, StockBalance, Unit, Partner


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "warehouse_type", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("warehouse_type", "is_active")
    ordering = ("name",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "category", "is_active", "created_at")
    search_fields = ("name", "barcode")
    list_filter = ("unit", "is_active", "category")
    ordering = ("name",)
    autocomplete_fields = ("unit",)


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("created_at", "move_type", "warehouse", "item", "partner", "quantity", "unit_cost", "reference")
    list_filter = ("move_type", "warehouse", "partner")
    search_fields = ("item__name", "reference", "note", "partner__name")
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
    search_fields = ("item__name",)
    ordering = ("warehouse__name", "item__name")

    # ✅ 禁止手动改余额（余额应由流水自动算出来）
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)
