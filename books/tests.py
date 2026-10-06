from django.contrib.auth.models import User
from django.test import Client, TestCase

from books.models import Item, LedgerEntry, Profile
from books.money import today_ist
from books.services import (
    ItemLine,
    ServiceLine,
    create_bill,
    create_customer,
    create_item,
    create_owner,
    create_purchase,
    create_shop,
    create_staff,
    create_vendor,
    record_ledger,
    stock_qty,
    wallet_totals,
)
from books.errors import AppError
from books.present import due_bills


class ShopLoopTests(TestCase):
    def test_daily_loop_and_optional_qr(self):
        user, token = create_owner("Owner", "owner", "secret1")
        self.assertTrue(user.is_superuser)
        shop = create_shop(user, "Lake Side", "", "")
        other = create_shop(user, "Hill Shop", "", "")
        plain = create_item("Candle", "pcs", 5000, False)
        self.assertIsNone(plain.code)
        self.assertFalse(plain.qr_image)
        tagged = create_item("RO filter", "pcs", 800000, True)
        tagged.refresh_from_db()
        self.assertEqual(tagged.code, f"VT-{tagged.pk:05d}")
        self.assertTrue(tagged.qr_image)

        vendor = create_vendor("Aqua Supply", "", "")
        day = today_ist().isoformat()
        create_purchase(shop.id, vendor.id, day, [ItemLine(tagged.id, 2, 700000)], "")
        self.assertEqual(stock_qty(shop.id, tagged.id), 2)
        self.assertEqual(stock_qty(other.id, tagged.id), 0)

        customer = create_customer(shop.id, "Ravi", "", "Kitchen")
        with self.assertRaises(AppError):
            create_bill(shop.id, "job", customer.id, day, "", [ItemLine(tagged.id, 5, 700000)], [], 0, "cash")

        bill = create_bill(
            shop.id,
            "job",
            customer.id,
            day,
            "Kitchen",
            [ItemLine(tagged.id, 1, 700000)],
            [ServiceLine("Installation", 300000)],
            0,
            "cash",
        )
        self.assertEqual(bill.total_paise, 1000000)
        self.assertEqual(stock_qty(shop.id, tagged.id), 1)
        record_ledger(shop.id, "opening", 50000, "cash", day, "")
        record_ledger(shop.id, "customer_receipt", 1000000, "cash", day, "", bill.id, None)
        purchase = shop.purchases.get()
        record_ledger(shop.id, "vendor_payout", 700000, "cash", day, "", None, purchase.id)
        record_ledger(shop.id, "expense", 20000, "cash", day, "Tea")
        totals = wallet_totals(shop.id, day)
        self.assertEqual(totals["in_paise"], 1050000)
        self.assertEqual(totals["out_paise"], 720000)
        self.assertEqual(totals["closing_paise"], 330000)

        staff = create_staff(user, "Mina", "mina", "secret1", [other.id])
        with self.assertRaises(AppError):
            from books.access import require_shop

            require_shop(staff, shop.id)

        client = Client()
        status = client.get("/api/auth/status")
        self.assertFalse(status.json()["needs_setup"])
        logged = client.post("/api/auth/login", {"username": "owner", "password": "secret1"}, content_type="application/json")
        body = logged.json()
        self.assertEqual(body["user"]["role"], "owner")
        today = client.get(f"/api/shops/{shop.id}/today", HTTP_AUTHORIZATION=f"Bearer {body['token']}")
        self.assertEqual(today.status_code, 200)
        self.assertEqual(today.json()["closing_paise"], 330000)
        self.assertEqual(token[:1], token[:1])

    def test_web_generates_qr_only_when_checked(self):
        user, _token = create_owner("Owner", "owner", "secret1")
        create_shop(user, "Lake Side", "", "")
        client = Client()
        client.force_login(user)
        skipped = client.post("/inventory/new", {"name": "Tap", "unit": "pcs", "sale_price": "150"})
        self.assertEqual(skipped.status_code, 302)
        tap = Item.objects.get(name="Tap")
        self.assertFalse(tap.code)
        made = client.post("/inventory/new", {"name": "Candle", "unit": "pcs", "sale_price": "40", "generate_code": "on"})
        self.assertEqual(made.status_code, 302)
        candle = Item.objects.get(name="Candle")
        self.assertTrue(candle.code)
        page = client.get(f"/inventory/{candle.id}")
        self.assertContains(page, "Verito Tech")
        self.assertContains(page, candle.code)
        self.assertContains(page, "Generate QR code")
        self.assertEqual(User.objects.count(), 1)

    def test_login_without_profile_opens_today(self):
        user = User.objects.create_superuser(username="sam", password="secret1")
        Profile.objects.filter(user=user).delete()
        client = Client()
        client.force_login(user)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your first shop")
        user.refresh_from_db()
        self.assertEqual(user.profile.role, "owner")

    def test_part_payment_stays_on_today(self):
        user, _token = create_owner("Owner", "owner", "secret1")
        shop = create_shop(user, "Lake Side", "", "")
        item = create_item("RO filter", "pcs", 800000, False)
        vendor = create_vendor("Aqua", "", "")
        day = today_ist().isoformat()
        create_purchase(shop.id, vendor.id, day, [ItemLine(item.id, 1, 500000)], "")
        bill = create_bill(shop.id, "counter", None, day, "", [ItemLine(item.id, 1, 800000)], [], 400000, "cash", "")
        dues = due_bills(shop.id)
        self.assertEqual(len(dues), 1)
        self.assertEqual(dues[0]["title"], "Walk-in")
        self.assertEqual(dues[0]["balance_paise"], 400000)
        client = Client()
        client.force_login(user)
        session = client.session
        session["shop_id"] = shop.id
        session.save()
        today = client.get("/")
        self.assertContains(today, "Due ₹4,000.00")
        self.assertContains(today, "paid ₹4,000.00 of ₹8,000.00")
        page = client.get(f"/bills/{bill.id}")
        self.assertContains(page, "Still to pay")
        self.assertContains(page, "₹4,000.00")

    def test_vendor_payment_without_stock_receipt(self):
        user, _token = create_owner("Owner", "owner", "secret1")
        shop = create_shop(user, "Lake Side", "", "")
        vendor = create_vendor("ds vendor", "", "")
        client = Client()
        client.force_login(user)
        session = client.session
        session["shop_id"] = shop.id
        session.save()
        form = client.get("/wallet/new?kind=vendor_payout")
        self.assertContains(form, "ds vendor")
        saved = client.post(
            "/wallet/new",
            {
                "shop_id": shop.id,
                "category": "vendor_payout",
                "vendor_id": vendor.id,
                "amount": "1500",
                "method": "cash",
                "date": today_ist().isoformat(),
                "note": "",
            },
        )
        self.assertEqual(saved.status_code, 302)
        entry = LedgerEntry.objects.get(category="vendor_payout")
        self.assertEqual(entry.amount_paise, 150000)
        self.assertEqual(entry.vendor_id, vendor.id)
        self.assertIsNone(entry.purchase_id)
