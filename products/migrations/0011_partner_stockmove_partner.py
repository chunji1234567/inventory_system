from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_remove_item_barcode_item_warehouse"),
    ]

    operations = [
        migrations.CreateModel(
            name="Partner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="名称")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name"],
                "verbose_name": "合作方",
                "verbose_name_plural": "合作方",
            },
        ),
        migrations.AddField(
            model_name="stockmove",
            name="partner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="stock_moves",
                to="products.partner",
                verbose_name="合作方",
            ),
        ),
        migrations.AddIndex(
            model_name="stockmove",
            index=models.Index(fields=["partner"], name="products_s_partner_5ba4fa_idx"),
        ),
    ]
