import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.money import today_ist


@pytest.fixture
def client(tmp_path):
    application = create_app(str(tmp_path / "crm.sqlite"))
    with TestClient(application) as test_client:
        yield test_client


def auth(client, username="owner", password="secret1"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_daily_loop_and_shop_isolation(client):
    setup = client.post("/api/auth/setup", json={"name": "Brother", "username": "Owner", "password": "secret1"})
    assert setup.status_code == 200, setup.text
    assert setup.json()["user"]["role"] == "owner"
    headers = {"Authorization": f"Bearer {setup.json()['token']}"}
    again = client.post("/api/auth/setup", json={"name": "X", "username": "other", "password": "secret1"})
    assert again.status_code == 409

    main = client.post("/api/shops", headers=headers, json={"name": "Main Road", "address": "12 Market", "phone": "900"}).json()
    other = client.post("/api/shops", headers=headers, json={"name": "Lake Side"}).json()
    vendor = client.post("/api/vendors", headers=headers, json={"name": "Aqua Supply", "phone": "111"}).json()
    item = client.post(
        "/api/items",
        headers=headers,
        json={"name": "Filter set", "unit": "pcs", "sale_price_paise": 700000},
    ).json()
    day = today_ist()

    opening = client.post(
        f"/api/shops/{main['id']}/wallet",
        headers=headers,
        json={"category": "opening", "amount_paise": 50000, "method": "cash", "date": day, "note": "drawer"},
    )
    assert opening.status_code == 200, opening.text

    purchase = client.post(
        f"/api/shops/{main['id']}/purchases",
        headers=headers,
        json={
            "vendor_id": vendor["id"],
            "date": day,
            "note": "morning stock",
            "lines": [{"item_id": item["id"], "quantity": 1, "unit_price_paise": 700000}],
        },
    )
    assert purchase.status_code == 200, purchase.text
    purchase_id = purchase.json()["id"]
    assert purchase.json()["balance_paise"] == 700000

    stock = client.get(f"/api/shops/{main['id']}/stock", headers=headers).json()
    assert stock[0]["quantity"] == 1
    other_stock = client.get(f"/api/shops/{other['id']}/stock", headers=headers).json()
    assert other_stock[0]["quantity"] == 0

    blocked = client.post(
        f"/api/shops/{main['id']}/bills",
        headers=headers,
        json={
            "kind": "counter",
            "date": day,
            "lines": [{"item_id": item["id"], "quantity": 2, "unit_price_paise": 700000}],
            "paid_now_paise": 0,
        },
    )
    assert blocked.status_code == 400
    assert "Not enough stock" in blocked.json()["detail"]
    assert client.get(f"/api/shops/{main['id']}/stock", headers=headers).json()[0]["quantity"] == 1

    customer = client.post(
        f"/api/shops/{main['id']}/customers",
        headers=headers,
        json={"name": "Ravi", "phone": "98", "address": "Kitchen, 2nd floor"},
    ).json()
    job = client.post(
        f"/api/shops/{main['id']}/bills",
        headers=headers,
        json={
            "kind": "job",
            "customer_id": customer["id"],
            "date": day,
            "site_note": "Kitchen",
            "lines": [{"item_id": item["id"], "quantity": 1, "unit_price_paise": 700000}],
            "services": [{"description": "Installation", "amount_paise": 300000}],
            "paid_now_paise": 0,
        },
    )
    assert job.status_code == 200, job.text
    bill = job.json()
    assert bill["total_paise"] == 1000000
    assert bill["balance_paise"] == 1000000
    assert client.get(f"/api/shops/{main['id']}/stock", headers=headers).json()[0]["quantity"] == 0

    partial = client.post(
        f"/api/shops/{main['id']}/wallet",
        headers=headers,
        json={
            "category": "customer_receipt",
            "amount_paise": 400000,
            "method": "upi",
            "date": day,
            "bill_id": bill["id"],
        },
    )
    assert partial.status_code == 200, partial.text
    too_much = client.post(
        f"/api/shops/{main['id']}/wallet",
        headers=headers,
        json={
            "category": "customer_receipt",
            "amount_paise": 700000,
            "method": "cash",
            "date": day,
            "bill_id": bill["id"],
        },
    )
    assert too_much.status_code == 400
    rest = client.post(
        f"/api/shops/{main['id']}/wallet",
        headers=headers,
        json={
            "category": "customer_receipt",
            "amount_paise": 600000,
            "method": "cash",
            "date": day,
            "bill_id": bill["id"],
        },
    )
    assert rest.status_code == 200, rest.text

    payout = client.post(
        f"/api/shops/{main['id']}/wallet",
        headers=headers,
        json={
            "category": "vendor_payout",
            "amount_paise": 700000,
            "method": "cash",
            "date": day,
            "purchase_id": purchase_id,
            "note": "from today's collection",
        },
    )
    assert payout.status_code == 200, payout.text
    expense = client.post(
        f"/api/shops/{main['id']}/wallet",
        headers=headers,
        json={"category": "expense", "amount_paise": 20000, "method": "cash", "date": day, "note": "petrol"},
    )
    assert expense.status_code == 200, expense.text

    today = client.get(f"/api/shops/{main['id']}/today", headers=headers).json()
    # opening 500 + customer 10000 - vendor 7000 - petrol 200 = 3300
    assert today["opening_paise"] == 0
    assert today["in_paise"] == 50000 + 1000000
    assert today["out_paise"] == 700000 + 20000
    assert today["closing_paise"] == 330000
    assert today["unpaid_bills"] == []
    assert today["unpaid_purchases"] == []
    assert today["has_opening"] is True

    other_today = client.get(f"/api/shops/{other['id']}/today", headers=headers).json()
    assert other_today["closing_paise"] == 0

    staff = client.post(
        "/api/users",
        headers=headers,
        json={"name": "Helper", "username": "helper", "password": "secret2", "shop_ids": [other["id"]]},
    )
    assert staff.status_code == 200, staff.text
    staff_headers = auth(client, "helper", "secret2")
    denied = client.get(f"/api/shops/{main['id']}/wallet", headers=staff_headers, params={"date": day})
    assert denied.status_code == 403
    allowed = client.get(f"/api/shops/{other['id']}/today", headers=staff_headers)
    assert allowed.status_code == 200
    assert client.get("/api/shops", headers=staff_headers).json() == [
        {"id": other["id"], "name": "Lake Side", "address": "", "phone": ""}
    ]


def test_adjustment_cannot_go_negative(client):
    client.post("/api/auth/setup", json={"name": "A", "username": "owner", "password": "secret1"})
    headers = auth(client)
    shop = client.post("/api/shops", headers=headers, json={"name": "Shop"}).json()
    item = client.post("/api/items", headers=headers, json={"name": "Tap", "sale_price_paise": 10000}).json()
    bad = client.post(
        f"/api/shops/{shop['id']}/stock/adjust",
        headers=headers,
        json={"item_id": item["id"], "quantity_delta": -1, "note": "missing"},
    )
    assert bad.status_code == 400
    ok = client.post(
        f"/api/shops/{shop['id']}/stock/adjust",
        headers=headers,
        json={"item_id": item["id"], "quantity_delta": 3, "note": "counted"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["quantity"] == 3


def test_web_counter_sale(client):
    client.post("/setup", data={"name": "Brother", "username": "owner", "password": "secret1"}, follow_redirects=False)
    page = client.get("/")
    assert page.status_code == 200
    assert "Create your first shop" in page.text
    client.post("/settings/shops", data={"name": "Main Road", "address": "", "phone": ""})
    today = client.get("/")
    assert "Cash in hand" in today.text
    client.post("/vendors", data={"name": "Aqua Supply", "phone": "", "note": ""})
    client.post("/inventory/new", data={"name": "Filter set", "unit": "pcs", "sale_price": "7000"})
    day = today_ist()
    stock_in = client.post(
        "/purchases/new",
        data={
            "shop_id": "1",
            "vendor_id": "1",
            "date": day,
            "note": "",
            "item_id": "1",
            "qty": "1",
            "unit_price": "7000",
        },
        follow_redirects=False,
    )
    assert stock_in.status_code == 303, stock_in.text
    sale = client.post(
        "/sales/new",
        data={
            "shop_id": "1",
            "customer_id": "",
            "date": day,
            "note": "",
            "paid_now": "7000",
            "method": "cash",
            "item_id": "1",
            "qty": "1",
            "unit_price": "7000",
        },
    )
    assert sale.status_code == 200, sale.text
    assert "₹7,000.00" in sale.text
    home = client.get("/")
    assert "₹7,000.00" in home.text
