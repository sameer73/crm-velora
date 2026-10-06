from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=20, default="staff")
    shops = models.ManyToManyField("Shop", blank=True, related_name="staff")

    def __str__(self):
        return self.name or self.user.username

    @property
    def is_owner(self):
        return self.role == "owner"


class Shop(models.Model):
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class ApiToken(models.Model):
    key = models.CharField(max_length=80, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    expires_at = models.DateTimeField()


class Item(models.Model):
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=20, default="pcs")
    sale_price_paise = models.IntegerField(default=0)
    last_cost_paise = models.IntegerField(null=True, blank=True)
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    qr_image = models.ImageField(upload_to="qr/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Vendor(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Stock(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="stock_rows")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_rows")
    quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = [("shop", "item")]

    def __str__(self):
        return f"{self.item} @ {self.shop}: {self.quantity}"


class StockMovement(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity_delta = models.IntegerField()
    reason = models.CharField(max_length=20)
    ref_type = models.CharField(max_length=20, blank=True)
    ref_id = models.IntegerField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Customer(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Purchase(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="purchases")
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    date = models.DateField()
    total_paise = models.IntegerField(default=0)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.vendor} · {self.date}"


class PurchaseLine(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_cost_paise = models.IntegerField()
    line_total_paise = models.IntegerField()


class Bill(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="bills")
    number = models.IntegerField()
    kind = models.CharField(max_length=20)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT)
    date = models.DateField()
    site_note = models.CharField(max_length=300, blank=True)
    total_paise = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        unique_together = [("shop", "number")]

    def __str__(self):
        return f"#{self.number:04d}"


class BillLine(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT)
    description = models.CharField(max_length=160)
    quantity = models.IntegerField()
    unit_price_paise = models.IntegerField()
    line_total_paise = models.IntegerField()
    is_service = models.BooleanField(default=False)


class LedgerEntry(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="ledger")
    date = models.DateField()
    direction = models.CharField(max_length=3)
    amount_paise = models.IntegerField()
    category = models.CharField(max_length=30)
    method = models.CharField(max_length=10, default="cash")
    note = models.CharField(max_length=300, blank=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL)
    bill = models.ForeignKey(Bill, null=True, blank=True, on_delete=models.CASCADE, related_name="payments")
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.CASCADE, related_name="payouts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Ledger entry"
        verbose_name_plural = "Ledger entries"
