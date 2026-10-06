package com.shopcrm.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val tabs = listOf("today" to "Today", "stock" to "Stock", "bills" to "Bills", "cash" to "Cash", "more" to "More")

@Composable
fun AppRoot(vm: CrmViewModel) {
    val state = vm.state
    val showTabs = state.user != null && state.shopId != 0L && vm.route in tabs.map { it.first }
    BackHandler(enabled = vm.route !in setOf("boot", "login", "today")) { vm.back() }
    Scaffold(
        bottomBar = {
            if (showTabs) {
                Row(Modifier.fillMaxWidth()) {
                    tabs.forEach { (id, label) ->
                        TextButton(onClick = { vm.tab(id) }, modifier = Modifier.weight(1f)) {
                            Text(label, fontWeight = if (vm.route == id) FontWeight.Bold else FontWeight.Normal)
                        }
                    }
                }
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            if (state.loading) CircularProgressIndicator()
            state.error?.let {
                Text(it, color = androidx.compose.material3.MaterialTheme.colorScheme.error)
                TextButton(onClick = vm::clearError) { Text("Dismiss") }
            }
            when {
                vm.route == "boot" -> Text("Opening the books…")
                vm.route == "login" -> LoginScreen(vm)
                vm.route == "today" -> TodayScreen(vm)
                vm.route == "stock" -> StockScreen(vm)
                vm.route == "bills" -> BillsScreen(vm)
                vm.route.startsWith("bill/") -> BillScreen(vm)
                vm.route == "cash" -> CashScreen(vm)
                vm.route == "cashnew" -> CashForm(vm)
                vm.route == "sale" -> BillForm(vm, job = false)
                vm.route == "job" -> BillForm(vm, job = true)
                vm.route == "purchase" -> PurchaseForm(vm)
                vm.route == "customers" -> PeopleScreen(vm, customers = true)
                vm.route == "vendors" -> PeopleScreen(vm, customers = false)
                vm.route == "settings" -> SettingsScreen(vm)
                vm.route == "more" -> MoreScreen(vm)
            }
        }
    }
}

@Composable
private fun LoginScreen(vm: CrmViewModel) {
    val state = vm.state
    var name by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var server by remember { mutableStateOf(state.serverUrl) }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Shop CRM", fontSize = 28.sp, fontWeight = FontWeight.Bold)
        Text(if (state.needsSetup) "Create the owner account" else "Log in")
        if (state.needsSetup) Field("Your name", name) { name = it }
        Field("Username", username) { username = it }
        Field("Password", password) { password = it }
        Button(onClick = {
            if (state.needsSetup) vm.setup(name, username, password) else vm.login(username, password)
        }) { Text(if (state.needsSetup) "Create owner" else "Log in") }
        Field("Server", server) { server = it }
        Text("Emulator: http://10.0.2.2:8000. Phone: the address shown in the web app under More.", fontSize = 13.sp)
        TextButton(onClick = { vm.saveServer(server) }) { Text("Save server and retry") }
    }
}

@Composable
private fun TodayScreen(vm: CrmViewModel) {
    val state = vm.state
    if (state.shopId == 0L) {
        Text("Create a shop to start.")
        Button(onClick = { vm.open("settings") }) { Text("Add shop") }
        return
    }
    val today = state.today
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        ShopPicker(vm)
        Text("Cash in hand", fontSize = 14.sp)
        Text(formatInr(today?.closingPaise ?: 0), fontSize = 36.sp, fontWeight = FontWeight.Bold)
        Text("In ${formatInr(today?.inPaise ?: 0)}   Out ${formatInr(today?.outPaise ?: 0)}")
        if (today?.hasOpening == false) {
            TextButton(onClick = { vm.open("cashnew") }) { Text("Add starting cash") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.open("sale") }) { Text("Sale") }
            Button(onClick = { vm.open("job") }) { Text("Install") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.open("purchase") }) { Text("Stock in") }
            Button(onClick = { vm.open("cashnew") }) { Text("Cash") }
        }
        Text("Customers still to pay", fontWeight = FontWeight.Bold)
        today?.unpaidBills.orEmpty().forEach { due ->
            DueRow(due.title, due.subtitle, due.balancePaise) { vm.open("bill/${due.id}") }
        }
        Text("Still to pay vendors", fontWeight = FontWeight.Bold)
        today?.unpaidPurchases.orEmpty().forEach { due ->
            DueRow(due.title, due.subtitle, due.balancePaise) { vm.open("cashnew") }
        }
    }
}

@Composable
private fun ShopPicker(vm: CrmViewModel) {
    val state = vm.state
    var open by remember { mutableStateOf(false) }
    val name = state.shops.firstOrNull { it.id == state.shopId }?.name ?: "Shop"
    TextButton(onClick = { open = true }) { Text(name, fontWeight = FontWeight.Bold) }
    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
        state.shops.forEach { shop ->
            DropdownMenuItem(text = { Text(shop.name) }, onClick = {
                open = false
                vm.selectShop(shop.id)
            })
        }
    }
}

@Composable
private fun DueRow(title: String, subtitle: String, paise: Long, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth().padding(bottom = 8.dp).clickable(onClick = onClick)) {
        Row(Modifier.padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.Bold)
                Text(subtitle, fontSize = 13.sp)
            }
            Text(formatInr(paise), fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun StockScreen(vm: CrmViewModel) {
    val state = vm.state
    var showAdd by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Button(onClick = { showAdd = !showAdd }) { Text("Add item") } }
        if (showAdd) {
            item {
                Field("Name", name) { name = it }
                Field("Sale price", price) { price = it }
                Button(onClick = { vm.createItem(name, "pcs", price); name = ""; price = "" }) { Text("Save item") }
            }
        }
        items(state.stock, key = { it.itemId }) { row ->
            var delta by remember(row.itemId) { mutableStateOf("") }
            var note by remember(row.itemId) { mutableStateOf("") }
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(row.name, fontWeight = FontWeight.Bold)
                    Text("${row.quantity} ${row.unit} · ${formatInr(row.salePricePaise)}")
                    Field("Qty change", delta) { delta = it }
                    Field("Note", note) { note = it }
                    TextButton(onClick = { vm.adjust(row.itemId, delta, note) }) { Text("Save adjustment") }
                }
            }
        }
    }
}

@Composable
private fun BillsScreen(vm: CrmViewModel) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { vm.open("sale") }) { Text("Counter sale") }
                Button(onClick = { vm.open("job") }) { Text("Installation") }
            }
        }
        items(vm.state.bills, key = { it.id }) { bill ->
            DueRow(
                bill.customerName ?: "Walk-in",
                "#${bill.number.toString().padStart(4, '0')} · ${if (bill.kind == "job") "Installation" else "Counter sale"}",
                if (bill.balancePaise > 0) bill.balancePaise else bill.totalPaise,
            ) { vm.open("bill/${bill.id}") }
        }
    }
}

@Composable
private fun BillScreen(vm: CrmViewModel) {
    val bill = vm.state.openBill ?: return
    var amount by remember(bill.id) { mutableStateOf(paiseInput(bill.balancePaise)) }
    var method by remember { mutableStateOf("cash") }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("#${bill.number.toString().padStart(4, '0')}", fontWeight = FontWeight.Bold)
        Text(bill.customerName ?: "Walk-in")
        if (bill.siteNote.isNotBlank()) Text(bill.siteNote)
        Text(formatInr(bill.totalPaise), fontSize = 32.sp)
        Text("Paid ${formatInr(bill.paidPaise)} · due ${formatInr(bill.balancePaise)}")
        bill.lines.forEach { line ->
            Text("${line.description}  ${formatInr(line.lineTotalPaise)}")
        }
        if (bill.balancePaise > 0) {
            Field("Amount", amount) { amount = it }
            MethodPicker(method) { method = it }
            Button(onClick = { vm.pay("customer_receipt", amount, method, "", bill.id, null) }) { Text("Record payment") }
        }
    }
}

@Composable
private fun CashScreen(vm: CrmViewModel) {
    val wallet = vm.state.wallet
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(formatInr(wallet?.closingPaise ?: 0), fontSize = 32.sp, fontWeight = FontWeight.Bold)
        Text("Open ${formatInr(wallet?.openingPaise ?: 0)}  In ${formatInr(wallet?.inPaise ?: 0)}  Out ${formatInr(wallet?.outPaise ?: 0)}")
        Button(onClick = { vm.open("cashnew") }) { Text("Money in / out") }
        wallet?.entries.orEmpty().forEach { entry ->
            val sign = if (entry.direction == "in") "+" else "−"
            Text("$sign${formatInr(entry.amountPaise)}  ${entry.label}")
        }
    }
}

@Composable
private fun CashForm(vm: CrmViewModel) {
    val today = vm.state.today
    var kind by remember { mutableStateOf(if (today?.hasOpening == false) "opening" else "expense") }
    var amount by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var method by remember { mutableStateOf("cash") }
    var billId by remember { mutableStateOf(today?.unpaidBills?.firstOrNull()?.id) }
    var purchaseId by remember { mutableStateOf(today?.unpaidPurchases?.firstOrNull()?.id) }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf("customer_receipt" to "In", "vendor_payout" to "Vendor", "expense" to "Expense", "opening" to "Start").forEach { (id, label) ->
                TextButton(onClick = { kind = id }) { Text(label, fontWeight = if (kind == id) FontWeight.Bold else FontWeight.Normal) }
            }
        }
        if (kind == "customer_receipt") {
            today?.unpaidBills.orEmpty().forEach { due ->
                Row {
                    RadioButton(selected = billId == due.id, onClick = { billId = due.id; amount = paiseInput(due.balancePaise) })
                    Text("${due.title} ${formatInr(due.balancePaise)}")
                }
            }
        }
        if (kind == "vendor_payout") {
            today?.unpaidPurchases.orEmpty().forEach { due ->
                Row {
                    RadioButton(selected = purchaseId == due.id, onClick = { purchaseId = due.id; amount = paiseInput(due.balancePaise) })
                    Text("${due.title} ${formatInr(due.balancePaise)}")
                }
            }
        }
        Field("Amount", amount) { amount = it }
        Field("Note", note) { note = it }
        MethodPicker(method) { method = it }
        Button(onClick = {
            vm.pay(
                kind,
                amount,
                method,
                note,
                if (kind == "customer_receipt") billId else null,
                if (kind == "vendor_payout") purchaseId else null,
            )
        }) { Text("Save cash entry") }
    }
}

@Composable
private fun BillForm(vm: CrmViewModel, job: Boolean) {
    val state = vm.state
    val qty = remember { mutableStateMapOf<Long, String>() }
    val rates = remember { mutableStateMapOf<Long, String>() }
    var customerId by remember { mutableStateOf<Long?>(null) }
    var site by remember { mutableStateOf("") }
    var service by remember { mutableStateOf("Installation") }
    var serviceAmount by remember { mutableStateOf("") }
    var paid by remember { mutableStateOf("") }
    var method by remember { mutableStateOf("cash") }
    var formError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(state.stock) {
        state.stock.forEach { row ->
            if (rates[row.itemId] == null) rates[row.itemId] = paiseInput(row.salePricePaise)
        }
    }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(if (job) "Installation" else "Counter sale", fontWeight = FontWeight.Bold)
        formError?.let { Text(it) }
        if (job || state.customers.isNotEmpty()) {
            TextButton(onClick = { customerId = null }) { Text(if (customerId == null) "Walk-in" else "Clear customer") }
            state.customers.forEach { customer ->
                Row {
                    RadioButton(selected = customerId == customer.id, onClick = { customerId = customer.id })
                    Text(customer.name)
                }
            }
        }
        if (job) Field("Site note", site) { site = it }
        state.stock.forEach { row ->
            Text("${row.name} · ${row.quantity} in stock")
            Field("Qty", qty[row.itemId].orEmpty()) { qty[row.itemId] = it }
            Field("Rate", rates[row.itemId].orEmpty()) { rates[row.itemId] = it }
        }
        if (job) {
            Field("Service", service) { service = it }
            Field("Service amount", serviceAmount) { serviceAmount = it }
        }
        Field("Paid now", paid) { paid = it }
        MethodPicker(method) { method = it }
        Button(onClick = {
            val lines = mutableListOf<ItemLineReq>()
            for (row in state.stock) {
                val count = qty[row.itemId]?.toIntOrNull() ?: 0
                if (count == 0) continue
                val price = rupeesToPaise(rates[row.itemId].orEmpty())
                if (price == null) {
                    formError = "Enter a rate for ${row.name}"
                    return@Button
                }
                lines += ItemLineReq(row.itemId, count, price)
            }
            val services = mutableListOf<ServiceReq>()
            if (job && (service.isNotBlank() || serviceAmount.isNotBlank())) {
                val amount = rupeesToPaise(serviceAmount)
                if (service.isBlank() || amount == null) {
                    formError = "Enter the service and its amount"
                    return@Button
                }
                services += ServiceReq(service, amount)
            }
            if (lines.isEmpty() && services.isEmpty()) {
                formError = "Add at least one line"
                return@Button
            }
            if (job && customerId == null) {
                formError = "Choose the customer"
                return@Button
            }
            formError = null
            vm.createBill(if (job) "job" else "counter", customerId, site, lines, services, paid, method) {}
        }) { Text(if (job) "Save job" else "Save sale") }
    }
}

@Composable
private fun PurchaseForm(vm: CrmViewModel) {
    val state = vm.state
    var vendorId by remember { mutableStateOf(state.vendors.firstOrNull()?.id) }
    val qty = remember { mutableStateMapOf<Long, String>() }
    val costs = remember { mutableStateMapOf<Long, String>() }
    var note by remember { mutableStateOf("") }
    var formError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(state.stock) {
        state.stock.forEach { row ->
            if (costs[row.itemId] == null && row.lastCostPaise != null) costs[row.itemId] = paiseInput(row.lastCostPaise)
        }
    }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Receive stock", fontWeight = FontWeight.Bold)
        formError?.let { Text(it) }
        state.vendors.forEach { vendor ->
            Row {
                RadioButton(selected = vendorId == vendor.id, onClick = { vendorId = vendor.id })
                Text(vendor.name)
            }
        }
        if (state.vendors.isEmpty()) TextButton(onClick = { vm.open("vendors") }) { Text("Add a vendor first") }
        state.stock.forEach { row ->
            Text(row.name)
            Field("Qty", qty[row.itemId].orEmpty()) { qty[row.itemId] = it }
            Field("Cost", costs[row.itemId].orEmpty()) { costs[row.itemId] = it }
        }
        Field("Note", note) { note = it }
        Button(onClick = {
            val id = vendorId
            if (id == null) {
                formError = "Choose a vendor"
                return@Button
            }
            val lines = mutableListOf<ItemLineReq>()
            for (row in state.stock) {
                val count = qty[row.itemId]?.toIntOrNull() ?: 0
                if (count == 0) continue
                val cost = rupeesToPaise(costs[row.itemId].orEmpty())
                if (cost == null) {
                    formError = "Enter a cost for ${row.name}"
                    return@Button
                }
                lines += ItemLineReq(row.itemId, count, cost)
            }
            if (lines.isEmpty()) {
                formError = "Add at least one item"
                return@Button
            }
            vm.createPurchase(id, lines, note) {}
        }) { Text("Save stock in") }
    }
}

@Composable
private fun PeopleScreen(vm: CrmViewModel, customers: Boolean) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var extra by remember { mutableStateOf("") }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Field("Name", name) { name = it }
        Field("Phone", phone) { phone = it }
        Field(if (customers) "Address" else "Note", extra) { extra = it }
        Button(onClick = {
            if (customers) vm.createCustomer(name, phone, extra) else vm.createVendor(name, phone, extra)
            name = ""; phone = ""; extra = ""
        }) { Text(if (customers) "Add customer" else "Add vendor") }
        val rows = if (customers) vm.state.customers.map { it.name to it.phone } else vm.state.vendors.map { it.name to it.phone }
        rows.forEach { (title, subtitle) -> Text("$title  $subtitle") }
    }
}

@Composable
private fun MoreScreen(vm: CrmViewModel) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { vm.open("customers") }) { Text("Customers") }
        Button(onClick = { vm.open("vendors") }) { Text("Vendors") }
        Button(onClick = { vm.open("purchase") }) { Text("Stock in") }
        if (vm.state.user?.role == "owner") Button(onClick = { vm.open("settings") }) { Text("Shops and staff") }
        Text("Server ${vm.state.serverUrl}")
        Button(onClick = vm::logout) { Text("Log out") }
    }
}

@Composable
private fun SettingsScreen(vm: CrmViewModel) {
    var shopName by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var staffName by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val picked = remember { mutableStateMapOf<Long, Boolean>() }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("New shop", fontWeight = FontWeight.Bold)
        Field("Name", shopName) { shopName = it }
        Field("Address", address) { address = it }
        Field("Phone", phone) { phone = it }
        Button(onClick = { vm.createShop(shopName, address, phone) }) { Text("Save shop") }
        if (vm.state.user?.role == "owner" && vm.state.shops.isNotEmpty()) {
            Text("Staff", fontWeight = FontWeight.Bold)
            Field("Name", staffName) { staffName = it }
            Field("Username", username) { username = it }
            Field("Password", password) { password = it }
            vm.state.shops.forEach { shop ->
                Row {
                    RadioButton(selected = picked[shop.id] == true, onClick = { picked[shop.id] = picked[shop.id] != true })
                    Text(shop.name)
                }
            }
            Button(onClick = {
                vm.createStaff(staffName, username, password, picked.filterValues { it }.keys.toList())
            }) { Text("Add staff") }
        }
    }
}

@Composable
private fun MethodPicker(method: String, onChange: (String) -> Unit) {
    Row {
        listOf("cash" to "Cash", "upi" to "UPI", "other" to "Other").forEach { (id, label) ->
            TextButton(onClick = { onChange(id) }) {
                Text(label, fontWeight = if (method == id) FontWeight.Bold else FontWeight.Normal)
            }
        }
    }
}

@Composable
private fun Field(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(value = value, onValueChange = onChange, label = { Text(label) }, modifier = Modifier.fillMaxWidth())
}
