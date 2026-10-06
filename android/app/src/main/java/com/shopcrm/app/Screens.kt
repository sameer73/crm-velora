package com.shopcrm.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CallMade
import androidx.compose.material.icons.filled.CallReceived
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.LocalShipping
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Payments
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.PointOfSale
import androidx.compose.material.icons.filled.QrCode2
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Savings
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Store
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Image

private val Navy = Color(0xFF10243A)
private val Teal = Color(0xFF0E7C6B)
private val TealSoft = Color(0xFFE7F4F1)
private val Paper = Color(0xFFF4EFE6)
private val CardWhite = Color(0xFFFFFDF8)
private val Muted = Color(0xFF667084)
private val InGreen = Color(0xFF0D7A45)
private val OutRed = Color(0xFFA33B24)

private val tabs = listOf(
    Tab("today", "Today", Icons.Filled.Home),
    Tab("stock", "Stock", Icons.Filled.Inventory2),
    Tab("bills", "Bills", Icons.Filled.ReceiptLong),
    Tab("cash", "Cash", Icons.Filled.AccountBalanceWallet),
    Tab("more", "More", Icons.Filled.GridView),
)

private data class Tab(val id: String, val label: String, val icon: ImageVector)

@Composable
fun AppRoot(vm: CrmViewModel) {
    val state = vm.state
    val onTab = vm.route in tabs.map { it.id }
    val showTabs = state.user != null && state.shopId != 0L && onTab
    val showBar = vm.route != "boot" && vm.route != "login"
    BackHandler(enabled = vm.route !in setOf("boot", "login", "today")) { vm.back() }
    Scaffold(
        containerColor = Paper,
        topBar = {
            if (showBar) {
                Surface(color = Navy) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .windowInsetsPadding(WindowInsets.statusBars)
                            .height(72.dp)
                            .padding(horizontal = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (!onTab) {
                            IconButton(onClick = vm::back) {
                                Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                            }
                        }
                        Logo(48)
                        if (!onTab) {
                            Spacer(Modifier.width(10.dp))
                            Text(pageTitle(vm.route), color = Color.White, fontWeight = FontWeight.SemiBold)
                        }
                        Spacer(Modifier.weight(1f))
                        if (vm.state.shops.isNotEmpty()) ShopPicker(vm)
                    }
                }
            }
        },
        bottomBar = {
            if (showTabs) {
                NavigationBar(containerColor = Color.White) {
                    tabs.forEach { tab ->
                        NavigationBarItem(
                            selected = vm.route == tab.id,
                            onClick = { vm.tab(tab.id) },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = Teal,
                                selectedTextColor = Teal,
                                indicatorColor = TealSoft,
                                unselectedIconColor = Muted,
                                unselectedTextColor = Muted,
                            ),
                        )
                    }
                }
            }
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (state.loading) {
                LinearProgressIndicator(Modifier.fillMaxWidth(), color = Teal, trackColor = TealSoft)
            }
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
                Column(Modifier.widthIn(max = 560.dp).fillMaxHeight().padding(16.dp)) {
                    state.error?.let { ErrorNote(it, vm::clearError) }
                    when {
                        vm.route == "boot" -> BootScreen()
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
    }
}

private fun pageTitle(route: String) = when {
    route == "stock" -> "Stock"
    route == "bills" -> "Bills"
    route == "cash" -> "Cash"
    route == "cashnew" -> "Money in / out"
    route == "sale" -> "Counter sale"
    route == "job" -> "Installation"
    route == "purchase" -> "Stock in"
    route == "customers" -> "Customers"
    route == "vendors" -> "Vendors"
    route == "settings" -> "Shops and staff"
    route == "more" -> "More"
    route.startsWith("bill/") -> "Bill"
    else -> "Today"
}

@Composable
private fun Logo(height: Int) {
    Image(
        painter = painterResource(R.drawable.company_logo),
        contentDescription = "Verito Tech",
        modifier = Modifier.height(height.dp).clip(RoundedCornerShape(8.dp)).background(Color.White),
        contentScale = ContentScale.Fit,
    )
}

@Composable
private fun BootScreen() {
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Logo(64)
        Spacer(Modifier.height(16.dp))
        Text("Opening the books…", color = Muted)
    }
}

@Composable
private fun ErrorNote(message: String, onDismiss: () -> Unit) {
    Card(Modifier.fillMaxWidth().padding(bottom = 10.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFFF8E6DF))) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Error, contentDescription = null, tint = OutRed)
            Spacer(Modifier.width(8.dp))
            Text(message, color = OutRed, modifier = Modifier.weight(1f))
            TextButton(onClick = onDismiss) { Text("Dismiss") }
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
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(12.dp))
        Logo(72)
        Text(if (state.needsSetup) "Create the owner account" else "Sign in to the shop book", color = Muted)
        if (state.needsSetup) Field("Your name", name, Icons.Filled.Person) { name = it }
        Field("Username", username, Icons.Filled.Person) { username = it }
        Field("Password", password, Icons.Filled.Lock, secret = true) { password = it }
        Button(onClick = {
            if (state.needsSetup) vm.setup(name, username, password) else vm.login(username, password)
        }, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            Icon(Icons.Filled.Lock, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (state.needsSetup) "Create owner" else "Log in")
        }
        Field("Server", server, Icons.Filled.Dns) { server = it }
        Text("This emulator uses http://localhost:8000.", color = Muted, fontSize = 13.sp)
        TextButton(onClick = { vm.saveServer(server) }) { Text("Save server and retry") }
    }
}

@Composable
private fun TodayScreen(vm: CrmViewModel) {
    val state = vm.state
    if (state.shopId == 0L) {
        EmptyShop(vm)
        return
    }
    val today = state.today
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        MoneyCard(
            label = "Cash in hand",
            amount = formatInr(today?.closingPaise ?: 0),
            incoming = formatInr(today?.inPaise ?: 0),
            outgoing = formatInr(today?.outPaise ?: 0),
        )
        if (today?.hasOpening == false) {
            TextButton(onClick = { vm.open("cashnew") }) {
                Icon(Icons.Filled.Savings, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Add starting cash")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ActionTile(Modifier.weight(1f), "Sale", Icons.Filled.PointOfSale) { vm.open("sale") }
            ActionTile(Modifier.weight(1f), "Install", Icons.Filled.Build) { vm.open("job") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ActionTile(Modifier.weight(1f), "Stock in", Icons.Filled.LocalShipping) { vm.open("purchase") }
            ActionTile(Modifier.weight(1f), "Cash", Icons.Filled.Payments) { vm.open("cashnew") }
        }
        SectionTitle("Customers still to pay", Icons.Filled.Person)
        if (today?.unpaidBills.orEmpty().isEmpty()) Text("No open bills.", color = Muted)
        today?.unpaidBills.orEmpty().forEach { due ->
            ListRow(due.title, due.subtitle, formatInr(due.balancePaise), Icons.Filled.ReceiptLong, OutRed) { vm.open("bill/${due.id}") }
        }
        SectionTitle("Still to pay vendors", Icons.Filled.Store)
        if (today?.unpaidPurchases.orEmpty().isEmpty()) Text("No open vendor bills.", color = Muted)
        today?.unpaidPurchases.orEmpty().forEach { due ->
            ListRow(due.title, due.subtitle, formatInr(due.balancePaise), Icons.Filled.LocalShipping, OutRed) { vm.open("cashnew") }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun EmptyShop(vm: CrmViewModel) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Create a shop to start.", color = Muted)
        Button(onClick = { vm.open("settings") }) {
            Icon(Icons.Filled.Store, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Add shop")
        }
    }
}

@Composable
private fun ShopPicker(vm: CrmViewModel) {
    val state = vm.state
    var open by remember { mutableStateOf(false) }
    val name = state.shops.firstOrNull { it.id == state.shopId }?.name ?: "Shop"
    Box {
        TextButton(onClick = { open = true }) {
            Icon(Icons.Filled.Store, contentDescription = null, tint = Color.White)
            Spacer(Modifier.width(4.dp))
            Text(name, color = Color.White, fontWeight = FontWeight.Bold)
            Icon(Icons.Filled.ExpandMore, contentDescription = "Choose shop", tint = Color.White)
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            state.shops.forEach { shop ->
                DropdownMenuItem(
                    text = { Text(shop.name) },
                    leadingIcon = { Icon(Icons.Filled.Store, contentDescription = null) },
                    onClick = {
                        open = false
                        vm.selectShop(shop.id)
                    },
                )
            }
        }
    }
}

@Composable
private fun MoneyCard(label: String, amount: String, incoming: String, outgoing: String) {
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = Navy)) {
        Column(Modifier.padding(20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.AccountBalanceWallet, contentDescription = null, tint = Color(0xFFD7EFE8))
                Spacer(Modifier.width(8.dp))
                Text(label, color = Color(0xFFD7EFE8))
            }
            Text(amount, color = Color.White, fontSize = 36.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                AmountChip(Icons.Filled.CallReceived, "In $incoming", InGreen)
                AmountChip(Icons.Filled.CallMade, "Out $outgoing", Color(0xFFFFB4A4))
            }
        }
    }
}

@Composable
private fun AmountChip(icon: ImageVector, label: String, tint: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(4.dp))
        Text(label, color = tint, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun ActionTile(modifier: Modifier, label: String, icon: ImageVector, onClick: () -> Unit) {
    Card(
        modifier.clickable(onClick = onClick),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = CardWhite),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.size(36.dp).clip(CircleShape).background(TealSoft), contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = null, tint = Teal)
            }
            Text(label, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun SectionTitle(title: String, icon: ImageVector) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = Navy, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(8.dp))
        Text(title, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun ListRow(title: String, subtitle: String, trailing: String, icon: ImageVector, tint: Color, onClick: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = CardWhite),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(40.dp).clip(CircleShape).background(TealSoft), contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = null, tint = Teal)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                if (subtitle.isNotBlank()) Text(subtitle, color = Muted, fontSize = 13.sp)
            }
            Text(trailing, color = tint, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun StockScreen(vm: CrmViewModel) {
    val state = vm.state
    var showAdd by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Button(onClick = { showAdd = !showAdd }) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Add item")
            }
        }
        if (showAdd) {
            item {
                Card(colors = CardDefaults.cardColors(containerColor = CardWhite), shape = RoundedCornerShape(16.dp)) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Field("Name", name, Icons.Filled.Inventory2) { name = it }
                        Field("Sale price", price, Icons.Filled.Payments, number = true) { price = it }
                        Button(onClick = { vm.createItem(name, "pcs", price); name = ""; price = "" }) { Text("Save item") }
                    }
                }
            }
        }
        items(state.stock, key = { it.itemId }) { row ->
            var open by remember(row.itemId) { mutableStateOf(false) }
            var delta by remember(row.itemId) { mutableStateOf("") }
            var note by remember(row.itemId) { mutableStateOf("") }
            Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = CardWhite)) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(40.dp).clip(CircleShape).background(TealSoft), contentAlignment = Alignment.Center) {
                            Icon(Icons.Filled.Inventory2, contentDescription = null, tint = Teal)
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(row.name, fontWeight = FontWeight.SemiBold)
                            Text("${row.quantity} ${row.unit} · ${formatInr(row.salePricePaise)}", color = Muted, fontSize = 13.sp)
                        }
                        IconButton(onClick = { open = !open }) {
                            Icon(Icons.Filled.Tune, contentDescription = "Correct stock", tint = Teal)
                        }
                    }
                    if (open) {
                        Field("Quantity change", delta, Icons.Filled.Tune, number = true) { delta = it }
                        Field("Note", note, Icons.Filled.Edit) { note = it }
                        Button(onClick = { vm.adjust(row.itemId, delta, note) }) { Text("Save adjustment") }
                    }
                }
            }
        }
    }
}

@Composable
private fun BillsScreen(vm: CrmViewModel) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                ActionTile(Modifier.weight(1f), "Counter sale", Icons.Filled.PointOfSale) { vm.open("sale") }
                ActionTile(Modifier.weight(1f), "Installation", Icons.Filled.Build) { vm.open("job") }
            }
        }
        items(vm.state.bills, key = { it.id }) { bill ->
            val due = bill.balancePaise > 0
            ListRow(
                bill.customerName ?: "Walk-in",
                "#${bill.number.toString().padStart(4, '0')} · ${if (bill.kind == "job") "Installation" else "Counter sale"}",
                if (due) formatInr(bill.balancePaise) else "Paid",
                if (due) Icons.Filled.Schedule else Icons.Filled.CheckCircle,
                if (due) OutRed else InGreen,
            ) { vm.open("bill/${bill.id}") }
        }
    }
}

@Composable
private fun BillScreen(vm: CrmViewModel) {
    val bill = vm.state.openBill ?: return
    var amount by remember(bill.id) { mutableStateOf(paiseInput(bill.balancePaise)) }
    var method by remember { mutableStateOf("cash") }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        MoneyCard(
            label = bill.customerName ?: "Walk-in",
            amount = formatInr(bill.balancePaise),
            incoming = "Paid ${formatInr(bill.paidPaise)}",
            outgoing = "Total ${formatInr(bill.totalPaise)}",
        )
        Text("#${bill.number.toString().padStart(4, '0')} · ${if (bill.kind == "job") "Installation" else "Counter sale"}", color = Muted)
        if (bill.siteNote.isNotBlank()) Text(bill.siteNote)
        bill.lines.forEach { line ->
            ListRow(line.description, if (line.service) "Service" else "Part", formatInr(line.lineTotalPaise), if (line.service) Icons.Filled.Build else Icons.Filled.Inventory2, Navy) {}
        }
        if (bill.balancePaise > 0) {
            SectionTitle("Record money received", Icons.Filled.Payments)
            Field("Amount", amount, Icons.Filled.Payments, number = true) { amount = it }
            MethodPicker(method) { method = it }
            Button(onClick = { vm.pay("customer_receipt", amount, method, "", bill.id, null) }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Filled.CheckCircle, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Record payment")
            }
        }
    }
}

@Composable
private fun CashScreen(vm: CrmViewModel) {
    val wallet = vm.state.wallet
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        MoneyCard(
            label = "Closing cash",
            amount = formatInr(wallet?.closingPaise ?: 0),
            incoming = formatInr(wallet?.inPaise ?: 0),
            outgoing = formatInr(wallet?.outPaise ?: 0),
        )
        Text("Opened at ${formatInr(wallet?.openingPaise ?: 0)}", color = Muted)
        Button(onClick = { vm.open("cashnew") }) {
            Icon(Icons.Filled.Payments, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Money in / out")
        }
        wallet?.entries.orEmpty().forEach { entry ->
            val incoming = entry.direction == "in"
            ListRow(
                entry.label,
                entry.method,
                "${if (incoming) "+" else "−"}${formatInr(entry.amountPaise)}",
                if (incoming) Icons.Filled.CallReceived else Icons.Filled.CallMade,
                if (incoming) InGreen else OutRed,
            ) {}
        }
        if (wallet?.entries.orEmpty().isEmpty()) Text("No cash movement on this day.", color = Muted)
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
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Choice("In", Icons.Filled.CallReceived, kind == "customer_receipt", Modifier.weight(1f)) { kind = "customer_receipt" }
            Choice("Vendor", Icons.Filled.Store, kind == "vendor_payout", Modifier.weight(1f)) { kind = "vendor_payout" }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Choice("Expense", Icons.Filled.Payments, kind == "expense", Modifier.weight(1f)) { kind = "expense" }
            Choice("Start", Icons.Filled.Savings, kind == "opening", Modifier.weight(1f)) { kind = "opening" }
        }
        if (kind == "customer_receipt") {
            today?.unpaidBills.orEmpty().forEach { due ->
                ListRow(due.title, formatInr(due.balancePaise), if (billId == due.id) "Selected" else "", Icons.Filled.ReceiptLong, Teal) {
                    billId = due.id
                    amount = paiseInput(due.balancePaise)
                }
            }
            if (today?.unpaidBills.orEmpty().isEmpty()) Text("No unpaid bills.", color = Muted)
        }
        if (kind == "vendor_payout") {
            today?.unpaidPurchases.orEmpty().forEach { due ->
                ListRow(due.title, formatInr(due.balancePaise), if (purchaseId == due.id) "Selected" else "", Icons.Filled.LocalShipping, Teal) {
                    purchaseId = due.id
                    amount = paiseInput(due.balancePaise)
                }
            }
            if (today?.unpaidPurchases.orEmpty().isEmpty()) Text("No stock receipt is waiting. Pay the vendor from the website, or record an expense.", color = Muted)
        }
        Field("Amount", amount, Icons.Filled.Payments, number = true) { amount = it }
        Field("Note", note, Icons.Filled.Edit) { note = it }
        MethodPicker(method) { method = it }
        Button(onClick = {
            vm.pay(kind, amount, method, note, if (kind == "customer_receipt") billId else null, if (kind == "vendor_payout") purchaseId else null)
        }, modifier = Modifier.fillMaxWidth()) { Text("Save cash entry") }
    }
}

@Composable
private fun Choice(label: String, icon: ImageVector, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        color = if (selected) Teal else CardWhite,
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
            Icon(icon, contentDescription = null, tint = if (selected) Color.White else Teal, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            Text(label, color = if (selected) Color.White else Navy, fontWeight = FontWeight.SemiBold)
        }
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
        formError?.let { ErrorNote(it) { formError = null } }
        SectionTitle(if (job) "Customer" else "Customer or walk-in", Icons.Filled.Person)
        Choice(if (customerId == null) "Walk-in" else "Walk-in", Icons.Filled.Person, customerId == null, Modifier.fillMaxWidth()) { customerId = null }
        state.customers.forEach { customer ->
            Choice(customer.name, Icons.Filled.Person, customerId == customer.id, Modifier.fillMaxWidth()) { customerId = customer.id }
        }
        if (job) Field("Site note", site, Icons.Filled.Place) { site = it }
        SectionTitle("Parts", Icons.Filled.Inventory2)
        state.stock.forEach { row ->
            Text("${row.name} · ${row.quantity} in stock", fontWeight = FontWeight.SemiBold)
            Field("Qty", qty[row.itemId].orEmpty(), Icons.Filled.Inventory2, number = true) { qty[row.itemId] = it }
            Field("Rate", rates[row.itemId].orEmpty(), Icons.Filled.Payments, number = true) { rates[row.itemId] = it }
        }
        if (job) {
            SectionTitle("Labour", Icons.Filled.Build)
            Field("Service", service, Icons.Filled.Build) { service = it }
            Field("Service amount", serviceAmount, Icons.Filled.Payments, number = true) { serviceAmount = it }
        }
        Field("Paid now", paid, Icons.Filled.Payments, number = true) { paid = it }
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
        }, modifier = Modifier.fillMaxWidth()) {
            Icon(if (job) Icons.Filled.Build else Icons.Filled.PointOfSale, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (job) "Save job" else "Save sale")
        }
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
        formError?.let { ErrorNote(it) { formError = null } }
        SectionTitle("Vendor", Icons.Filled.Store)
        state.vendors.forEach { vendor ->
            Choice(vendor.name, Icons.Filled.Store, vendorId == vendor.id, Modifier.fillMaxWidth()) { vendorId = vendor.id }
        }
        if (state.vendors.isEmpty()) TextButton(onClick = { vm.open("vendors") }) { Text("Add a vendor first") }
        SectionTitle("Items", Icons.Filled.Inventory2)
        state.stock.forEach { row ->
            Text(row.name, fontWeight = FontWeight.SemiBold)
            Field("Qty", qty[row.itemId].orEmpty(), Icons.Filled.Inventory2, number = true) { qty[row.itemId] = it }
            Field("Cost", costs[row.itemId].orEmpty(), Icons.Filled.Payments, number = true) { costs[row.itemId] = it }
        }
        Field("Note", note, Icons.Filled.Edit) { note = it }
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
        }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Filled.LocalShipping, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Save stock in")
        }
    }
}

@Composable
private fun PeopleScreen(vm: CrmViewModel, customers: Boolean) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var extra by remember { mutableStateOf("") }
    val icon = if (customers) Icons.Filled.Person else Icons.Filled.Store
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Field("Name", name, icon) { name = it }
        Field("Phone", phone, Icons.Filled.Phone) { phone = it }
        Field(if (customers) "Address" else "Note", extra, if (customers) Icons.Filled.Place else Icons.Filled.Edit) { extra = it }
        Button(onClick = {
            if (customers) vm.createCustomer(name, phone, extra) else vm.createVendor(name, phone, extra)
            name = ""; phone = ""; extra = ""
        }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Filled.Add, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (customers) "Add customer" else "Add vendor")
        }
        val rows = if (customers) vm.state.customers.map { it.name to it.phone } else vm.state.vendors.map { it.name to it.phone }
        rows.forEach { (title, subtitle) -> ListRow(title, subtitle, "", icon, Navy) {} }
    }
}

@Composable
private fun MoreScreen(vm: CrmViewModel) {
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        ListRow("Customers", "People who buy and get installations", "", Icons.Filled.Person, Navy) { vm.open("customers") }
        ListRow("Vendors", "Suppliers you pay", "", Icons.Filled.Store, Navy) { vm.open("vendors") }
        ListRow("Stock in", "Receive goods from a vendor", "", Icons.Filled.LocalShipping, Navy) { vm.open("purchase") }
        if (vm.state.user?.role == "owner") {
            ListRow("Shops and staff", "Add a shop or a login", "", Icons.Filled.Settings, Navy) { vm.open("settings") }
        }
        ListRow("Server", vm.state.serverUrl, "", Icons.Filled.Dns, Muted) {}
        Button(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Filled.Logout, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Log out")
        }
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
        SectionTitle("New shop", Icons.Filled.Store)
        Field("Name", shopName, Icons.Filled.Store) { shopName = it }
        Field("Address", address, Icons.Filled.Place) { address = it }
        Field("Phone", phone, Icons.Filled.Phone) { phone = it }
        Button(onClick = { vm.createShop(shopName, address, phone) }, modifier = Modifier.fillMaxWidth()) { Text("Save shop") }
        if (vm.state.user?.role == "owner" && vm.state.shops.isNotEmpty()) {
            SectionTitle("Staff", Icons.Filled.Person)
            Field("Name", staffName, Icons.Filled.Person) { staffName = it }
            Field("Username", username, Icons.Filled.Person) { username = it }
            Field("Password", password, Icons.Filled.Lock, secret = true) { password = it }
            vm.state.shops.forEach { shop ->
                Choice(shop.name, Icons.Filled.Store, picked[shop.id] == true, Modifier.fillMaxWidth()) {
                    picked[shop.id] = picked[shop.id] != true
                }
            }
            Button(onClick = {
                vm.createStaff(staffName, username, password, picked.filterValues { it }.keys.toList())
            }, modifier = Modifier.fillMaxWidth()) { Text("Add staff") }
        }
    }
}

@Composable
private fun MethodPicker(method: String, onChange: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Choice("Cash", Icons.Filled.Payments, method == "cash", Modifier.weight(1f)) { onChange("cash") }
        Choice("UPI", Icons.Filled.QrCode2, method == "upi", Modifier.weight(1f)) { onChange("upi") }
        Choice("Other", Icons.Filled.GridView, method == "other", Modifier.weight(1f)) { onChange("other") }
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    icon: ImageVector,
    secret: Boolean = false,
    number: Boolean = false,
    onChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        leadingIcon = { Icon(icon, contentDescription = null) },
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        singleLine = true,
        visualTransformation = if (secret) PasswordVisualTransformation() else VisualTransformation.None,
        keyboardOptions = KeyboardOptions(keyboardType = if (number) KeyboardType.Decimal else KeyboardType.Text),
    )
}
