import socket
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import end_session, needs_setup, require_shop, shop_ids_for, shops_for, user_from_token
from app.db import get_db
from app.errors import AppError
from app.models import User
from app.money import paise_to_input, parse_date, parse_rupees, parse_whole, shift_date, today_ist
from app.present import present_bill, present_purchase, present_today, present_wallet, unpaid_bills, unpaid_purchases
from app.services import (
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
    list_bills,
    list_customers,
    list_items,
    list_purchases,
    list_users,
    list_vendors,
    login,
    record_ledger,
    stock_map,
    stock_qty,
    update_item,
)
from app.templating import render

router = APIRouter()


class LoginRedirect(Exception):
    pass


class SetupRedirect(Exception):
    pass


def web_user(request: Request, db: Session = Depends(get_db)) -> User:
    if needs_setup(db):
        raise SetupRedirect()
    user = user_from_token(db, request.cookies.get("crm_session"))
    if user is None:
        raise LoginRedirect()
    return user


def cookie(response: RedirectResponse, token: str | None = None, shop_id: int | None = None) -> RedirectResponse:
    if token:
        response.set_cookie("crm_session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30, path="/")
    if shop_id is not None:
        response.set_cookie("crm_shop", str(shop_id), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365, path="/")
    return response


def page(request: Request, db: Session, user: User, **extra) -> dict:
    shops = shops_for(db, user)
    raw = request.cookies.get("crm_shop")
    shop = None
    if raw and raw.isdigit():
        shop = next((item for item in shops if item.id == int(raw)), None)
    if shop is None and shops:
        shop = shops[0]
    ctx = {
        "user": user,
        "shops": shops,
        "shop": shop,
        "error": request.query_params.get("error"),
        "notice": request.query_params.get("notice"),
        "nav": "",
        "today": today_ist(),
        "server_hint": server_hint(request),
    }
    ctx.update(extra)
    return ctx


def paint(request: Request, name: str, ctx: dict, status: int = 200):
    response = render(request, name, ctx, status)
    shop = ctx.get("shop")
    if shop is not None and request.cookies.get("crm_shop") != str(shop.id):
        response.set_cookie(
            "crm_shop",
            str(shop.id),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365,
            path="/",
        )
    return response


def posted_shop(request: Request, db: Session, user: User, shop_id: int):
    shop = require_shop(db, user, shop_id)
    raw = request.cookies.get("crm_shop")
    if raw and raw.isdigit() and int(raw) != shop.id:
        raise AppError("Shop changed. Open the page again.")
    return shop


def optional_int(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    if not text.isdigit():
        raise AppError("Choose a valid record")
    return int(text)


def parse_item_lines(item_ids: list[str], qtys: list[str], prices: list[str], price_label: str) -> list[ItemLine]:
    lines: list[ItemLine] = []
    for item_id, qty, price in zip(item_ids, qtys, prices):
        if not item_id.strip() and not qty.strip() and not price.strip():
            continue
        if not item_id.strip():
            raise AppError("Choose an item on each line")
        lines.append(ItemLine(int(item_id), parse_whole(qty, "Quantity"), parse_rupees(price, price_label)))
        if lines[-1].quantity <= 0:
            raise AppError("Quantity must be at least 1")
    return lines


def parse_services(descs: list[str], amounts: list[str]) -> list[ServiceLine]:
    lines: list[ServiceLine] = []
    for desc, amount in zip(descs, amounts):
        if not desc.strip() and not str(amount).strip():
            continue
        lines.append(ServiceLine(desc, parse_rupees(amount, "Service amount")))
    return lines


def server_hint(request: Request) -> str:
    port = request.url.port or 8000
    host = request.url.hostname or "127.0.0.1"
    if host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        ip = lan_ip()
        if ip:
            return f"http://{ip}:{port}"
    return str(request.base_url).rstrip("/")


def lan_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def safe_next(request: Request) -> str:
    ref = request.headers.get("referer") or "/"
    parsed = urlparse(ref)
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return "/"
    if parsed.query:
        return f"{parsed.path}?{parsed.query}"
    return parsed.path


@router.get("/setup")
def setup_page(request: Request, db: Session = Depends(get_db)):
    if not needs_setup(db):
        if user_from_token(db, request.cookies.get("crm_session")):
            return RedirectResponse("/", status_code=303)
        return RedirectResponse("/login", status_code=303)
    return render(request, "auth.html", {"title": "Set up", "mode": "setup", "error": None})


@router.post("/setup")
def setup_post(
    request: Request,
    name: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user, token = create_owner(db, name, username, password)
        del user
    except AppError as exc:
        return render(request, "auth.html", {"title": "Set up", "mode": "setup", "error": exc.message}, exc.status)
    return cookie(RedirectResponse("/", status_code=303), token=token)


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if needs_setup(db):
        return RedirectResponse("/setup", status_code=303)
    if user_from_token(db, request.cookies.get("crm_session")):
        return RedirectResponse("/", status_code=303)
    return render(request, "auth.html", {"title": "Log in", "mode": "login", "error": None})


@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user, token = login(db, username, password)
        del user
    except AppError as exc:
        return render(request, "auth.html", {"title": "Log in", "mode": "login", "error": exc.message}, exc.status)
    return cookie(RedirectResponse("/", status_code=303), token=token)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    end_session(db, request.cookies.get("crm_session"))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("crm_session", path="/")
    return response


@router.post("/shop")
def switch_shop(request: Request, shop_id: int = Form(...), user: User = Depends(web_user), db: Session = Depends(get_db)):
    shop = require_shop(db, user, shop_id)
    return cookie(RedirectResponse(safe_next(request), status_code=303), shop_id=shop.id)


@router.get("/")
def today(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Today", nav="today")
    if ctx["shop"] is not None:
        ctx["summary"] = present_today(db, ctx["shop"])
    return paint(request, "today.html", ctx)


@router.get("/inventory")
def inventory(request: Request, q: str = "", user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Stock", nav="stock", q=q)
    items = list_items(db, q)
    counts = stock_map(db, ctx["shop"].id) if ctx["shop"] is not None else {}
    ctx["rows"] = [(item, counts.get(item.id, 0)) for item in items]
    return paint(request, "inventory.html", ctx)


@router.get("/inventory/new")
def item_new(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="New item", nav="stock", form={})
    return paint(request, "item_form.html", ctx)


@router.post("/inventory/new")
def item_new_post(
    request: Request,
    name: str = Form(""),
    unit: str = Form("pcs"),
    sale_price: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        create_item(db, name, unit, parse_rupees(sale_price, "Sale price"))
    except AppError as exc:
        ctx = page(request, db, user, title="New item", nav="stock", form={"name": name, "unit": unit, "sale_price": sale_price})
        ctx["error"] = exc.message
        return paint(request, "item_form.html", ctx, exc.status)
    return RedirectResponse("/inventory", status_code=303)


@router.get("/inventory/{item_id}")
def item_page(item_id: int, request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Item", nav="stock")
    item = next((row for row in list_items(db) if row.id == item_id), None)
    if item is None:
        raise AppError("Item not found", 404)
    ctx["item"] = item
    ctx["quantity"] = stock_qty(db, ctx["shop"].id, item.id) if ctx["shop"] is not None else 0
    return paint(request, "item_detail.html", ctx)


@router.post("/inventory/{item_id}")
def item_update_post(
    item_id: int,
    request: Request,
    name: str = Form(""),
    unit: str = Form("pcs"),
    sale_price: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        update_item(db, item_id, name, unit, parse_rupees(sale_price, "Sale price"))
    except AppError as exc:
        ctx = page(request, db, user, title="Item", nav="stock")
        ctx["error"] = exc.message
        item = next((row for row in list_items(db) if row.id == item_id), None)
        ctx["item"] = item
        ctx["quantity"] = stock_qty(db, ctx["shop"].id, item_id) if ctx["shop"] is not None and item else 0
        return paint(request, "item_detail.html", ctx, exc.status)
    return RedirectResponse(f"/inventory/{item_id}", status_code=303)


@router.post("/inventory/{item_id}/adjust")
def item_adjust(
    item_id: int,
    request: Request,
    shop_id: int = Form(...),
    quantity_delta: str = Form(""),
    note: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        adjust_stock(db, shop.id, item_id, parse_whole(quantity_delta, "Quantity change"), note)
    except AppError as exc:
        return fail(f"/inventory/{item_id}", exc)
    return RedirectResponse(f"/inventory/{item_id}", status_code=303)


@router.get("/vendors")
def vendors_page(request: Request, q: str = "", user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Vendors", nav="more", q=q, vendors=list_vendors(db, q))
    return paint(request, "vendors.html", ctx)


@router.post("/vendors")
def vendors_post(
    request: Request,
    name: str = Form(""),
    phone: str = Form(""),
    note: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        create_vendor(db, name, phone, note)
    except AppError as exc:
        ctx = page(request, db, user, title="Vendors", nav="more", q="", vendors=list_vendors(db))
        ctx["error"] = exc.message
        return paint(request, "vendors.html", ctx, exc.status)
    return RedirectResponse("/vendors", status_code=303)


@router.get("/customers")
def customers_page(request: Request, q: str = "", user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Customers", nav="more", q=q)
    ctx["customers"] = list_customers(db, ctx["shop"].id, q) if ctx["shop"] is not None else []
    return paint(request, "customers.html", ctx)


@router.post("/customers")
def customers_post(
    request: Request,
    shop_id: int = Form(...),
    name: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        create_customer(db, shop.id, name, phone, address)
    except AppError as exc:
        ctx = page(request, db, user, title="Customers", nav="more", q="")
        ctx["customers"] = list_customers(db, ctx["shop"].id) if ctx["shop"] is not None else []
        ctx["error"] = exc.message
        return paint(request, "customers.html", ctx, exc.status)
    return RedirectResponse("/customers", status_code=303)


@router.get("/purchases")
def purchases_page(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Stock in", nav="more")
    ctx["purchases"] = present_purchase_list(db, ctx["shop"])
    return paint(request, "purchases.html", ctx)


def present_purchase_list(db: Session, shop) -> list[dict]:
    if shop is None:
        return []
    from app.present import present_purchases

    return present_purchases(db, list_purchases(db, shop.id))


@router.get("/purchases/new")
def purchase_new(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Receive stock", nav="more")
    ctx["vendors"] = list_vendors(db)
    ctx["items"] = list_items(db)
    ctx["stock"] = stock_map(db, ctx["shop"].id) if ctx["shop"] is not None else {}
    ctx["cost_mode"] = True
    ctx["price_label"] = "Cost"
    return paint(request, "purchase_form.html", ctx)


@router.post("/purchases/new")
def purchase_new_post(
    request: Request,
    shop_id: int = Form(...),
    vendor_id: int = Form(...),
    date: str = Form(""),
    note: str = Form(""),
    item_id: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price: list[str] = Form(default=[]),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        create_purchase(db, shop.id, vendor_id, date or today_ist(), parse_item_lines(item_id, qty, unit_price, "Cost"), note)
    except AppError as exc:
        ctx = page(request, db, user, title="Receive stock", nav="more")
        ctx.update(
            {
                "vendors": list_vendors(db),
                "items": list_items(db),
                "stock": stock_map(db, ctx["shop"].id) if ctx["shop"] is not None else {},
                "cost_mode": True,
                "price_label": "Cost",
                "error": exc.message,
            }
        )
        return paint(request, "purchase_form.html", ctx, exc.status)
    return RedirectResponse("/purchases", status_code=303)


@router.get("/purchases/{purchase_id}")
def purchase_page(purchase_id: int, request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Stock in", nav="more")
    if ctx["shop"] is None:
        raise AppError("Create a shop first")
    ctx["purchase"] = present_purchase(db, get_shop_purchase(db, ctx["shop"].id, purchase_id))
    return paint(request, "purchase_detail.html", ctx)


@router.post("/purchases/{purchase_id}/pay")
def purchase_pay(
    purchase_id: int,
    request: Request,
    shop_id: int = Form(...),
    amount: str = Form(""),
    method: str = Form("cash"),
    date: str = Form(""),
    note: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        record_ledger(db, shop.id, "vendor_payout", parse_rupees(amount, "Payment"), method, date or today_ist(), note, None, purchase_id)
    except AppError as exc:
        return fail(f"/purchases/{purchase_id}", exc)
    return RedirectResponse(f"/purchases/{purchase_id}", status_code=303)


@router.get("/sales/new")
def sale_new(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    return paint(request, "bill_form.html", bill_form_ctx(request, db, user, "counter"))


@router.post("/sales/new")
def sale_new_post(
    request: Request,
    shop_id: int = Form(...),
    customer_id: str = Form(""),
    date: str = Form(""),
    note: str = Form(""),
    paid_now: str = Form(""),
    method: str = Form("cash"),
    item_id: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price: list[str] = Form(default=[]),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    return save_bill(
        request, db, user, "counter", shop_id, customer_id, date, "", note, paid_now, method, item_id, qty, unit_price, [], []
    )


@router.get("/jobs/new")
def job_new(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    return paint(request, "bill_form.html", bill_form_ctx(request, db, user, "job"))


@router.post("/jobs/new")
def job_new_post(
    request: Request,
    shop_id: int = Form(...),
    customer_id: str = Form(""),
    date: str = Form(""),
    site_note: str = Form(""),
    note: str = Form(""),
    paid_now: str = Form(""),
    method: str = Form("cash"),
    item_id: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price: list[str] = Form(default=[]),
    service_desc: list[str] = Form(default=[]),
    service_amount: list[str] = Form(default=[]),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    return save_bill(
        request,
        db,
        user,
        "job",
        shop_id,
        customer_id,
        date,
        site_note,
        note,
        paid_now,
        method,
        item_id,
        qty,
        unit_price,
        service_desc,
        service_amount,
    )


def bill_form_ctx(request: Request, db: Session, user: User, kind: str) -> dict:
    ctx = page(request, db, user, title="Counter sale" if kind == "counter" else "Installation", nav="bills", kind=kind)
    ctx["customers"] = list_customers(db, ctx["shop"].id) if ctx["shop"] is not None else []
    ctx["items"] = list_items(db)
    ctx["stock"] = stock_map(db, ctx["shop"].id) if ctx["shop"] is not None else {}
    ctx["cost_mode"] = False
    ctx["price_label"] = "Rate"
    return ctx


def save_bill(
    request,
    db,
    user,
    kind,
    shop_id,
    customer_id,
    date,
    site_note,
    note,
    paid_now,
    method,
    item_id,
    qty,
    unit_price,
    service_desc,
    service_amount,
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        paid_text = (paid_now or "").strip()
        paid = 0 if not paid_text else parse_rupees(paid_text, "Payment")
        bill = create_bill(
            db,
            shop.id,
            kind,
            optional_int(customer_id),
            date or today_ist(),
            site_note,
            parse_item_lines(item_id, qty, unit_price, "Rate"),
            parse_services(service_desc, service_amount),
            paid,
            method,
            note,
        )
    except AppError as exc:
        ctx = bill_form_ctx(request, db, user, kind)
        ctx["error"] = exc.message
        return paint(request, "bill_form.html", ctx, exc.status)
    return RedirectResponse(f"/bills/{bill.id}", status_code=303)


@router.get("/bills")
def bills_page(request: Request, kind: str = "", user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Bills", nav="bills", kind=kind)
    if ctx["shop"] is None:
        ctx["bills"] = []
    else:
        from app.present import present_bills

        ctx["bills"] = present_bills(db, list_bills(db, ctx["shop"].id, kind))
    return paint(request, "bills.html", ctx)


@router.get("/bills/{bill_id}")
def bill_page(bill_id: int, request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Bill", nav="bills")
    if ctx["shop"] is None:
        raise AppError("Create a shop first")
    ctx["bill"] = present_bill(db, get_shop_bill(db, ctx["shop"].id, bill_id))
    return paint(request, "bill_detail.html", ctx)


@router.post("/bills/{bill_id}/pay")
def bill_pay(
    bill_id: int,
    request: Request,
    shop_id: int = Form(...),
    amount: str = Form(""),
    method: str = Form("cash"),
    date: str = Form(""),
    note: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        record_ledger(db, shop.id, "customer_receipt", parse_rupees(amount, "Payment"), method, date or today_ist(), note, bill_id, None)
    except AppError as exc:
        return fail(f"/bills/{bill_id}", exc)
    return RedirectResponse(f"/bills/{bill_id}", status_code=303)


@router.get("/wallet")
def wallet_page(request: Request, date: str = "", user: User = Depends(web_user), db: Session = Depends(get_db)):
    ctx = page(request, db, user, title="Cash", nav="cash")
    chosen = today_ist()
    if date:
        try:
            chosen = parse_date(date)
        except AppError as exc:
            ctx["error"] = exc.message
    ctx["date"] = chosen
    ctx["prev"] = shift_date(chosen, -1)
    ctx["next"] = shift_date(chosen, 1)
    ctx["wallet"] = present_wallet(db, ctx["shop"].id, chosen) if ctx["shop"] is not None else None
    return paint(request, "wallet.html", ctx)


@router.get("/wallet/new")
def wallet_new(
    request: Request,
    kind: str = "expense",
    bill_id: int | None = None,
    purchase_id: int | None = None,
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    ctx = cash_form_ctx(request, db, user, kind, bill_id, purchase_id)
    return paint(request, "ledger_form.html", ctx)


@router.post("/wallet/new")
def wallet_new_post(
    request: Request,
    shop_id: int = Form(...),
    category: str = Form("expense"),
    amount: str = Form(""),
    method: str = Form("cash"),
    date: str = Form(""),
    note: str = Form(""),
    bill_id: str = Form(""),
    purchase_id: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = posted_shop(request, db, user, shop_id)
        record_ledger(
            db,
            shop.id,
            category,
            parse_rupees(amount, "Amount"),
            method,
            date or today_ist(),
            note,
            optional_int(bill_id),
            optional_int(purchase_id),
        )
    except AppError as exc:
        ctx = cash_form_ctx(request, db, user, category, optional_int(bill_id) if bill_id.isdigit() else None, optional_int(purchase_id) if purchase_id.isdigit() else None)
        ctx["error"] = exc.message
        return paint(request, "ledger_form.html", ctx, exc.status)
    return RedirectResponse("/wallet", status_code=303)


def cash_form_ctx(request, db, user, kind, bill_id, purchase_id) -> dict:
    ctx = page(request, db, user, title="Money in / out", nav="cash", kind=kind if kind in {"customer_receipt", "vendor_payout", "expense", "opening"} else "expense")
    shop = ctx["shop"]
    ctx["bills_due"] = unpaid_bills(db, shop.id) if shop is not None else []
    ctx["purchases_due"] = unpaid_purchases(db, shop.id) if shop is not None else []
    ctx["bill_id"] = bill_id
    ctx["purchase_id"] = purchase_id
    ctx["amount"] = ""
    if shop is not None and bill_id:
        match = next((row for row in ctx["bills_due"] if row["id"] == bill_id), None)
        if match:
            ctx["amount"] = paise_to_input(match["balance_paise"])
            ctx["kind"] = "customer_receipt"
    if shop is not None and purchase_id:
        match = next((row for row in ctx["purchases_due"] if row["id"] == purchase_id), None)
        if match:
            ctx["amount"] = paise_to_input(match["balance_paise"])
            ctx["kind"] = "vendor_payout"
    return ctx


@router.get("/more")
def more_page(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    return paint(request, "more.html", page(request, db, user, title="More", nav="more"))


@router.get("/settings")
def settings_page(request: Request, user: User = Depends(web_user), db: Session = Depends(get_db)):
    if user.role != "owner":
        raise AppError("Only the owner can do that", 403)
    ctx = page(request, db, user, title="Settings", nav="more")
    people = []
    for row in list_users(db):
        people.append({"user": row, "shop_ids": shop_ids_for(db, row)})
    ctx["people"] = people
    return paint(request, "settings.html", ctx)


@router.post("/settings/shops")
def settings_shop(
    request: Request,
    name: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        shop = create_shop(db, user, name, address, phone)
    except AppError as exc:
        return fail("/settings", exc)
    return cookie(RedirectResponse("/", status_code=303), shop_id=shop.id)


@router.post("/settings/users")
def settings_user(
    request: Request,
    name: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    shop_ids: list[int] = Form(default=[]),
    user: User = Depends(web_user),
    db: Session = Depends(get_db),
):
    try:
        create_staff(db, user, name, username, password, shop_ids)
    except AppError as exc:
        return fail("/settings", exc)
    return RedirectResponse("/settings?notice=Staff added", status_code=303)


def fail(path: str, exc: AppError) -> RedirectResponse:
    return RedirectResponse(f"{path}?error={quote(exc.message)}", status_code=303)
