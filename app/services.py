from dataclasses import dataclass
from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    check_password,
    clean_password,
    clean_text,
    clean_username,
    hash_password,
    needs_setup,
    require_owner,
    start_session,
    user_by_username,
)
from app.errors import AppError
from app.models import (
    Bill,
    BillLine,
    Customer,
    Item,
    LedgerEntry,
    Purchase,
    PurchaseLine,
    Shop,
    Stock,
    StockMovement,
    User,
    UserShop,
    Vendor,
)
from app.money import MAX_PAISE, check_paise, parse_date

METHODS = {"cash", "upi", "other"}
CATEGORIES = {
    "customer_receipt": "in",
    "vendor_payout": "out",
    "expense": "out",
    "opening": "in",
}


def transactional(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        db: Session = args[0]
        try:
            result = fn(*args, **kwargs)
            db.commit()
            return result
        except IntegrityError:
            db.rollback()
            raise AppError("That record already exists") from None
        except Exception:
            db.rollback()
            raise

    return wrapper


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


def _item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise AppError("Item not found")
    return item


def _customer(db: Session, shop_id: int, customer_id: int | None) -> Customer | None:
    if customer_id is None:
        return None
    customer = db.get(Customer, customer_id)
    if customer is None or customer.shop_id != shop_id:
        raise AppError("Customer not found for this shop")
    return customer


def stock_qty(db: Session, shop_id: int, item_id: int) -> int:
    row = db.get(Stock, (shop_id, item_id))
    return row.quantity if row else 0


def stock_map(db: Session, shop_id: int) -> dict[int, int]:
    rows = db.scalars(select(Stock).where(Stock.shop_id == shop_id)).all()
    return {row.item_id: row.quantity for row in rows}


def _change_stock(
    db: Session,
    shop_id: int,
    item_id: int,
    delta: int,
    reason: str,
    ref_type: str,
    ref_id: int | None,
    note: str = "",
) -> None:
    row = db.get(Stock, (shop_id, item_id))
    if row is None:
        row = Stock(shop_id=shop_id, item_id=item_id, quantity=0)
        db.add(row)
        db.flush()
    new_qty = row.quantity + delta
    if new_qty < 0:
        item = db.get(Item, item_id)
        name = item.name if item else "this item"
        raise AppError(f"Not enough stock for {name}")
    row.quantity = new_qty
    db.add(
        StockMovement(
            shop_id=shop_id,
            item_id=item_id,
            quantity_delta=delta,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
        )
    )


def _line_total(qty: int, price: int, label: str = "Price") -> int:
    if qty <= 0:
        raise AppError("Quantity must be at least 1")
    check_paise(price, label)
    total = qty * price
    if total > MAX_PAISE:
        raise AppError("Amount is too large")
    return total


def _paid_bill(db: Session, bill_id: int) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).where(
            LedgerEntry.bill_id == bill_id,
            LedgerEntry.category == "customer_receipt",
        )
    )
    return int(value or 0)


def _paid_purchase(db: Session, purchase_id: int) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).where(
            LedgerEntry.purchase_id == purchase_id,
            LedgerEntry.category == "vendor_payout",
        )
    )
    return int(value or 0)


def _receipt(
    db: Session,
    shop_id: int,
    bill: Bill,
    amount: int,
    method: str,
    date: str,
    note: str,
    customer_id: int | None,
) -> LedgerEntry:
    if amount <= 0:
        raise AppError("Enter a payment amount")
    balance = bill.total_paise - _paid_bill(db, bill.id)
    if amount > balance:
        raise AppError("Payment is more than the amount still due")
    entry = LedgerEntry(
        shop_id=shop_id,
        date=date,
        direction="in",
        amount_paise=amount,
        category="customer_receipt",
        method=method,
        note=clean_text(note, "Note", required=False, limit=300),
        customer_id=customer_id or bill.customer_id,
        bill_id=bill.id,
    )
    db.add(entry)
    db.flush()
    return entry


def _payout(
    db: Session,
    shop_id: int,
    purchase: Purchase,
    amount: int,
    method: str,
    date: str,
    note: str,
) -> LedgerEntry:
    if amount <= 0:
        raise AppError("Enter a payment amount")
    if purchase.shop_id != shop_id:
        raise AppError("Purchase not found for this shop")
    balance = purchase.total_paise - _paid_purchase(db, purchase.id)
    if amount > balance:
        raise AppError("Payment is more than the amount still owed to the vendor")
    entry = LedgerEntry(
        shop_id=shop_id,
        date=date,
        direction="out",
        amount_paise=amount,
        category="vendor_payout",
        method=method,
        note=clean_text(note, "Note", required=False, limit=300),
        vendor_id=purchase.vendor_id,
        purchase_id=purchase.id,
    )
    db.add(entry)
    db.flush()
    return entry


@transactional
def create_owner(db: Session, name: str, username: str, password: str) -> tuple[User, str]:
    if not needs_setup(db):
        raise AppError("Setup is already done", 409)
    user = User(
        name=clean_text(name, "Name"),
        username=clean_username(username),
        password_hash=hash_password(clean_password(password)),
        role="owner",
    )
    db.add(user)
    db.flush()
    return user, start_session(db, user)


@transactional
def login(db: Session, username: str, password: str) -> tuple[User, str]:
    user = user_by_username(db, clean_username(username))
    if user is None or not check_password(password, user.password_hash):
        raise AppError("Username or password is wrong", 401)
    return user, start_session(db, user)


@transactional
def create_shop(db: Session, user: User, name: str, address: str, phone: str) -> Shop:
    require_owner(user)
    shop = Shop(
        name=clean_text(name, "Shop name"),
        address=clean_text(address, "Address", required=False, limit=300),
        phone=clean_text(phone, "Phone", required=False, limit=40),
    )
    db.add(shop)
    db.flush()
    return shop


@transactional
def create_staff(
    db: Session,
    user: User,
    name: str,
    username: str,
    password: str,
    shop_ids: list[int],
) -> User:
    require_owner(user)
    if not shop_ids:
        raise AppError("Assign at least one shop")
    username = clean_username(username)
    if user_by_username(db, username):
        raise AppError("That username is already used")
    staff = User(
        name=clean_text(name, "Name"),
        username=username,
        password_hash=hash_password(clean_password(password)),
        role="staff",
    )
    db.add(staff)
    db.flush()
    seen: set[int] = set()
    for shop_id in shop_ids:
        if shop_id in seen:
            continue
        seen.add(shop_id)
        if db.get(Shop, shop_id) is None:
            raise AppError("Shop not found", 404)
        db.add(UserShop(user_id=staff.id, shop_id=shop_id))
    return staff


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name, User.id)))


@transactional
def create_item(db: Session, name: str, unit: str, sale_price_paise: int) -> Item:
    item = Item(
        name=clean_text(name, "Item name"),
        unit=clean_text(unit or "pcs", "Unit", limit=20),
        sale_price_paise=check_paise(sale_price_paise, "Sale price"),
    )
    db.add(item)
    db.flush()
    return item


@transactional
def update_item(db: Session, item_id: int, name: str, unit: str, sale_price_paise: int) -> Item:
    item = _item(db, item_id)
    item.name = clean_text(name, "Item name")
    item.unit = clean_text(unit or "pcs", "Unit", limit=20)
    item.sale_price_paise = check_paise(sale_price_paise, "Sale price")
    return item


def list_items(db: Session, q: str = "") -> list[Item]:
    stmt = select(Item).order_by(Item.name, Item.id)
    query = q.strip()
    if query:
        stmt = stmt.where(Item.name.ilike(f"%{query}%"))
    return list(db.scalars(stmt))


@transactional
def adjust_stock(db: Session, shop_id: int, item_id: int, quantity_delta: int, note: str) -> Stock:
    item = _item(db, item_id)
    if not isinstance(quantity_delta, int) or isinstance(quantity_delta, bool):
        raise AppError("Quantity must be a whole number")
    if quantity_delta == 0:
        raise AppError("Enter a quantity change other than zero")
    _change_stock(
        db,
        shop_id,
        item.id,
        quantity_delta,
        "adjustment",
        "adjustment",
        None,
        clean_text(note, "Note", limit=300),
    )
    stock = db.get(Stock, (shop_id, item.id))
    assert stock is not None
    return stock


@transactional
def create_vendor(db: Session, name: str, phone: str, note: str) -> Vendor:
    vendor = Vendor(
        name=clean_text(name, "Vendor name"),
        phone=clean_text(phone, "Phone", required=False, limit=40),
        note=clean_text(note, "Note", required=False, limit=300),
    )
    db.add(vendor)
    db.flush()
    return vendor


def list_vendors(db: Session, q: str = "") -> list[Vendor]:
    stmt = select(Vendor).order_by(Vendor.name, Vendor.id)
    query = q.strip()
    if query:
        stmt = stmt.where(Vendor.name.ilike(f"%{query}%"))
    return list(db.scalars(stmt))


@transactional
def create_customer(db: Session, shop_id: int, name: str, phone: str, address: str) -> Customer:
    customer = Customer(
        shop_id=shop_id,
        name=clean_text(name, "Customer name"),
        phone=clean_text(phone, "Phone", required=False, limit=40),
        address=clean_text(address, "Address", required=False, limit=300),
    )
    db.add(customer)
    db.flush()
    return customer


def list_customers(db: Session, shop_id: int, q: str = "") -> list[Customer]:
    stmt = select(Customer).where(Customer.shop_id == shop_id).order_by(Customer.name, Customer.id)
    query = q.strip()
    if query:
        stmt = stmt.where(Customer.name.ilike(f"%{query}%"))
    return list(db.scalars(stmt))


@transactional
def create_purchase(
    db: Session,
    shop_id: int,
    vendor_id: int,
    date: str,
    lines: list[ItemLine],
    note: str,
) -> Purchase:
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise AppError("Choose a vendor")
    if not lines:
        raise AppError("Add at least one item")
    purchase = Purchase(
        shop_id=shop_id,
        vendor_id=vendor.id,
        date=parse_date(date),
        total_paise=0,
        note=clean_text(note, "Note", required=False, limit=300),
    )
    db.add(purchase)
    db.flush()
    total = 0
    for line in lines:
        item = _item(db, line.item_id)
        line_total = _line_total(line.quantity, line.unit_price_paise, "Cost")
        total += line_total
        db.add(
            PurchaseLine(
                purchase_id=purchase.id,
                item_id=item.id,
                quantity=line.quantity,
                unit_cost_paise=line.unit_price_paise,
                line_total_paise=line_total,
            )
        )
        item.last_cost_paise = line.unit_price_paise
        _change_stock(db, shop_id, item.id, line.quantity, "purchase", "purchase", purchase.id)
    if total > MAX_PAISE:
        raise AppError("Amount is too large")
    purchase.total_paise = total
    return purchase


def list_purchases(db: Session, shop_id: int) -> list[Purchase]:
    return list(
        db.scalars(
            select(Purchase).where(Purchase.shop_id == shop_id).order_by(Purchase.date.desc(), Purchase.id.desc())
        )
    )


@transactional
def create_bill(
    db: Session,
    shop_id: int,
    kind: str,
    customer_id: int | None,
    date: str,
    site_note: str,
    lines: list[ItemLine],
    services: list[ServiceLine],
    paid_now: int,
    method: str,
    note: str = "",
) -> Bill:
    if kind not in ("counter", "job"):
        raise AppError("Unknown bill type")
    customer = _customer(db, shop_id, customer_id)
    if kind == "job" and customer is None:
        raise AppError("Choose the customer for this job")
    if not lines and not services:
        raise AppError("Add at least one line")
    date = parse_date(date)
    needed: dict[int, int] = {}
    for line in lines:
        _item(db, line.item_id)
        if line.quantity <= 0:
            raise AppError("Quantity must be at least 1")
        needed[line.item_id] = needed.get(line.item_id, 0) + line.quantity
    for item_id, qty in needed.items():
        have = stock_qty(db, shop_id, item_id)
        if have < qty:
            raise AppError(f"Not enough stock for {_item(db, item_id).name}")
    number = int(db.scalar(select(func.max(Bill.number)).where(Bill.shop_id == shop_id)) or 0) + 1
    bill = Bill(
        shop_id=shop_id,
        number=number,
        kind=kind,
        customer_id=customer.id if customer else None,
        date=date,
        site_note=clean_text(site_note, "Site note", required=False, limit=300),
        total_paise=0,
    )
    db.add(bill)
    db.flush()
    total = 0
    reason = "sale" if kind == "counter" else "job"
    for line in lines:
        item = _item(db, line.item_id)
        line_total = _line_total(line.quantity, line.unit_price_paise, "Rate")
        total += line_total
        db.add(
            BillLine(
                bill_id=bill.id,
                item_id=item.id,
                description=item.name,
                quantity=line.quantity,
                unit_price_paise=line.unit_price_paise,
                line_total_paise=line_total,
                is_service=False,
            )
        )
        _change_stock(db, shop_id, item.id, -line.quantity, reason, "bill", bill.id)
    for service in services:
        amount = check_paise(service.amount_paise, "Service amount")
        if amount <= 0:
            raise AppError("Service amount must be more than zero")
        total += amount
        db.add(
            BillLine(
                bill_id=bill.id,
                item_id=None,
                description=clean_text(service.description, "Service", limit=160),
                quantity=1,
                unit_price_paise=amount,
                line_total_paise=amount,
                is_service=True,
            )
        )
    if total <= 0:
        raise AppError("Bill total must be more than zero")
    if total > MAX_PAISE:
        raise AppError("Amount is too large")
    bill.total_paise = total
    if paid_now:
        _receipt(
            db,
            shop_id,
            bill,
            check_paise(paid_now, "Payment"),
            clean_method(method),
            date,
            note,
            customer.id if customer else None,
        )
    return bill


def list_bills(db: Session, shop_id: int, kind: str = "") -> list[Bill]:
    stmt = select(Bill).where(Bill.shop_id == shop_id)
    if kind in ("counter", "job"):
        stmt = stmt.where(Bill.kind == kind)
    return list(db.scalars(stmt.order_by(Bill.date.desc(), Bill.id.desc())))


def get_shop_bill(db: Session, shop_id: int, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None or bill.shop_id != shop_id:
        raise AppError("Bill not found for this shop", 404)
    return bill


def get_shop_purchase(db: Session, shop_id: int, purchase_id: int) -> Purchase:
    purchase = db.get(Purchase, purchase_id)
    if purchase is None or purchase.shop_id != shop_id:
        raise AppError("Purchase not found for this shop", 404)
    return purchase


@transactional
def record_ledger(
    db: Session,
    shop_id: int,
    category: str,
    amount_paise: int,
    method: str,
    date: str,
    note: str,
    bill_id: int | None = None,
    purchase_id: int | None = None,
) -> LedgerEntry:
    if category not in CATEGORIES:
        raise AppError("Unknown cash entry")
    date = parse_date(date)
    amount = check_paise(amount_paise, "Amount")
    if amount <= 0:
        raise AppError("Enter an amount")
    method = clean_method(method)
    note = clean_text(note or "", "Note", required=False, limit=300)
    if category == "customer_receipt":
        if not bill_id:
            raise AppError("Choose the bill this payment is for")
        bill = get_shop_bill(db, shop_id, bill_id)
        return _receipt(db, shop_id, bill, amount, method, date, note, bill.customer_id)
    if category == "vendor_payout":
        if not purchase_id:
            raise AppError("Choose the purchase this payment is for")
        purchase = get_shop_purchase(db, shop_id, purchase_id)
        return _payout(db, shop_id, purchase, amount, method, date, note)
    if category == "expense" and not note:
        raise AppError("Add a note for this expense")
    entry = LedgerEntry(
        shop_id=shop_id,
        date=date,
        direction=CATEGORIES[category],
        amount_paise=amount,
        category=category,
        method=method,
        note=note,
    )
    db.add(entry)
    db.flush()
    return entry


def _sum(db: Session, shop_id: int, direction: str, *, before: str | None = None, on: str | None = None) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).where(
        LedgerEntry.shop_id == shop_id,
        LedgerEntry.direction == direction,
    )
    if before is not None:
        stmt = stmt.where(LedgerEntry.date < before)
    if on is not None:
        stmt = stmt.where(LedgerEntry.date == on)
    return int(db.scalar(stmt) or 0)


def wallet_totals(db: Session, shop_id: int, date: str) -> dict[str, int | str]:
    date = parse_date(date)
    opening = _sum(db, shop_id, "in", before=date) - _sum(db, shop_id, "out", before=date)
    today_in = _sum(db, shop_id, "in", on=date)
    today_out = _sum(db, shop_id, "out", on=date)
    return {
        "date": date,
        "opening_paise": opening,
        "in_paise": today_in,
        "out_paise": today_out,
        "closing_paise": opening + today_in - today_out,
    }


def has_opening(db: Session, shop_id: int) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.shop_id == shop_id, LedgerEntry.category == "opening")
    )
    return bool(count)


def ledger_on(db: Session, shop_id: int, date: str) -> list[LedgerEntry]:
    date = parse_date(date)
    return list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.shop_id == shop_id, LedgerEntry.date == date)
            .order_by(LedgerEntry.id)
        )
    )
