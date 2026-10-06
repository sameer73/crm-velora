from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Bill, BillLine, Customer, Item, LedgerEntry, Purchase, PurchaseLine, Vendor
from app.services import has_opening, ledger_on, list_bills, list_purchases, wallet_totals


def ledger_label(entry: LedgerEntry) -> str:
    if entry.category == "customer_receipt":
        return "Customer payment"
    if entry.category == "vendor_payout":
        return "Paid vendor"
    if entry.category == "opening":
        return "Cash in hand"
    return entry.note or "Expense"


def present_entry(entry: LedgerEntry) -> dict:
    return {
        "id": entry.id,
        "date": entry.date,
        "direction": entry.direction,
        "amount_paise": entry.amount_paise,
        "category": entry.category,
        "method": entry.method,
        "note": entry.note,
        "bill_id": entry.bill_id,
        "purchase_id": entry.purchase_id,
        "label": ledger_label(entry),
    }


def present_item(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "unit": item.unit,
        "sale_price_paise": item.sale_price_paise,
        "last_cost_paise": item.last_cost_paise,
    }


def present_bills(db: Session, bills: list[Bill]) -> list[dict]:
    if not bills:
        return []
    ids = [bill.id for bill in bills]
    paid_rows = db.execute(
        select(LedgerEntry.bill_id, func.coalesce(func.sum(LedgerEntry.amount_paise), 0))
        .where(LedgerEntry.bill_id.in_(ids), LedgerEntry.category == "customer_receipt")
        .group_by(LedgerEntry.bill_id)
    ).all()
    paid = {bill_id: int(amount) for bill_id, amount in paid_rows}
    customer_ids = {bill.customer_id for bill in bills if bill.customer_id}
    customers: dict[int, str] = {}
    if customer_ids:
        for customer in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))):
            customers[customer.id] = customer.name
    grouped: dict[int, list[dict]] = {}
    lines = db.scalars(select(BillLine).where(BillLine.bill_id.in_(ids)).order_by(BillLine.id)).all()
    for line in lines:
        grouped.setdefault(line.bill_id, []).append(
            {
                "id": line.id,
                "item_id": line.item_id,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price_paise": line.unit_price_paise,
                "line_total_paise": line.line_total_paise,
                "is_service": bool(line.is_service),
            }
        )
    result = []
    for bill in bills:
        paid_paise = paid.get(bill.id, 0)
        result.append(
            {
                "id": bill.id,
                "number": bill.number,
                "kind": bill.kind,
                "customer_id": bill.customer_id,
                "customer_name": customers.get(bill.customer_id) if bill.customer_id else None,
                "date": bill.date,
                "site_note": bill.site_note,
                "total_paise": bill.total_paise,
                "paid_paise": paid_paise,
                "balance_paise": bill.total_paise - paid_paise,
                "lines": grouped.get(bill.id, []),
            }
        )
    return result


def present_bill(db: Session, bill: Bill) -> dict:
    return present_bills(db, [bill])[0]


def present_purchases(db: Session, purchases: list[Purchase]) -> list[dict]:
    if not purchases:
        return []
    ids = [purchase.id for purchase in purchases]
    paid_rows = db.execute(
        select(LedgerEntry.purchase_id, func.coalesce(func.sum(LedgerEntry.amount_paise), 0))
        .where(LedgerEntry.purchase_id.in_(ids), LedgerEntry.category == "vendor_payout")
        .group_by(LedgerEntry.purchase_id)
    ).all()
    paid = {purchase_id: int(amount) for purchase_id, amount in paid_rows}
    vendor_ids = {purchase.vendor_id for purchase in purchases}
    vendors = {
        vendor.id: vendor.name
        for vendor in db.scalars(select(Vendor).where(Vendor.id.in_(vendor_ids)))
    }
    grouped: dict[int, list[dict]] = {}
    lines = db.scalars(
        select(PurchaseLine).where(PurchaseLine.purchase_id.in_(ids)).order_by(PurchaseLine.id)
    ).all()
    item_ids = {line.item_id for line in lines}
    names = {
        item.id: item.name for item in db.scalars(select(Item).where(Item.id.in_(item_ids)))
    } if item_ids else {}
    for line in lines:
        grouped.setdefault(line.purchase_id, []).append(
            {
                "id": line.id,
                "item_id": line.item_id,
                "name": names.get(line.item_id, "Item"),
                "quantity": line.quantity,
                "unit_cost_paise": line.unit_cost_paise,
                "line_total_paise": line.line_total_paise,
            }
        )
    result = []
    for purchase in purchases:
        paid_paise = paid.get(purchase.id, 0)
        result.append(
            {
                "id": purchase.id,
                "vendor_id": purchase.vendor_id,
                "vendor_name": vendors.get(purchase.vendor_id, "Vendor"),
                "date": purchase.date,
                "note": purchase.note,
                "total_paise": purchase.total_paise,
                "paid_paise": paid_paise,
                "balance_paise": purchase.total_paise - paid_paise,
                "lines": grouped.get(purchase.id, []),
            }
        )
    return result


def present_purchase(db: Session, purchase: Purchase) -> dict:
    return present_purchases(db, [purchase])[0]


def unpaid_bills(db: Session, shop_id: int) -> list[dict]:
    dues = []
    for bill in present_bills(db, list_bills(db, shop_id)):
        if bill["balance_paise"] <= 0:
            continue
        kind = "Installation" if bill["kind"] == "job" else "Counter sale"
        dues.append(
            {
                "id": bill["id"],
                "title": bill["customer_name"] or "Walk-in",
                "subtitle": f"Bill #{bill['number']:04d} · {kind}",
                "date": bill["date"],
                "total_paise": bill["total_paise"],
                "paid_paise": bill["paid_paise"],
                "balance_paise": bill["balance_paise"],
            }
        )
    return dues


def unpaid_purchases(db: Session, shop_id: int) -> list[dict]:
    dues = []
    for purchase in present_purchases(db, list_purchases(db, shop_id)):
        if purchase["balance_paise"] <= 0:
            continue
        dues.append(
            {
                "id": purchase["id"],
                "title": purchase["vendor_name"],
                "subtitle": "Stock in",
                "date": purchase["date"],
                "total_paise": purchase["total_paise"],
                "paid_paise": purchase["paid_paise"],
                "balance_paise": purchase["balance_paise"],
            }
        )
    return dues


def present_wallet(db: Session, shop_id: int, date: str) -> dict:
    totals = wallet_totals(db, shop_id, date)
    totals["entries"] = [present_entry(entry) for entry in ledger_on(db, shop_id, str(totals["date"]))]
    return totals


def present_today(db: Session, shop) -> dict:
    from app.money import today_ist

    date = today_ist()
    totals = wallet_totals(db, shop.id, date)
    return {
        **totals,
        "shop_id": shop.id,
        "shop_name": shop.name,
        "has_opening": has_opening(db, shop.id),
        "unpaid_bills": unpaid_bills(db, shop.id),
        "unpaid_purchases": unpaid_purchases(db, shop.id),
    }
