import socket
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from books.access import ensure_profile, needs_setup, require_owner, require_shop, shops_for
from books.errors import AppError
from books.models import Bill, Item, LedgerEntry, Purchase
from books.money import paise_to_input, parse_date, parse_rupees, parse_whole, shift_date, today_ist
from books.present import attach_bill_balances, attach_purchase_balances, due_bills, due_purchases
from books.services import (
    ItemLine,
    ServiceLine,
    adjust_stock,
    create_bill,
    create_customer,
    create_item,
    create_owner,
    create_purchase,
    create_shop,
    create_staff,
    create_vendor,
    get_shop_bill,
    get_shop_purchase,
    has_opening,
    ledger_on,
    list_customers,
    list_items,
    list_vendors,
    login as password_login,
    record_ledger,
    stock_map,
    stock_qty,
    update_item,
    wallet_totals,
)


def with_shop(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if needs_setup():
            return redirect("setup")
        shops = list(shops_for(request.user))
        chosen = request.session.get("shop_id")
        shop = next((row for row in shops if row.id == chosen), None)
        if shop is None and shops:
            shop = shops[0]
            request.session["shop_id"] = shop.id
        request.shop = shop
        request.shops = shops
        return view(request, *args, **kwargs)

    return wrapper


def optional_int(value: str):
    text = (value or "").strip()
    if not text:
        return None
    if not text.isdigit():
        raise AppError("Choose a valid record")
    return int(text)


def parse_item_lines(item_ids, qtys, prices, label):
    lines = []
    for item_id, qty, price in zip(item_ids, qtys, prices):
        if not str(item_id).strip() and not str(qty).strip() and not str(price).strip():
            continue
        if not str(item_id).strip():
            raise AppError("Choose an item on each line")
        parsed = ItemLine(int(item_id), parse_whole(qty, "Quantity"), parse_rupees(price, label))
        if parsed.quantity <= 0:
            raise AppError("Quantity must be at least 1")
        lines.append(parsed)
    return lines


def parse_services(descs, amounts):
    lines = []
    for desc, amount in zip(descs, amounts):
        if not str(desc).strip() and not str(amount).strip():
            continue
        lines.append(ServiceLine(desc, parse_rupees(amount, "Service amount")))
    return lines


def posted_shop(request):
    shop_id = int(request.POST.get("shop_id") or 0)
    shop = require_shop(request.user, shop_id)
    current = request.session.get("shop_id")
    if current and current != shop.id:
        raise AppError("Shop changed. Open the page again.")
    return shop


def server_hint(request) -> str:
    host = request.get_host().split(":")[0]
    port = request.get_port()
    if host in {"127.0.0.1", "localhost"}:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return f"http://{sock.getsockname()[0]}:{port}"
        except OSError:
            return request.build_absolute_uri("/").rstrip("/")
        finally:
            sock.close()
    return request.build_absolute_uri("/").rstrip("/")


def setup_page(request):
    if not needs_setup():
        return redirect("today" if request.user.is_authenticated else "login")
    error = None
    if request.method == "POST":
        try:
            user, _token = create_owner(request.POST.get("name", ""), request.POST.get("username", ""), request.POST.get("password", ""))
            auth_login(request, user)
            return redirect("today")
        except AppError as exc:
            error = exc.message
    return render(request, "books/auth.html", {"title": "Set up", "mode": "setup", "error": error})


def login_page(request):
    if needs_setup():
        return redirect("setup")
    if request.user.is_authenticated:
        return redirect("today")
    error = None
    if request.method == "POST":
        try:
            user, _token = password_login(request.POST.get("username", ""), request.POST.get("password", ""))
            auth_login(request, user)
            return redirect("today")
        except AppError as exc:
            error = exc.message
    return render(request, "books/auth.html", {"title": "Log in", "mode": "login", "error": error})


def logout_page(request):
    auth_logout(request)
    return redirect("login")


@require_POST
@with_shop
def switch_shop(request):
    shop = require_shop(request.user, int(request.POST.get("shop_id") or 0))
    request.session["shop_id"] = shop.id
    return redirect(request.META.get("HTTP_REFERER") or "today")


@with_shop
def today(request):
    request.nav = "today"
    summary = None
    if request.shop:
        summary = wallet_totals(request.shop.id, today_ist())
        summary["has_opening"] = has_opening(request.shop.id)
        summary["unpaid_bills"] = due_bills(request.shop.id)
        summary["unpaid_purchases"] = due_purchases(request.shop.id)
    return render(request, "books/today.html", {"title": "Today", "summary": summary})


@with_shop
def inventory(request):
    request.nav = "stock"
    q = request.GET.get("q", "")
    counts = stock_map(request.shop.id) if request.shop else {}
    rows = [(item, counts.get(item.id, 0)) for item in list_items(q)]
    return render(request, "books/inventory.html", {"title": "Stock", "rows": rows, "q": q})


@with_shop
def item_new(request):
    request.nav = "stock"
    form = {}
    if request.method == "POST":
        form = request.POST
        try:
            create_item(
                request.POST.get("name", ""),
                request.POST.get("unit") or "pcs",
                parse_rupees(request.POST.get("sale_price", ""), "Sale price"),
                request.POST.get("generate_code") == "on",
            )
            return redirect("inventory")
        except AppError as exc:
            return render(request, "books/item_form.html", {"title": "New item", "form": form, "error": exc.message})
    return render(request, "books/item_form.html", {"title": "New item", "form": form})


@with_shop
def item_page(request, item_id):
    request.nav = "stock"
    item = get_object_or_404(Item, pk=item_id)
    if request.method == "POST":
        try:
            update_item(
                item.id,
                request.POST.get("name", ""),
                request.POST.get("unit") or "pcs",
                parse_rupees(request.POST.get("sale_price", ""), "Sale price"),
                request.POST.get("generate_code") == "on",
            )
            return redirect("item", item_id=item.id)
        except AppError as exc:
            messages.error(request, exc.message)
            item.refresh_from_db()
    quantity = stock_qty(request.shop.id, item.id) if request.shop else 0
    return render(request, "books/item_detail.html", {"title": item.name, "item": item, "quantity": quantity})


@require_POST
@with_shop
def item_adjust(request, item_id):
    try:
        shop = posted_shop(request)
        adjust_stock(shop.id, item_id, parse_whole(request.POST.get("quantity_delta", ""), "Quantity change"), request.POST.get("note", ""))
    except AppError as exc:
        messages.error(request, exc.message)
    return redirect("item", item_id=item_id)


@with_shop
def vendors_page(request):
    request.nav = "more"
    if request.method == "POST":
        try:
            create_vendor(request.POST.get("name", ""), request.POST.get("phone", ""), request.POST.get("note", ""))
            return redirect("vendors")
        except AppError as exc:
            messages.error(request, exc.message)
    q = request.GET.get("q", "")
    return render(request, "books/vendors.html", {"title": "Vendors", "vendors": list_vendors(q), "q": q})


@with_shop
def customers_page(request):
    request.nav = "more"
    if request.method == "POST":
        try:
            shop = posted_shop(request)
            create_customer(shop.id, request.POST.get("name", ""), request.POST.get("phone", ""), request.POST.get("address", ""))
            return redirect("customers")
        except AppError as exc:
            messages.error(request, exc.message)
    q = request.GET.get("q", "")
    customers = list_customers(request.shop.id, q) if request.shop else []
    return render(request, "books/customers.html", {"title": "Customers", "customers": customers, "q": q})


@with_shop
def purchases_page(request):
    request.nav = "more"
    rows = []
    if request.shop:
        rows = attach_purchase_balances(list(Purchase.objects.filter(shop=request.shop).select_related("vendor")))
    return render(request, "books/purchases.html", {"title": "Stock in", "purchases": rows})


@with_shop
def purchase_new(request):
    request.nav = "more"
    context = {
        "title": "Receive stock",
        "vendors": list_vendors(),
        "items": list_items(),
        "stock": stock_map(request.shop.id) if request.shop else {},
        "cost_mode": True,
        "price_label": "Cost",
    }
    if request.method == "POST":
        try:
            shop = posted_shop(request)
            create_purchase(
                shop.id,
                int(request.POST.get("vendor_id") or 0),
                request.POST.get("date") or today_ist().isoformat(),
                parse_item_lines(request.POST.getlist("item_id"), request.POST.getlist("qty"), request.POST.getlist("unit_price"), "Cost"),
                request.POST.get("note", ""),
            )
            return redirect("purchases")
        except AppError as exc:
            context["error"] = exc.message
    return render(request, "books/purchase_form.html", context)


@with_shop
def purchase_page(request, purchase_id):
    request.nav = "more"
    if request.shop is None:
        return redirect("today")
    try:
        purchase = get_shop_purchase(request.shop.id, purchase_id)
    except AppError as exc:
        messages.error(request, exc.message)
        return redirect("purchases")
    attach_purchase_balances([purchase])
    purchase.line_rows = list(purchase.lines.select_related("item"))
    return render(request, "books/purchase_detail.html", {"title": "Stock in", "purchase": purchase})


@require_POST
@with_shop
def purchase_pay(request, purchase_id):
    try:
        shop = posted_shop(request)
        record_ledger(
            shop.id,
            "vendor_payout",
            parse_rupees(request.POST.get("amount", ""), "Payment"),
            request.POST.get("method") or "cash",
            request.POST.get("date") or today_ist().isoformat(),
            request.POST.get("note", ""),
            None,
            purchase_id,
        )
    except AppError as exc:
        messages.error(request, exc.message)
    return redirect("purchase", purchase_id=purchase_id)


def bill_context(request, kind):
    request.nav = "bills"
    return {
        "title": "Counter sale" if kind == "counter" else "Installation",
        "kind": kind,
        "customers": list_customers(request.shop.id) if request.shop else [],
        "items": list_items(),
        "stock": stock_map(request.shop.id) if request.shop else {},
        "cost_mode": False,
        "price_label": "Rate",
    }


def save_bill(request, kind):
    shop = posted_shop(request)
    paid_text = (request.POST.get("paid_now") or "").strip()
    paid = 0 if not paid_text else parse_rupees(paid_text, "Payment")
    return create_bill(
        shop.id,
        kind,
        optional_int(request.POST.get("customer_id", "")),
        request.POST.get("date") or today_ist().isoformat(),
        request.POST.get("site_note", ""),
        parse_item_lines(request.POST.getlist("item_id"), request.POST.getlist("qty"), request.POST.getlist("unit_price"), "Rate"),
        parse_services(request.POST.getlist("service_desc"), request.POST.getlist("service_amount")),
        paid,
        request.POST.get("method") or "cash",
        request.POST.get("note", ""),
    )


@with_shop
def sale_new(request):
    context = bill_context(request, "counter")
    if request.method == "POST":
        try:
            bill = save_bill(request, "counter")
            return redirect("bill", bill_id=bill.id)
        except AppError as exc:
            context["error"] = exc.message
    return render(request, "books/bill_form.html", context)


@with_shop
def job_new(request):
    context = bill_context(request, "job")
    if request.method == "POST":
        try:
            bill = save_bill(request, "job")
            return redirect("bill", bill_id=bill.id)
        except AppError as exc:
            context["error"] = exc.message
    return render(request, "books/bill_form.html", context)


@with_shop
def bills_page(request):
    request.nav = "bills"
    kind = request.GET.get("kind", "")
    rows = []
    if request.shop:
        query = Bill.objects.filter(shop=request.shop).select_related("customer")
        if kind in {"counter", "job"}:
            query = query.filter(kind=kind)
        rows = attach_bill_balances(list(query))
    return render(request, "books/bills.html", {"title": "Bills", "bills": rows, "kind": kind})


@with_shop
def bill_page(request, bill_id):
    request.nav = "bills"
    if request.shop is None:
        return redirect("today")
    try:
        bill = get_shop_bill(request.shop.id, bill_id)
    except AppError as exc:
        messages.error(request, exc.message)
        return redirect("bills")
    attach_bill_balances([bill])
    bill.line_rows = list(bill.lines.all())
    bill.receipts = list(bill.payments.filter(category="customer_receipt"))
    return render(request, "books/bill_detail.html", {"title": f"Bill #{bill.number:04d}", "bill": bill})


@require_POST
@with_shop
def bill_pay(request, bill_id):
    try:
        shop = posted_shop(request)
        record_ledger(
            shop.id,
            "customer_receipt",
            parse_rupees(request.POST.get("amount", ""), "Payment"),
            request.POST.get("method") or "cash",
            request.POST.get("date") or today_ist().isoformat(),
            request.POST.get("note", ""),
            bill_id,
            None,
        )
    except AppError as exc:
        messages.error(request, exc.message)
    return redirect("bill", bill_id=bill_id)


@require_POST
@with_shop
def bill_unpay(request, bill_id, entry_id):
    try:
        shop = posted_shop(request)
        bill = get_shop_bill(shop.id, bill_id)
        entry = LedgerEntry.objects.filter(pk=entry_id, bill=bill, shop=shop, category="customer_receipt").first()
        if entry is None:
            raise AppError("Payment not found")
        entry.delete()
        messages.success(request, "Payment removed. The balance is due again.")
    except AppError as exc:
        messages.error(request, exc.message)
    return redirect("bill", bill_id=bill_id)


@with_shop
def wallet_page(request):
    request.nav = "cash"
    day = today_ist()
    if request.GET.get("date"):
        try:
            day = parse_date(request.GET.get("date"))
        except AppError as exc:
            messages.error(request, exc.message)
    wallet = wallet_totals(request.shop.id, day) if request.shop else None
    entries = ledger_on(request.shop.id, day) if request.shop else []
    return render(
        request,
        "books/wallet.html",
        {"title": "Cash", "date": day, "prev": shift_date(day, -1), "next": shift_date(day, 1), "wallet": wallet, "entries": entries},
    )


@with_shop
def wallet_new(request):
    request.nav = "cash"
    kind = request.GET.get("kind") or request.POST.get("category") or "expense"
    if kind not in {"customer_receipt", "vendor_payout", "expense", "opening"}:
        kind = "expense"
    bills_due = due_bills(request.shop.id) if request.shop else []
    purchases_due = due_purchases(request.shop.id) if request.shop else []
    amount = ""
    bill_id = request.GET.get("bill_id") or ""
    purchase_id = request.GET.get("purchase_id") or ""
    if bill_id.isdigit():
        match = next((row for row in bills_due if row["id"] == int(bill_id)), None)
        if match:
            amount = paise_to_input(match["balance_paise"])
            kind = "customer_receipt"
    if purchase_id.isdigit():
        match = next((row for row in purchases_due if row["id"] == int(purchase_id)), None)
        if match:
            amount = paise_to_input(match["balance_paise"])
            kind = "vendor_payout"
    if request.method == "POST":
        try:
            shop = posted_shop(request)
            record_ledger(
                shop.id,
                request.POST.get("category") or kind,
                parse_rupees(request.POST.get("amount", ""), "Amount"),
                request.POST.get("method") or "cash",
                request.POST.get("date") or today_ist().isoformat(),
                request.POST.get("note", ""),
                optional_int(request.POST.get("bill_id", "")),
                optional_int(request.POST.get("purchase_id", "")),
                optional_int(request.POST.get("vendor_id", "")),
            )
            return redirect("wallet")
        except AppError as exc:
            messages.error(request, exc.message)
            amount = request.POST.get("amount", amount)
    return render(
        request,
        "books/ledger_form.html",
        {
            "title": "Money in / out",
            "kind": kind,
            "bills_due": bills_due,
            "purchases_due": purchases_due,
            "vendors": list_vendors(),
            "amount": amount,
            "bill_id": int(bill_id) if str(bill_id).isdigit() else None,
            "purchase_id": int(purchase_id) if str(purchase_id).isdigit() else None,
        },
    )


@with_shop
def more_page(request):
    request.nav = "more"
    return render(request, "books/more.html", {"title": "More", "server_hint": server_hint(request)})


@with_shop
def settings_page(request):
    request.nav = "more"
    try:
        require_owner(request.user)
    except AppError as exc:
        messages.error(request, exc.message)
        return redirect("more")
    from django.contrib.auth.models import User

    people = []
    for person in User.objects.order_by("username"):
        ensure_profile(person)
        people.append(person)
    return render(request, "books/settings.html", {"title": "Settings", "people": people})


@require_POST
@with_shop
def settings_shop(request):
    try:
        shop = create_shop(request.user, request.POST.get("name", ""), request.POST.get("address", ""), request.POST.get("phone", ""))
        request.session["shop_id"] = shop.id
        return redirect("today")
    except AppError as exc:
        messages.error(request, exc.message)
        return redirect("settings")


@require_POST
@with_shop
def settings_user(request):
    try:
        create_staff(
            request.user,
            request.POST.get("name", ""),
            request.POST.get("username", ""),
            request.POST.get("password", ""),
            [int(value) for value in request.POST.getlist("shop_ids")],
        )
        messages.success(request, "Staff added")
    except AppError as exc:
        messages.error(request, exc.message)
    return redirect("settings")
