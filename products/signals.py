from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import StockMove, StockBalance


def recalc_balance(item_id: int, warehouse_id: int) -> None:
    total = (
        StockMove.objects
        .filter(item_id=item_id, warehouse_id=warehouse_id)
        .aggregate(s=Sum("quantity"))
        .get("s")
    ) or Decimal("0")

    with transaction.atomic():
        balance, _ = StockBalance.objects.select_for_update().get_or_create(
            item_id=item_id,
            warehouse_id=warehouse_id,
            defaults={"on_hand": Decimal("0")},
        )
        balance.on_hand = total
        balance.save(update_fields=["on_hand"])


@receiver(post_save, sender=StockMove)
def stockmove_saved(sender, instance: StockMove, **kwargs):
    recalc_balance(instance.item_id, instance.warehouse_id)


@receiver(post_delete, sender=StockMove)
def stockmove_deleted(sender, instance: StockMove, **kwargs):
    recalc_balance(instance.item_id, instance.warehouse_id)
