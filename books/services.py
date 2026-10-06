from dataclasses import dataclass

from django.db import transaction
from django.db.models import Sum

from books.access import clean_password, clean_text, clean_username, ensure_profile, require_owner, start_token
from books.errors import AppError
from books.models import Bill, BillLine, Customer, Item, LedgerEntry, Purchase, PurchaseLine, Shop, Stock, StockMovement, Vendor
from books.money import MAX_PAISE, check_paise, parse_date
from books.qr import generate_qr
from django.contrib.auth.models import User

METHODS = {"cash", "upi", "other"}
CATEGORIES = {
    "customer_receipt": "in",
    "vendor_payout": "out",
    "expense": "out",
    "opening": "in",
}


@dataclass
class ItemLine:
    item_id: int
    quantity: int
    unit_price_paise: int


@dataclass
class ServiceLine:
    description: str
    amount_paise: int


def clean_method(value: str | None) -> str:
    method = (value or "cash").strip().lower()
    if method not in METHODS:
        raise AppError("Choose cash, UPI, or other")
    return method


def _item(item_id: int) -> Item:
    item = Item.objects.filter(pk=item_id).first()
    if item is None:
        raise AppError("Item not found")
    return item


def stock_qty(shop_id: int, item_id: int) -> int:
    row = Stock.objects.filter(shop_id=shop_id, item_id=item_id).first()
    return row.quantity if row else 0


def stock_map(shop_id: int) -> dict[int, int]:
    return {row.item_id: row.quantity for row in Stock.objects.filter(shop_id=shop_id)}


def _change_stock(shop_id, item_id, delta, reason, ref_type, ref_id, note=""):
    row, _ = Stock.objects.get_or_create(shop_id=shop_id, item_id=item_id, defaults={"quantity": 0})
    new_qty = row.quantity + delta
    if new_qty < 0:
        name = Item.objects.filter(pk=item_id).values_list("name", flat=True).first() or "this item"
        raise AppError(f"Not enough stock for {name}")
    row.quantity = new_qty
    row.save(update_fields=["quantity"])
    StockMovement.objects.create(
        shop_id=shop_id,
        item_id=item_id,
        quantity_delta=delta,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
    )


def _line_total(qty: int, price: int, label: str = "Price") -> int:
    if qty <= 0:
        raise AppError("Quantity must be at least 1")
    check_paise(price, label)
    total = qty * price
    if total > MAX_PAISE:
        raise AppError("Amount is too large")
    return total


def _paid_bill(bill_id: int) -> int:
    return LedgerEntry.objects.filter(bill_id=bill_id, category="customer_receipt").aggregate(s=Sum("amount_paise"))["s"] or 0


def _paid_purchase(purchase_id: int) -> int:
    return LedgerEntry.objects.filter(purchase_id=purchase_id, category="vendor_payout").aggregate(s=Sum("amount_paise"))["s"] or 0


def _receipt(shop_id, bill, amount, method, day, note, customer_id):
    if amount <= 0:
        raise AppError("Enter a payment amount")
    if amount > bill.total_paise - _paid_bill(bill.id):
        raise AppError("Payment is more than the amount still due")
    return LedgerEntry.objects.create(
        shop_id=shop_id,
        date=day,
        direction="in",
        amount_paise=amount,
        category="customer_receipt",
        method=method,
        note=clean_text(note, "Note", required=False, limit=300),
        customer_id=customer_id or bill.customer_id,
        bill=bill,
    )


def _payout(shop_id, purchase, amount, method, day, note):
    if amount <= 0:
        raise AppError("Enter a payment amount")
    if purchase.shop_id != shop_id:
        raise AppError("Purchase not found for this shop")
    if amount > purchase.total_paise - _paid_purchase(purchase.id):
        raise AppError("Payment is more than the amount still owed to the vendor")
    return LedgerEntry.objects.create(
        shop_id=shop_id,
        date=day,
        direction="out",
        amount_paise=amount,
        category="vendor_payout",
        method=method,
        note=clean_text(note, "Note", required=False, limit=300),
        vendor_id=purchase.vendor_id,
        purchase=purchase,
    )


@transaction.atomic
def create_owner(name, username, password):
    from books.access import needs_setup

    if not needs_setup():
        raise AppError("Setup is already done", 409)
    username = clean_username(username)
    user = User.objects.create_user(username=username, password=clean_password(password))
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    ensure_profile(user, name=clean_text(name, "Name"), role="owner")
    return user, start_token(user)


@transaction.atomic
def login(username, password):
    username = clean_username(username)
    user = User.objects.filter(username=username).select_related("profile").first()
    if user is None or not user.check_password(password):
        raise AppError("Username or password is wrong", 401)
    return user, start_token(user)


@transaction.atomic
def create_shop(user, name, address, phone) -> Shop:
    require_owner(user)
    return Shop.objects.create(
        name=clean_text(name, "Shop name"),
        address=clean_text(address, "Address", required=False, limit=300),
        phone=clean_text(phone, "Phone", required=False, limit=40),
    )


@transaction.atomic
def create_staff(user, name, username, password, shop_ids: list[int]) -> User:
    require_owner(user)
    if not shop_ids:
        raise AppError("Assign at least one shop")
    username = clean_username(username)
    if User.objects.filter(username=username).exists():
        raise AppError("That username is already used")
    staff = User.objects.create_user(username=username, password=clean_password(password))
    profile = ensure_profile(staff, name=clean_text(name, "Name"), role="staff")
    seen = []
    for shop_id in shop_ids:
        if shop_id in seen:
            continue
        seen.append(shop_id)
        if not Shop.objects.filter(pk=shop_id).exists():
            raise AppError("Shop not found", 404)
    profile.shops.set(seen)
    return staff


@transaction.atomic
def create_item(name, unit, sale_price_paise, generate_code=False) -> Item:
    item = Item.objects.create(
        name=clean_text(name, "Item name"),
        unit=clean_text(unit or "pcs", "Unit", limit=20),
        sale_price_paise=check_paise(sale_price_paise, "Sale price"),
    )
    if generate_code:
        generate_qr(item)
    return item


@transaction.atomic
def update_item(item_id, name, unit, sale_price_paise, generate_code=False) -> Item:
    item = _item(item_id)
    item.name = clean_text(name, "Item name")
    item.unit = clean_text(unit or "pcs", "Unit", limit=20)
    item.sale_price_paise = check_paise(sale_price_paise, "Sale price")
    item.save()
    if generate_code:
        generate_qr(item)
    return item


def list_items(q=""):
    rows = Item.objects.all()
    if q.strip():
        rows = rows.filter(name__icontains=q.strip())
    return rows


@transaction.atomic
def adjust_stock(shop_id, item_id, quantity_delta, note) -> Stock:
    item = _item(item_id)
    if not isinstance(quantity_delta, int) or isinstance(quantity_delta, bool) or quantity_delta == 0:
        raise AppError("Enter a quantity change other than zero")
    _change_stock(shop_id, item.id, quantity_delta, "adjustment", "adjustment", None, clean_text(note, "Note", limit=300))
    return Stock.objects.get(shop_id=shop_id, item=item)


@transaction.atomic
def create_vendor(name, phone, note) -> Vendor:
    return Vendor.objects.create(
        name=clean_text(name, "Vendor name"),
        phone=clean_text(phone, "Phone", required=False, limit=40),
        note=clean_text(note, "Note", required=False, limit=300),
    )


def list_vendors(q=""):
    rows = Vendor.objects.all()
    if q.strip():
        rows = rows.filter(name__icontains=q.strip())
    return rows


@transaction.atomic
def create_customer(shop_id, name, phone, address) -> Customer:
    return Customer.objects.create(
        shop_id=shop_id,
        name=clean_text(name, "Customer name"),
        phone=clean_text(phone, "Phone", required=False, limit=40),
        address=clean_text(address, "Address", required=False, limit=300),
    )


def list_customers(shop_id, q=""):
    rows = Customer.objects.filter(shop_id=shop_id)
    if q.strip():
        rows = rows.filter(name__icontains=q.strip())
    return rows


@transaction.atomic
def create_purchase(shop_id, vendor_id, date, lines: list[ItemLine], note) -> Purchase:
    vendor = Vendor.objects.filter(pk=vendor_id).first()
    if vendor is None:
        raise AppError("Choose a vendor")
    if not lines:
        raise AppError("Add at least one item")
    purchase = Purchase.objects.create(
        shop_id=shop_id,
        vendor=vendor,
        date=parse_date(date) if isinstance(date, str) else date,
        total_paise=0,
        note=clean_text(note, "Note", required=False, limit=300),
    )
    total = 0
    for line in lines:
        item = _item(line.item_id)
        line_total = _line_total(line.quantity, line.unit_price_paise, "Cost")
        total += line_total
        PurchaseLine.objects.create(
            purchase=purchase,
            item=item,
            quantity=line.quantity,
            unit_cost_paise=line.unit_price_paise,
            line_total_paise=line_total,
        )
        item.last_cost_paise = line.unit_price_paise
        item.save(update_fields=["last_cost_paise"])
        _change_stock(shop_id, item.id, line.quantity, "purchase", "purchase", purchase.id)
    if total > MAX_PAISE:
        raise AppError("Amount is too large")
    purchase.total_paise = total
    purchase.save(update_fields=["total_paise"])
    return purchase


@transaction.atomic
def create_bill(shop_id, kind, customer_id, date, site_note, lines, services, paid_now, method, note=""):
    if kind not in ("counter", "job"):
        raise AppError("Unknown bill type")
    customer = None
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id, shop_id=shop_id).first()
        if customer is None:
            raise AppError("Customer not found for this shop")
    if kind == "job" and customer is None:
        raise AppError("Choose the customer for this job")
    if not lines and not services:
        raise AppError("Add at least one line")
    day = parse_date(date) if isinstance(date, str) else date
    needed: dict[int, int] = {}
    for line in lines:
        _item(line.item_id)
        if line.quantity <= 0:
            raise AppError("Quantity must be at least 1")
        needed[line.item_id] = needed.get(line.item_id, 0) + line.quantity
    for item_id, qty in needed.items():
        if stock_qty(shop_id, item_id) < qty:
            raise AppError(f"Not enough stock for {_item(item_id).name}")
    last = Bill.objects.filter(shop_id=shop_id).order_by("-number").values_list("number", flat=True).first()
    bill = Bill.objects.create(
        shop_id=shop_id,
        number=(last or 0) + 1,
        kind=kind,
        customer=customer,
        date=day,
        site_note=clean_text(site_note, "Site note", required=False, limit=300),
        total_paise=0,
    )
    total = 0
    reason = "sale" if kind == "counter" else "job"
    for line in lines:
        item = _item(line.item_id)
        line_total = _line_total(line.quantity, line.unit_price_paise, "Rate")
        total += line_total
        BillLine.objects.create(
            bill=bill,
            item=item,
            description=item.name,
            quantity=line.quantity,
            unit_price_paise=line.unit_price_paise,
            line_total_paise=line_total,
            is_service=False,
        )
        _change_stock(shop_id, item.id, -line.quantity, reason, "bill", bill.id)
    for service in services:
        amount = check_paise(service.amount_paise, "Service amount")
        if amount <= 0:
            raise AppError("Service amount must be more than zero")
        total += amount
        BillLine.objects.create(
            bill=bill,
            item=None,
            description=clean_text(service.description, "Service", limit=160),
            quantity=1,
            unit_price_paise=amount,
            line_total_paise=amount,
            is_service=True,
        )
    if total <= 0:
        raise AppError("Bill total must be more than zero")
    if total > MAX_PAISE:
        raise AppError("Amount is too large")
    bill.total_paise = total
    bill.save(update_fields=["total_paise"])
    if paid_now:
        _receipt(shop_id, bill, check_paise(paid_now, "Payment"), clean_method(method), day, note, customer.id if customer else None)
    return bill


def get_shop_bill(shop_id, bill_id) -> Bill:
    bill = Bill.objects.filter(pk=bill_id, shop_id=shop_id).first()
    if bill is None:
        raise AppError("Bill not found for this shop", 404)
    return bill


def get_shop_purchase(shop_id, purchase_id) -> Purchase:
    purchase = Purchase.objects.filter(pk=purchase_id, shop_id=shop_id).first()
    if purchase is None:
        raise AppError("Purchase not found for this shop", 404)
    return purchase


@transaction.atomic
def record_ledger(shop_id, category, amount_paise, method, date, note, bill_id=None, purchase_id=None, vendor_id=None):
    if category not in CATEGORIES:
        raise AppError("Unknown cash entry")
    day = parse_date(date) if isinstance(date, str) else date
    amount = check_paise(amount_paise, "Amount")
    if amount <= 0:
        raise AppError("Enter an amount")
    method = clean_method(method)
    note = clean_text(note or "", "Note", required=False, limit=300)
    if category == "customer_receipt":
        if not bill_id:
            raise AppError("Choose the bill this payment is for")
        bill = get_shop_bill(shop_id, bill_id)
        return _receipt(shop_id, bill, amount, method, day, note, bill.customer_id)
    if category == "vendor_payout":
        if purchase_id:
            purchase = get_shop_purchase(shop_id, purchase_id)
            return _payout(shop_id, purchase, amount, method, day, note)
        vendor = Vendor.objects.filter(pk=vendor_id).first() if vendor_id else None
        if vendor is None:
            raise AppError("Choose the vendor")
        return LedgerEntry.objects.create(
            shop_id=shop_id,
            date=day,
            direction="out",
            amount_paise=amount,
            category="vendor_payout",
            method=method,
            note=note,
            vendor=vendor,
        )
    if category == "expense" and not note:
        raise AppError("Add a note for this expense")
    return LedgerEntry.objects.create(
        shop_id=shop_id,
        date=day,
        direction=CATEGORIES[category],
        amount_paise=amount,
        category=category,
        method=method,
        note=note,
    )


def _sum(shop_id, direction, *, before=None, on=None) -> int:
    rows = LedgerEntry.objects.filter(shop_id=shop_id, direction=direction)
    if before is not None:
        rows = rows.filter(date__lt=before)
    if on is not None:
        rows = rows.filter(date=on)
    return rows.aggregate(s=Sum("amount_paise"))["s"] or 0


def wallet_totals(shop_id, day) -> dict:
    if isinstance(day, str):
        day = parse_date(day)
    opening = _sum(shop_id, "in", before=day) - _sum(shop_id, "out", before=day)
    today_in = _sum(shop_id, "in", on=day)
    today_out = _sum(shop_id, "out", on=day)
    return {
        "date": day,
        "opening_paise": opening,
        "in_paise": today_in,
        "out_paise": today_out,
        "closing_paise": opening + today_in - today_out,
    }


def has_opening(shop_id) -> bool:
    return LedgerEntry.objects.filter(shop_id=shop_id, category="opening").exists()


def ledger_on(shop_id, day):
    if isinstance(day, str):
        day = parse_date(day)
    return LedgerEntry.objects.filter(shop_id=shop_id, date=day)


def paid_map(model_field, category, ids):
    if not ids:
        return {}
    rows = (
        LedgerEntry.objects.filter(**{f"{model_field}__in": ids}, category=category)
        .values(model_field)
        .annotate(s=Sum("amount_paise"))
    )
    return {row[model_field]: row["s"] or 0 for row in rows}
