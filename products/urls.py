from django.urls import path
from products.views.inventory import inventory_dashboard
from products.views.warehouse import (
    warehouse_list,
    warehouse_create,
    warehouse_edit,
    warehouse_toggle_active,
    unit_create,
    partner_create,
)
from products.views.stockmove import inbound_create, outbound_create, adjust_create
from products.views.stockmove_list import stockmove_list, stockmove_export
from products.views.item import item_create, item_update, item_toggle_active


app_name = "products"

urlpatterns = [
    path("inventory/", inventory_dashboard, name="inventory_dashboard"),

    path("warehouses/", warehouse_list, name="warehouse_list"),
    path("warehouses/new/", warehouse_create, name="warehouse_create"),
    path("warehouses/<int:pk>/edit/", warehouse_edit, name="warehouse_edit"),
    path("warehouses/<int:pk>/toggle/", warehouse_toggle_active, name="warehouse_toggle_active"),
    path("units/new/", unit_create, name="unit_create"),
    path("partners/new/", partner_create, name="partner_create"),
    path("inventory/inbound/", inbound_create, name="inventory_inbound"),
    path("inventory/outbound/", outbound_create, name="inventory_outbound"),
    path("inventory/adjust/", adjust_create, name="inventory_adjust"),
    path("moves/", stockmove_list, name="stockmove_list"),
    path("moves/export/", stockmove_export, name="stockmove_export"),
    path("items/new/", item_create, name="item_create"),
    path("items/<int:pk>/edit/", item_update, name="item_update"),
    path("items/<int:pk>/toggle/", item_toggle_active, name="item_toggle_active"),
]
