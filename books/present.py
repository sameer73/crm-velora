from books.access import ensure_profile, shops_for
from books.money import format_inr
from books.models import BillLine, PurchaseLine
from books.services import has_opening, ledger_on, paid_map, wallet_totals


def iso(value) -> str:
    return value.isoformat()


def user_payload(user) -> dict:
    profile = ensure_profile(user)
    shop_ids = list(shops_for(user).values_list("id", flat=True))
    return {
        "id": user.id,
        "name": profile.name,
        "username": user.username,
        "role": profile.role,
        "shop_ids": shop_ids,
    }


def item_payload(item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "unit": item.unit,
        "sale_price_paise": item.sale_price_paise,
        "last_cost_paise": item.last_cost_paise,
        "code": item.code,
        "qr_url": item.qr_image.url if item.qr_image else None,
    }


def ledger_label(entry) -> str:
    if entry.category == "customer_receipt":
        return "Customer payment"
    if entry.category == "vendor_payout":
        return "Paid vendor"
    if entry.category == "opening":
        return "Cash in hand"
    return entry.note or "Expense"


def entry_payload(entry) -> dict:
    return {
        "id": entry.id,
        "date": iso(entry.date),
        "direction": entry.direction,
        "amount_paise": entry.amount_paise,
        "category": entry.category,
        "method": entry.method,
        "note": entry.note,
        "bill_id": entry.bill_id,
        "purchase_id": entry.purchase_id,
        "label": ledger_label(entry),
    }


def attach_bill_balances(bills):
    paid = paid_map("bill_id", "customer_receipt", [bill.id for bill in bills])
    for bill in bills:
        bill.paid_sum = paid.get(bill.id, 0)
        bill.balance_sum = bill.total_paise - bill.paid_sum
    return bills


def attach_purchase_balances(purchases):
    paid = paid_map("purchase_id", "vendor_payout", [row.id for row in purchases])
    for purchase in purchases:
        purchase.paid_sum = paid.get(purchase.id, 0)
        purchase.balance_sum = purchase.total_paise - purchase.paid_sum
    return purchases


def bill_payload(bill, lines=None) -> dict:
    paid = getattr(bill, "paid_sum", None)
    if paid is None:
        paid = paid_map("bill_id", "customer_receipt", [bill.id]).get(bill.id, 0)
    if lines is None:
        lines = list(bill.lines.all())
    return {
        "id": bill.id,
        "number": bill.number,
        "kind": bill.kind,
        "customer_id": bill.customer_id,
        "customer_name": bill.customer.name if bill.customer_id else None,
        "date": iso(bill.date),
        "site_note": bill.site_note,
        "total_paise": bill.total_paise,
        "paid_paise": paid,
        "balance_paise": bill.total_paise - paid,
        "lines": [
            {
                "id": line.id,
                "item_id": line.item_id,
                "description": line.description,
                "quantity": line.quantity,
                "unit_price_paise": line.unit_price_paise,
                "line_total_paise": line.line_total_paise,
                "is_service": line.is_service,
            }
            for line in lines
        ],
    }


def bills_payload(bills) -> list[dict]:
    bills = list(bills)
    attach_bill_balances(bills)
    grouped: dict[int, list] = {}
    if bills:
        for line in BillLine.objects.filter(bill_id__in=[bill.id for bill in bills]).order_by("id"):
            grouped.setdefault(line.bill_id, []).append(line)
    return [bill_payload(bill, grouped.get(bill.id, [])) for bill in bills]


def purchase_payload(purchase, lines=None) -> dict:
    paid = getattr(purchase, "paid_sum", None)
    if paid is None:
        paid = paid_map("purchase_id", "vendor_payout", [purchase.id]).get(purchase.id, 0)
    if lines is None:
        lines = list(purchase.lines.select_related("item"))
    return {
        "id": purchase.id,
        "vendor_id": purchase.vendor_id,
        "vendor_name": purchase.vendor.name,
        "date": iso(purchase.date),
        "note": purchase.note,
        "total_paise": purchase.total_paise,
        "paid_paise": paid,
        "balance_paise": purchase.total_paise - paid,
        "lines": [
            {
                "id": line.id,
                "item_id": line.item_id,
                "name": line.item.name,
                "quantity": line.quantity,
                "unit_cost_paise": line.unit_cost_paise,
                "line_total_paise": line.line_total_paise,
            }
            for line in lines
        ],
    }


def purchases_payload(purchases) -> list[dict]:
    purchases = list(purchases)
    attach_purchase_balances(purchases)
    grouped: dict[int, list] = {}
    if purchases:
        for line in PurchaseLine.objects.filter(purchase_id__in=[row.id for row in purchases]).select_related("item").order_by("id"):
            grouped.setdefault(line.purchase_id, []).append(line)
    return [purchase_payload(row, grouped.get(row.id, [])) for row in purchases]


def due_bills(shop_id) -> list[dict]:
    from books.models import Bill

    dues = []
    for bill in bills_payload(Bill.objects.filter(shop_id=shop_id).select_related("customer")):
        if bill["balance_paise"] <= 0:
            continue
        kind = "Installation" if bill["kind"] == "job" else "Counter sale"
        dues.append(
            {
                "id": bill["id"],
                "title": bill["customer_name"] or "Walk-in",
                "subtitle": f"Bill #{bill['number']:04d} · {kind} · paid {format_inr(bill['paid_paise'])} of {format_inr(bill['total_paise'])}",
                "date": bill["date"],
                "total_paise": bill["total_paise"],
                "paid_paise": bill["paid_paise"],
                "balance_paise": bill["balance_paise"],
            }
        )
    return dues


def due_purchases(shop_id) -> list[dict]:
    from books.models import Purchase

    dues = []
    for purchase in purchases_payload(Purchase.objects.filter(shop_id=shop_id).select_related("vendor")):
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


def today_payload(shop) -> dict:
    from books.money import today_ist

    day = today_ist()
    totals = wallet_totals(shop.id, day)
    totals["date"] = iso(totals["date"])
    return {
        **totals,
        "shop_id": shop.id,
        "shop_name": shop.name,
        "has_opening": has_opening(shop.id),
        "unpaid_bills": due_bills(shop.id),
        "unpaid_purchases": due_purchases(shop.id),
    }


def wallet_payload(shop_id, day) -> dict:
    totals = wallet_totals(shop_id, day)
    totals["date"] = iso(totals["date"])
    totals["entries"] = [entry_payload(entry) for entry in ledger_on(shop_id, day)]
    return totals
