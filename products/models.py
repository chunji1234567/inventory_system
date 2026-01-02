from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError


class Unit(models.TextChoices):
    PCS = "PCS", "件"
    BOX = "BOX", "箱"
    GE = "GE", "个"
    ZHI = "ZHI", "只"
    OTHER = "OTHER", "其他"


class MoveType(models.TextChoices):
    INBOUND = "INBOUND", "入库"
    OUTBOUND = "OUTBOUND", "出库"
    ADJUST = "ADJUST", "调整"


class Warehouse(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="仓库名称")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "仓库"
        verbose_name_plural = "仓库"

    def __str__(self):
        return self.name


class Item(models.Model):
    """物品主档（SKU 字段已移除，仅保留名称）。"""
    name = models.CharField(max_length=100, unique=True, verbose_name="名称")
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.PCS, verbose_name="单位")
    category = models.CharField(max_length=50, blank=True, verbose_name="分类（可选）")
    barcode = models.CharField(max_length=80, blank=True, verbose_name="条码（可选）")
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="items",
        null=True,
        verbose_name="所属仓库",
    )

    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "物品"
        verbose_name_plural = "物品"

    def __str__(self):
        if self.warehouse_id:
            return f"{self.name} @ {self.warehouse.name}"
        return self.name


class StockMove(models.Model):
    """
    库存流水（权威来源）
    约定：
    - 入库：quantity > 0
    - 出库：quantity < 0
    - 调整：正负皆可
    """
    move_type = models.CharField(max_length=20, choices=MoveType.choices, verbose_name="类型")

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="moves")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="moves")

    quantity = models.IntegerField(verbose_name="变动数量")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="单位成本(可选)")

    reference = models.CharField(max_length=100, blank=True, verbose_name="关联单号/来源(可选)")
    note = models.TextField(blank=True, verbose_name="备注(可选)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["item", "warehouse"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at", "-id"]
        verbose_name = "库存流水"
        verbose_name_plural = "库存流水"

    def clean(self):
        super().clean()

        if self.quantity is None:
            return

        # 统一规则：入库永远为正、出库永远为负、调整随意
        if self.move_type == "INBOUND" and self.quantity < 0:
            self.quantity = abs(self.quantity)

        if self.move_type == "OUTBOUND" and self.quantity > 0:
            self.quantity = -abs(self.quantity)

        # 可选：禁止 0
        if self.quantity == 0:
            raise ValidationError({"quantity": "数量不能为 0"})

    def __str__(self):
        return f"{self.move_type} {self.item.name} {self.quantity}"
    


class StockBalance(models.Model):
    """
    当前库存余额（缓存表）
    """
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="balances")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")

    on_hand = models.IntegerField(default=0, verbose_name="当前库存")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "warehouse"], name="uniq_balance_item_warehouse")
        ]
        indexes = [
            models.Index(fields=["item", "warehouse"]),
        ]
        verbose_name = "库存余额"
        verbose_name_plural = "库存余额"

    def __str__(self):
        return f"{self.item.name} @ {self.warehouse.name}: {self.on_hand}"
