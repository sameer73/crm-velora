from django import forms
from django.contrib import admin
from django.utils.html import format_html

from books.models import Bill, BillLine, Customer, Item, LedgerEntry, Profile, Purchase, PurchaseLine, Shop, Stock, Vendor
from books.money import parse_rupees
from books.qr import generate_qr


class ItemAdminForm(forms.ModelForm):
    sale_price = forms.CharField(label="Sale price (₹)", help_text="Example: 800 or 800.50")
    generate_code = forms.BooleanField(required=False, label="Generate QR code")

    class Meta:
        model = Item
        fields = ("name", "unit")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            rupees, frac = divmod(self.instance.sale_price_paise or 0, 100)
            self.fields["sale_price"].initial = f"{rupees}.{frac:02d}"

    def clean_sale_price(self):
        return parse_rupees(self.cleaned_data["sale_price"], "Sale price")

    def save(self, commit=True):
        item = super().save(commit=False)
        item.sale_price_paise = self.cleaned_data["sale_price"]
        if commit:
            item.save()
            if self.cleaned_data.get("generate_code"):
                generate_qr(item)
        return item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    form = ItemAdminForm
    list_display = ("name", "code", "unit", "price", "qr_thumb")
    search_fields = ("name", "code")
    readonly_fields = ("code", "qr_thumb", "last_cost_paise")
    actions = ("generate_codes",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get("generate_code"):
            generate_qr(obj)

    @admin.display(description="Sale price")
    def price(self, obj):
        rupees, frac = divmod(obj.sale_price_paise or 0, 100)
        return f"₹{rupees}.{frac:02d}"

    @admin.display(description="QR")
    def qr_thumb(self, obj):
        if not obj.qr_image:
            return "—"
        return format_html('<img src="{}" alt="{}" width="64" height="64">', obj.qr_image.url, obj.code)

    @admin.action(description="Generate QR code")
    def generate_codes(self, request, queryset):
        for item in queryset:
            generate_qr(item)


class ShopStaffInline(admin.TabularInline):
    model = Profile.shops.through
    extra = 0


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "address")
    search_fields = ("name",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "role")
    filter_horizontal = ("shops",)
    list_filter = ("role",)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "phone")
    search_fields = ("name",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "phone")
    list_filter = ("shop",)
    search_fields = ("name", "phone")


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("item", "shop", "quantity")
    list_filter = ("shop",)
    search_fields = ("item__name",)


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("vendor", "shop", "date", "total_paise")
    list_filter = ("shop",)
    inlines = [PurchaseLineInline]


class BillLineInline(admin.TabularInline):
    model = BillLine
    extra = 0


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("number", "kind", "shop", "customer", "date", "total_paise")
    list_filter = ("shop", "kind")
    inlines = [BillLineInline]


@admin.register(LedgerEntry)
class LedgerAdmin(admin.ModelAdmin):
    list_display = ("date", "shop", "direction", "category", "amount_paise", "method", "note")
    list_filter = ("shop", "category", "direction")
