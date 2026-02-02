import random
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from products.models import Item, Partner, StockBalance, StockMove, MoveType


class Command(BaseCommand):
    help = "Generate demo inbound/outbound stock move records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Total number of stock moves to create (half inbound, half outbound)",
        )

    def handle(self, *args, **options):
        total = max(2, options["count"])
        inbound_count = total // 2 + total % 2
        outbound_count = total // 2

        items = list(
            Item.objects.select_related("warehouse").filter(
                is_active=True,
                warehouse__isnull=False,
            )
        )
        if not items:
            raise CommandError("没有可用的物品（需要至少一个关联了仓库的启用物品）")

        partners = list(Partner.objects.filter(is_active=True))

        created = {"inbound": 0, "outbound": 0}

        self.stdout.write(self.style.NOTICE(f"开始创建 {inbound_count} 条入库 + {outbound_count} 条出库"))

        for _ in range(inbound_count):
            item = random.choice(items)
            qty = random.randint(5, 30)
            partner = random.choice(partners) if partners else None
            self._create_move(item=item, quantity=qty, move_type=MoveType.INBOUND, partner=partner)
            created["inbound"] += 1

        # Refresh balances so outbound uses up-to-date stock
        balances = list(StockBalance.objects.select_related("item", "warehouse").filter(on_hand__gt=0))

        for _ in range(outbound_count):
            if not balances:
                self.stdout.write(self.style.WARNING("库存不足，无法继续生成出库数据"))
                break
            balance = random.choice(balances)
            max_qty = int(balance.on_hand)
            if max_qty <= 0:
                balances.remove(balance)
                continue
            qty = random.randint(1, max_qty)
            partner = random.choice(partners) if partners else None
            self._create_move(
                item=balance.item,
                quantity=-qty,
                move_type=MoveType.OUTBOUND,
                partner=partner,
            )
            created["outbound"] += 1
            balance.on_hand -= Decimal(qty)
            if balance.on_hand <= 0:
                balances.remove(balance)

        self.stdout.write(self.style.SUCCESS(
            f"已完成：入库 {created['inbound']} 条，出库 {created['outbound']} 条"
        ))

    @transaction.atomic
    def _create_move(self, *, item, quantity, move_type, partner=None):
        ref_prefix = "IN" if move_type == MoveType.INBOUND else "OUT"
        StockMove.objects.create(
            move_type=move_type,
            warehouse=item.warehouse,
            item=item,
            quantity=quantity,
            reference=f"SEED-{ref_prefix}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}-{random.randint(1000, 9999)}",
            note="系统自动生成样例数据",
            partner=partner,
        )
