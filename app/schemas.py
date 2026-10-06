from pydantic import BaseModel, Field


class SetupIn(BaseModel):
    name: str
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    username: str
    role: str
    shop_ids: list[int]


class AuthOut(BaseModel):
    token: str
    user: UserOut


class ShopIn(BaseModel):
    name: str
    address: str = ""
    phone: str = ""


class ShopOut(BaseModel):
    id: int
    name: str
    address: str
    phone: str


class ItemIn(BaseModel):
    name: str
    unit: str = "pcs"
    sale_price_paise: int = Field(ge=0)


class ItemOut(BaseModel):
    id: int
    name: str
    unit: str
    sale_price_paise: int
    last_cost_paise: int | None


class StockOut(BaseModel):
    item_id: int
    name: str
    unit: str
    sale_price_paise: int
    last_cost_paise: int | None
    quantity: int


class AdjustIn(BaseModel):
    item_id: int
    quantity_delta: int
    note: str


class VendorIn(BaseModel):
    name: str
    phone: str = ""
    note: str = ""


class VendorOut(BaseModel):
    id: int
    name: str
    phone: str
    note: str


class CustomerIn(BaseModel):
    name: str
    phone: str = ""
    address: str = ""


class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    address: str


class ItemLineIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)


class ServiceIn(BaseModel):
    description: str
    amount_paise: int = Field(gt=0)


class PurchaseIn(BaseModel):
    vendor_id: int
    date: str
    note: str = ""
    lines: list[ItemLineIn]


class PurchaseLineOut(BaseModel):
    id: int
    item_id: int
    name: str
    quantity: int
    unit_cost_paise: int
    line_total_paise: int


class PurchaseOut(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str
    date: str
    note: str
    total_paise: int
    paid_paise: int
    balance_paise: int
    lines: list[PurchaseLineOut]


class BillIn(BaseModel):
    kind: str
    customer_id: int | None = None
    date: str
    site_note: str = ""
    lines: list[ItemLineIn] = []
    services: list[ServiceIn] = []
    paid_now_paise: int = Field(default=0, ge=0)
    method: str = "cash"
    note: str = ""


class BillLineOut(BaseModel):
    id: int
    item_id: int | None
    description: str
    quantity: int
    unit_price_paise: int
    line_total_paise: int
    is_service: bool


class BillOut(BaseModel):
    id: int
    number: int
    kind: str
    customer_id: int | None
    customer_name: str | None
    date: str
    site_note: str
    total_paise: int
    paid_paise: int
    balance_paise: int
    lines: list[BillLineOut]


class LedgerIn(BaseModel):
    category: str
    amount_paise: int = Field(gt=0)
    method: str = "cash"
    date: str
    note: str = ""
    bill_id: int | None = None
    purchase_id: int | None = None


class LedgerOut(BaseModel):
    id: int
    date: str
    direction: str
    amount_paise: int
    category: str
    method: str
    note: str
    bill_id: int | None
    purchase_id: int | None
    label: str


class DueOut(BaseModel):
    id: int
    title: str
    subtitle: str
    date: str
    total_paise: int
    paid_paise: int
    balance_paise: int


class TodayOut(BaseModel):
    date: str
    shop_id: int
    shop_name: str
    opening_paise: int
    in_paise: int
    out_paise: int
    closing_paise: int
    has_opening: bool
    unpaid_bills: list[DueOut]
    unpaid_purchases: list[DueOut]


class WalletOut(BaseModel):
    date: str
    opening_paise: int
    in_paise: int
    out_paise: int
    closing_paise: int
    entries: list[LedgerOut]


class StaffIn(BaseModel):
    name: str
    username: str
    password: str
    shop_ids: list[int]
