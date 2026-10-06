package com.shopcrm.app

import com.google.gson.annotations.SerializedName

data class StatusDto(@SerializedName("needs_setup") val needsSetup: Boolean)

data class UserDto(
    val id: Long,
    val name: String,
    val username: String,
    val role: String,
    @SerializedName("shop_ids") val shopIds: List<Long> = emptyList(),
)

data class AuthDto(val token: String, val user: UserDto)

data class ShopDto(
    val id: Long,
    val name: String,
    val address: String = "",
    val phone: String = "",
)

data class StockRowDto(
    @SerializedName("item_id") val itemId: Long,
    val name: String,
    val unit: String,
    @SerializedName("sale_price_paise") val salePricePaise: Long,
    @SerializedName("last_cost_paise") val lastCostPaise: Long?,
    val quantity: Int,
)

data class VendorDto(val id: Long, val name: String, val phone: String = "", val note: String = "")

data class CustomerDto(
    val id: Long,
    val name: String,
    val phone: String = "",
    val address: String = "",
)

data class ItemLineReq(
    @SerializedName("item_id") val itemId: Long,
    val quantity: Int,
    @SerializedName("unit_price_paise") val unitPricePaise: Long,
)

data class ServiceReq(val description: String, @SerializedName("amount_paise") val amountPaise: Long)

data class PurchaseDto(
    val id: Long,
    @SerializedName("vendor_name") val vendorName: String,
    val date: String,
    val note: String = "",
    @SerializedName("total_paise") val totalPaise: Long,
    @SerializedName("paid_paise") val paidPaise: Long,
    @SerializedName("balance_paise") val balancePaise: Long,
)

data class BillLineDto(
    val description: String,
    val quantity: Int,
    @SerializedName("unit_price_paise") val unitPricePaise: Long,
    @SerializedName("line_total_paise") val lineTotalPaise: Long,
    @SerializedName("is_service") val service: Boolean,
)

data class BillDto(
    val id: Long,
    val number: Int,
    val kind: String,
    @SerializedName("customer_name") val customerName: String?,
    val date: String,
    @SerializedName("site_note") val siteNote: String = "",
    @SerializedName("total_paise") val totalPaise: Long,
    @SerializedName("paid_paise") val paidPaise: Long,
    @SerializedName("balance_paise") val balancePaise: Long,
    val lines: List<BillLineDto> = emptyList(),
)

data class DueDto(
    val id: Long,
    val title: String,
    val subtitle: String,
    val date: String,
    @SerializedName("balance_paise") val balancePaise: Long,
)

data class TodayDto(
    val date: String,
    @SerializedName("shop_name") val shopName: String,
    @SerializedName("opening_paise") val openingPaise: Long,
    @SerializedName("in_paise") val inPaise: Long,
    @SerializedName("out_paise") val outPaise: Long,
    @SerializedName("closing_paise") val closingPaise: Long,
    @SerializedName("has_opening") val hasOpening: Boolean,
    @SerializedName("unpaid_bills") val unpaidBills: List<DueDto> = emptyList(),
    @SerializedName("unpaid_purchases") val unpaidPurchases: List<DueDto> = emptyList(),
)

data class LedgerDto(
    val id: Long,
    val direction: String,
    @SerializedName("amount_paise") val amountPaise: Long,
    val method: String,
    val note: String = "",
    val label: String,
    val category: String,
)

data class WalletDto(
    val date: String,
    @SerializedName("opening_paise") val openingPaise: Long,
    @SerializedName("in_paise") val inPaise: Long,
    @SerializedName("out_paise") val outPaise: Long,
    @SerializedName("closing_paise") val closingPaise: Long,
    val entries: List<LedgerDto> = emptyList(),
)

data class SetupRequest(val name: String, val username: String, val password: String)
data class LoginRequest(val username: String, val password: String)
data class ShopRequest(val name: String, val address: String, val phone: String)
data class ItemRequest(val name: String, val unit: String, @SerializedName("sale_price_paise") val salePricePaise: Long)
data class AdjustRequest(@SerializedName("item_id") val itemId: Long, @SerializedName("quantity_delta") val quantityDelta: Int, val note: String)
data class VendorRequest(val name: String, val phone: String, val note: String)
data class CustomerRequest(val name: String, val phone: String, val address: String)
data class PurchaseRequest(
    @SerializedName("vendor_id") val vendorId: Long,
    val date: String,
    val note: String,
    val lines: List<ItemLineReq>,
)
data class BillRequest(
    val kind: String,
    @SerializedName("customer_id") val customerId: Long?,
    val date: String,
    @SerializedName("site_note") val siteNote: String,
    val lines: List<ItemLineReq>,
    val services: List<ServiceReq>,
    @SerializedName("paid_now_paise") val paidNowPaise: Long,
    val method: String,
    val note: String,
)
data class LedgerRequest(
    val category: String,
    @SerializedName("amount_paise") val amountPaise: Long,
    val method: String,
    val date: String,
    val note: String,
    @SerializedName("bill_id") val billId: Long?,
    @SerializedName("purchase_id") val purchaseId: Long?,
)
data class StaffRequest(val name: String, val username: String, val password: String, @SerializedName("shop_ids") val shopIds: List<Long>)
