import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from books.access import end_token, needs_setup, require_owner, require_shop, shops_for, user_from_token
from books.errors import AppError
from books.models import Bill, Item, Purchase
from books.money import today_ist
from books.present import (
    bill_payload,
    bills_payload,
    entry_payload,
    item_payload,
    purchase_payload,
    purchases_payload,
    today_payload,
    user_payload,
    wallet_payload,
)
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
    list_customers,
    list_items,
    list_vendors,
    login,
    record_ledger,
    stock_map,
    update_item,
)


def _json(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        raise AppError("Send JSON") from None
    return data if isinstance(data, dict) else {}


def api(view):
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except AppError as exc:
            return JsonResponse({"detail": exc.message}, status=exc.status)

    wrapper.__name__ = view.__name__
    return csrf_exempt(wrapper)


def authed(view):
    @api
    def wrapper(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.split(" ", 1)[1].strip() if header.lower().startswith("bearer ") else request.COOKIES.get("crm_session")
        user = user_from_token(token)
        if user is None:
            return JsonResponse({"detail": "Login required"}, status=401)
        request.api_user = user
        return view(request, *args, **kwargs)

    return wrapper


def shop_from(request, shop_id):
    return require_shop(request.api_user, shop_id)


@api
def health(_request):
    return JsonResponse({"ok": True})


@api
def auth_status(_request):
    return JsonResponse({"needs_setup": needs_setup()})


@api
def auth_setup(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST only"}, status=405)
    data = _json(request)
    user, token = create_owner(data.get("name", ""), data.get("username", ""), data.get("password", ""))
    return JsonResponse({"token": token, "user": user_payload(user)})


@api
def auth_login(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST only"}, status=405)
    data = _json(request)
    user, token = login(data.get("username", ""), data.get("password", ""))
    return JsonResponse({"token": token, "user": user_payload(user)})


@api
def auth_logout(request):
    header = request.headers.get("Authorization", "")
    token = header.split(" ", 1)[1].strip() if header.lower().startswith("bearer ") else request.COOKIES.get("crm_session")
    end_token(token)
    return JsonResponse({"ok": True})


@authed
def auth_me(request):
    return JsonResponse(user_payload(request.api_user))


@authed
def shops(request):
    if request.method == "POST":
        data = _json(request)
        shop = create_shop(request.api_user, data.get("name", ""), data.get("address", ""), data.get("phone", ""))
        return JsonResponse({"id": shop.id, "name": shop.name, "address": shop.address, "phone": shop.phone})
    rows = [{"id": shop.id, "name": shop.name, "address": shop.address, "phone": shop.phone} for shop in shops_for(request.api_user)]
    return JsonResponse(rows, safe=False)


@authed
def users(request):
    require_owner(request.api_user)
    if request.method == "POST":
        data = _json(request)
        staff = create_staff(
            request.api_user,
            data.get("name", ""),
            data.get("username", ""),
            data.get("password", ""),
            data.get("shop_ids") or [],
        )
        return JsonResponse(user_payload(staff))
    from django.contrib.auth.models import User

    return JsonResponse([user_payload(user) for user in User.objects.select_related("profile").order_by("profile__name")], safe=False)


@authed
def items(request):
    if request.method == "POST":
        data = _json(request)
        item = create_item(data.get("name", ""), data.get("unit") or "pcs", int(data.get("sale_price_paise") or 0), bool(data.get("generate_code")))
        return JsonResponse(item_payload(item))
    return JsonResponse([item_payload(item) for item in list_items(request.GET.get("q", ""))], safe=False)


@authed
def item_update(request, item_id):
    data = _json(request)
    item = update_item(item_id, data.get("name", ""), data.get("unit") or "pcs", int(data.get("sale_price_paise") or 0), bool(data.get("generate_code")))
    return JsonResponse(item_payload(item))


@authed
def vendors(request):
    if request.method == "POST":
        data = _json(request)
        vendor = create_vendor(data.get("name", ""), data.get("phone", ""), data.get("note", ""))
        return JsonResponse({"id": vendor.id, "name": vendor.name, "phone": vendor.phone, "note": vendor.note})
    rows = [{"id": row.id, "name": row.name, "phone": row.phone, "note": row.note} for row in list_vendors(request.GET.get("q", ""))]
    return JsonResponse(rows, safe=False)


@authed
def stock(request, shop_id):
    shop = shop_from(request, shop_id)
    counts = stock_map(shop.id)
    rows = []
    for item in list_items(request.GET.get("q", "")):
        payload = item_payload(item)
        payload["item_id"] = item.id
        payload["quantity"] = counts.get(item.id, 0)
        rows.append(payload)
    return JsonResponse(rows, safe=False)


@authed
def stock_adjust(request, shop_id):
    shop = shop_from(request, shop_id)
    data = _json(request)
    adjust_stock(shop.id, int(data["item_id"]), int(data["quantity_delta"]), data.get("note", ""))
    item = Item.objects.get(pk=data["item_id"])
    payload = item_payload(item)
    payload["item_id"] = item.id
    payload["quantity"] = stock_map(shop.id).get(item.id, 0)
    return JsonResponse(payload)


@authed
def customers(request, shop_id):
    shop = shop_from(request, shop_id)
    if request.method == "POST":
        data = _json(request)
        customer = create_customer(shop.id, data.get("name", ""), data.get("phone", ""), data.get("address", ""))
        return JsonResponse({"id": customer.id, "name": customer.name, "phone": customer.phone, "address": customer.address})
    rows = [
        {"id": row.id, "name": row.name, "phone": row.phone, "address": row.address}
        for row in list_customers(shop.id, request.GET.get("q", ""))
    ]
    return JsonResponse(rows, safe=False)


@authed
def purchases(request, shop_id):
    shop = shop_from(request, shop_id)
    if request.method == "POST":
        data = _json(request)
        lines = [ItemLine(int(line["item_id"]), int(line["quantity"]), int(line["unit_price_paise"])) for line in data.get("lines") or []]
        purchase = create_purchase(shop.id, int(data["vendor_id"]), data.get("date") or today_ist().isoformat(), lines, data.get("note", ""))
        return JsonResponse(purchase_payload(Purchase.objects.select_related("vendor").get(pk=purchase.id)))
    return JsonResponse(purchases_payload(Purchase.objects.filter(shop=shop).select_related("vendor")), safe=False)


@authed
def purchase_detail(request, shop_id, purchase_id):
    shop = shop_from(request, shop_id)
    return JsonResponse(purchase_payload(get_shop_purchase(shop.id, purchase_id)))


@authed
def bills(request, shop_id):
    shop = shop_from(request, shop_id)
    if request.method == "POST":
        data = _json(request)
        lines = [ItemLine(int(line["item_id"]), int(line["quantity"]), int(line["unit_price_paise"])) for line in data.get("lines") or []]
        services = [ServiceLine(line.get("description", ""), int(line["amount_paise"])) for line in data.get("services") or []]
        bill = create_bill(
            shop.id,
            data.get("kind", ""),
            data.get("customer_id"),
            data.get("date") or today_ist().isoformat(),
            data.get("site_note", ""),
            lines,
            services,
            int(data.get("paid_now_paise") or 0),
            data.get("method") or "cash",
            data.get("note", ""),
        )
        return JsonResponse(bill_payload(Bill.objects.select_related("customer").get(pk=bill.id)))
    kind = request.GET.get("kind", "")
    rows = Bill.objects.filter(shop=shop).select_related("customer")
    if kind in {"counter", "job"}:
        rows = rows.filter(kind=kind)
    return JsonResponse(bills_payload(rows), safe=False)


@authed
def bill_detail(request, shop_id, bill_id):
    shop = shop_from(request, shop_id)
    return JsonResponse(bill_payload(get_shop_bill(shop.id, bill_id)))


@authed
def today(request, shop_id):
    shop = shop_from(request, shop_id)
    return JsonResponse(today_payload(shop))


@authed
def wallet(request, shop_id):
    shop = shop_from(request, shop_id)
    if request.method == "POST":
        data = _json(request)
        entry = record_ledger(
            shop.id,
            data.get("category", ""),
            int(data.get("amount_paise") or 0),
            data.get("method") or "cash",
            data.get("date") or today_ist().isoformat(),
            data.get("note", ""),
            data.get("bill_id"),
            data.get("purchase_id"),
            data.get("vendor_id"),
        )
        return JsonResponse(entry_payload(entry))
    return JsonResponse(wallet_payload(shop.id, request.GET.get("date") or today_ist().isoformat()))
