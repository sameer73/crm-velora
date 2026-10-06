from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import (
    end_session,
    needs_setup,
    require_owner,
    require_shop,
    shop_ids_for,
    shops_for,
    user_from_token,
)
from app.db import get_db
from app.models import Shop, User
from app.present import (
    present_bill,
    present_bills,
    present_entry,
    present_item,
    present_purchase,
    present_purchases,
    present_today,
    present_wallet,
    unpaid_bills,
    unpaid_purchases,
)
from app.schemas import (
    AdjustIn,
    AuthOut,
    BillIn,
    BillOut,
    CustomerIn,
    CustomerOut,
    ItemIn,
    ItemOut,
    LedgerIn,
    LedgerOut,
    LoginIn,
    PurchaseIn,
    PurchaseOut,
    SetupIn,
    ShopIn,
    ShopOut,
    StaffIn,
    StockOut,
    TodayOut,
    UserOut,
    VendorIn,
    VendorOut,
    WalletOut,
)
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
    update_item,
)

router = APIRouter(prefix="/api")


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("crm_session")
    user = user_from_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def user_payload(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "role": user.role,
        "shop_ids": shop_ids_for(db, user),
    }


def shop_or_404(shop_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Shop:
    return require_shop(db, user, shop_id)


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/auth/status")
def auth_status(db: Session = Depends(get_db)) -> dict:
    return {"needs_setup": needs_setup(db)}


@router.post("/auth/setup", response_model=AuthOut)
def auth_setup(body: SetupIn, db: Session = Depends(get_db)) -> dict:
    user, token = create_owner(db, body.name, body.username, body.password)
    return {"token": token, "user": user_payload(db, user)}


@router.post("/auth/login", response_model=AuthOut)
def auth_login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    user, token = login(db, body.username, body.password)
    return {"token": token, "user": user_payload(db, user)}


@router.post("/auth/logout")
def auth_logout(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("crm_session")
    end_session(db, token)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def auth_me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return user_payload(db, user)


@router.get("/shops", response_model=list[ShopOut])
def shops(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Shop]:
    return shops_for(db, user)


@router.post("/shops", response_model=ShopOut)
def shop_create(body: ShopIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Shop:
    return create_shop(db, user, body.name, body.address, body.phone)


@router.get("/users", response_model=list[UserOut])
def users(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_owner(user)
    return [user_payload(db, row) for row in list_users(db)]


@router.post("/users", response_model=UserOut)
def user_create(body: StaffIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    staff = create_staff(db, user, body.name, body.username, body.password, body.shop_ids)
    return user_payload(db, staff)


@router.get("/items", response_model=list[ItemOut])
def items(q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    del user
    return [present_item(item) for item in list_items(db, q)]


@router.post("/items", response_model=ItemOut)
def item_create(body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    del user
    return present_item(create_item(db, body.name, body.unit, body.sale_price_paise))


@router.patch("/items/{item_id}", response_model=ItemOut)
def item_update(
    item_id: int,
    body: ItemIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    del user
    return present_item(update_item(db, item_id, body.name, body.unit, body.sale_price_paise))


@router.get("/vendors", response_model=list[VendorOut])
def vendors(q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    del user
    return list_vendors(db, q)


@router.post("/vendors", response_model=VendorOut)
def vendor_create(body: VendorIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    del user
    return create_vendor(db, body.name, body.phone, body.note)


@router.get("/shops/{shop_id}/stock", response_model=list[StockOut])
def stock(q: str = "", shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> list[dict]:
    counts = stock_map(db, shop.id)
    return [
        {**present_item(item), "item_id": item.id, "quantity": counts.get(item.id, 0)}
        for item in list_items(db, q)
    ]


@router.post("/shops/{shop_id}/stock/adjust", response_model=StockOut)
def stock_adjust(body: AdjustIn, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    adjust_stock(db, shop.id, body.item_id, body.quantity_delta, body.note)
    item = next(row for row in list_items(db) if row.id == body.item_id)
    return {**present_item(item), "item_id": item.id, "quantity": stock_map(db, shop.id).get(item.id, 0)}


@router.get("/shops/{shop_id}/customers", response_model=list[CustomerOut])
def customers(q: str = "", shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)):
    return list_customers(db, shop.id, q)


@router.post("/shops/{shop_id}/customers", response_model=CustomerOut)
def customer_create(body: CustomerIn, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)):
    return create_customer(db, shop.id, body.name, body.phone, body.address)


@router.get("/shops/{shop_id}/purchases", response_model=list[PurchaseOut])
def purchases(shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> list[dict]:
    return present_purchases(db, list_purchases(db, shop.id))


@router.post("/shops/{shop_id}/purchases", response_model=PurchaseOut)
def purchase_create(body: PurchaseIn, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    purchase = create_purchase(
        db,
        shop.id,
        body.vendor_id,
        body.date,
        [ItemLine(line.item_id, line.quantity, line.unit_price_paise) for line in body.lines],
        body.note,
    )
    return present_purchase(db, purchase)


@router.get("/shops/{shop_id}/purchases/{purchase_id}", response_model=PurchaseOut)
def purchase_detail(purchase_id: int, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    return present_purchase(db, get_shop_purchase(db, shop.id, purchase_id))


@router.get("/shops/{shop_id}/bills", response_model=list[BillOut])
def bills(kind: str = "", shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> list[dict]:
    return present_bills(db, list_bills(db, shop.id, kind))


@router.post("/shops/{shop_id}/bills", response_model=BillOut)
def bill_create(body: BillIn, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    bill = create_bill(
        db,
        shop.id,
        body.kind,
        body.customer_id,
        body.date,
        body.site_note,
        [ItemLine(line.item_id, line.quantity, line.unit_price_paise) for line in body.lines],
        [ServiceLine(line.description, line.amount_paise) for line in body.services],
        body.paid_now_paise,
        body.method,
        body.note,
    )
    return present_bill(db, bill)


@router.get("/shops/{shop_id}/bills/{bill_id}", response_model=BillOut)
def bill_detail(bill_id: int, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    return present_bill(db, get_shop_bill(db, shop.id, bill_id))


@router.get("/shops/{shop_id}/today", response_model=TodayOut)
def today(shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    return present_today(db, shop)


@router.get("/shops/{shop_id}/wallet", response_model=WalletOut)
def wallet(date: str, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    return present_wallet(db, shop.id, date)


@router.post("/shops/{shop_id}/wallet", response_model=LedgerOut)
def wallet_add(body: LedgerIn, shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    entry = record_ledger(
        db,
        shop.id,
        body.category,
        body.amount_paise,
        body.method,
        body.date,
        body.note,
        body.bill_id,
        body.purchase_id,
    )
    return present_entry(entry)


@router.get("/shops/{shop_id}/dues")
def dues(shop: Shop = Depends(shop_or_404), db: Session = Depends(get_db)) -> dict:
    return {"bills": unpaid_bills(db, shop.id), "purchases": unpaid_purchases(db, shop.id)}
