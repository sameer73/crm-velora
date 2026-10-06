package com.shopcrm.app

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.util.ArrayDeque

data class UiState(
    val loading: Boolean = false,
    val error: String? = null,
    val needsSetup: Boolean = false,
    val user: UserDto? = null,
    val shops: List<ShopDto> = emptyList(),
    val shopId: Long = 0,
    val serverUrl: String = "http://10.0.2.2:8000",
    val today: TodayDto? = null,
    val stock: List<StockRowDto> = emptyList(),
    val bills: List<BillDto> = emptyList(),
    val customers: List<CustomerDto> = emptyList(),
    val vendors: List<VendorDto> = emptyList(),
    val purchases: List<PurchaseDto> = emptyList(),
    val wallet: WalletDto? = null,
    val openBill: BillDto? = null,
)

class CrmViewModel(app: Application) : AndroidViewModel(app) {
    private val store = SessionStore(app)
    private var api: CrmApi = buildApi(store)
    private val history = ArrayDeque<String>()

    var state by mutableStateOf(UiState(serverUrl = store.serverUrl))
        private set
    var route by mutableStateOf("boot")
        private set

    init {
        boot()
    }

    fun open(next: String) {
        if (route != next) history.addLast(route)
        route = next
        loadRoute(next)
    }

    fun tab(next: String) {
        history.clear()
        route = next
        loadRoute(next)
    }

    fun back() {
        route = if (history.isEmpty()) "today" else history.removeLast()
        loadRoute(route)
    }

    fun clearError() {
        state = state.copy(error = null)
    }

    fun boot() {
        viewModelScope.launch {
            try {
                api = buildApi(store)
                val status = api.status()
                state = state.copy(needsSetup = status.needsSetup, serverUrl = store.serverUrl, error = null)
                if (!store.token.isNullOrBlank() && !status.needsSetup) {
                    state = state.copy(user = api.me())
                    loadShops()
                    route = if (state.shopId == 0L) "settings" else "today"
                    if (state.shopId != 0L) loadRoute("today")
                } else {
                    route = "login"
                }
            } catch (error: Exception) {
                route = "login"
                state = state.copy(error = httpMessage(error), serverUrl = store.serverUrl)
            }
        }
    }

    fun setup(name: String, username: String, password: String) = run {
        val auth = api.setup(SetupRequest(name, username, password))
        signedIn(auth)
    }

    fun login(username: String, password: String) = run {
        val auth = api.login(LoginRequest(username.trim(), password))
        signedIn(auth)
    }

    fun logout() {
        store.token = null
        store.shopId = 0
        state = UiState(serverUrl = store.serverUrl)
        history.clear()
        route = "login"
    }

    fun saveServer(url: String) {
        store.serverUrl = url
        api = buildApi(store)
        state = state.copy(serverUrl = store.serverUrl, error = null)
        boot()
    }

    fun selectShop(id: Long) {
        store.shopId = id
        state = state.copy(shopId = id)
        tab("today")
    }

    fun createShop(name: String, address: String, phone: String) = run {
        val shop = api.createShop(ShopRequest(name, address, phone))
        store.shopId = shop.id
        loadShops()
        route = "today"
        loadRoute("today")
    }

    fun createStaff(name: String, username: String, password: String, shopIds: List<Long>) = run {
        api.createStaff(StaffRequest(name, username, password, shopIds))
        state = state.copy(error = null)
    }

    fun createItem(name: String, unit: String, price: String) = run {
        val paise = rupeesToPaise(price) ?: error("Enter a sale price like 800 or 800.50")
        api.createItem(ItemRequest(name, unit.ifBlank { "pcs" }, paise))
        state = state.copy(stock = api.stock(shop()))
    }

    fun adjust(itemId: Long, delta: String, note: String) = run {
        val change = delta.trim().toIntOrNull() ?: error("Enter a whole number like -1 or 2")
        api.adjust(shop(), AdjustRequest(itemId, change, note))
        state = state.copy(stock = api.stock(shop()))
    }

    fun createVendor(name: String, phone: String, note: String) = run {
        api.createVendor(VendorRequest(name, phone, note))
        state = state.copy(vendors = api.vendors())
    }

    fun createCustomer(name: String, phone: String, address: String) = run {
        api.createCustomer(shop(), CustomerRequest(name, phone, address))
        state = state.copy(customers = api.customers(shop()))
    }

    fun createPurchase(vendorId: Long, lines: List<ItemLineReq>, note: String, onDone: () -> Unit) = run {
        if (lines.isEmpty()) error("Add at least one item")
        api.createPurchase(shop(), PurchaseRequest(vendorId, LocalDate.now().toString(), note, lines))
        onDone()
        tab("today")
    }

    fun createBill(
        kind: String,
        customerId: Long?,
        siteNote: String,
        lines: List<ItemLineReq>,
        services: List<ServiceReq>,
        paidNow: String,
        method: String,
        onDone: () -> Unit,
    ) = run {
        val paid = if (paidNow.isBlank()) 0L else rupeesToPaise(paidNow) ?: error("Enter the amount paid")
        val bill = api.createBill(
            shop(),
            BillRequest(kind, customerId, LocalDate.now().toString(), siteNote, lines, services, paid, method, ""),
        )
        onDone()
        openBill(bill.id)
    }

    fun pay(category: String, amount: String, method: String, note: String, billId: Long?, purchaseId: Long?) = run {
        val paise = rupeesToPaise(amount) ?: error("Enter an amount like 150 or 150.50")
        api.addLedger(shop(), LedgerRequest(category, paise, method, LocalDate.now().toString(), note, billId, purchaseId))
        refreshMoney()
        if (billId != null) state = state.copy(openBill = api.bill(shop(), billId))
    }

    private fun openBill(id: Long) {
        history.clear()
        history.addLast("bills")
        route = "bill/$id"
        loadRoute(route)
    }

    private suspend fun signedIn(auth: AuthDto) {
        store.token = auth.token
        api = buildApi(store)
        state = state.copy(user = auth.user, needsSetup = false)
        loadShops()
        route = if (state.shopId == 0L) "settings" else "today"
        if (state.shopId != 0L) loadRoute("today")
    }

    private fun loadRoute(next: String) {
        viewModelScope.launch {
            try {
                when {
                    next == "today" && state.shopId != 0L -> state = state.copy(today = api.today(state.shopId))
                    next == "stock" && state.shopId != 0L -> state = state.copy(stock = api.stock(state.shopId))
                    next == "bills" && state.shopId != 0L -> state = state.copy(bills = api.bills(state.shopId))
                    next == "cash" && state.shopId != 0L -> state = state.copy(wallet = api.wallet(state.shopId, LocalDate.now().toString()))
                    next == "sale" || next == "job" || next == "purchase" -> {
                        if (state.shopId == 0L) return@launch
                        state = state.copy(
                            stock = api.stock(state.shopId),
                            customers = api.customers(state.shopId),
                            vendors = api.vendors(),
                        )
                    }
                    next == "customers" && state.shopId != 0L -> state = state.copy(customers = api.customers(state.shopId))
                    next == "vendors" -> state = state.copy(vendors = api.vendors())
                    next == "cashnew" && state.shopId != 0L -> state = state.copy(today = api.today(state.shopId))
                    next.startsWith("bill/") && state.shopId != 0L -> {
                        val id = next.removePrefix("bill/").toLong()
                        state = state.copy(openBill = api.bill(state.shopId, id))
                    }
                }
            } catch (error: Exception) {
                state = state.copy(error = httpMessage(error))
            }
        }
    }

    private suspend fun refreshMoney() {
        val id = shop()
        state = state.copy(today = api.today(id), wallet = api.wallet(id, LocalDate.now().toString()))
    }

    private suspend fun loadShops() {
        val shops = api.shops()
        var id = store.shopId
        if (shops.none { it.id == id }) id = shops.firstOrNull()?.id ?: 0L
        store.shopId = id
        val today = if (id != 0L) api.today(id) else null
        state = state.copy(shops = shops, shopId = id, today = today)
    }

    private fun shop(): Long {
        if (state.shopId == 0L) error("Create a shop first")
        return state.shopId
    }

    private fun run(block: suspend () -> Unit) {
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                block()
            } catch (error: Exception) {
                state = state.copy(error = httpMessage(error))
            } finally {
                state = state.copy(loading = false)
            }
        }
    }
}
