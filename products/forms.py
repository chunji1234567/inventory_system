from django import forms
from .models import Warehouse, Unit, Partner

class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["name", "is_active"]


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["name", "is_active"]


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ["name", "is_active"]
