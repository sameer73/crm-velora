from django.urls import path

from books import views

urlpatterns = [
    path("setup", views.setup_page, name="setup"),
    path("login", views.login_page, name="login"),
    path("logout", views.logout_page, name="logout"),
    path("shop", views.switch_shop, name="switch-shop"),
    path("", views.today, name="today"),
    path("inventory", views.inventory, name="inventory"),
    path("inventory/new", views.item_new, name="item-new"),
    path("inventory/<int:item_id>", views.item_page, name="item"),
    path("inventory/<int:item_id>/adjust", views.item_adjust, name="item-adjust"),
    path("vendors", views.vendors_page, name="vendors"),
    path("customers", views.customers_page, name="customers"),
    path("purchases", views.purchases_page, name="purchases"),
    path("purchases/new", views.purchase_new, name="purchase-new"),
    path("purchases/<int:purchase_id>", views.purchase_page, name="purchase"),
    path("purchases/<int:purchase_id>/pay", views.purchase_pay, name="purchase-pay"),
    path("sales/new", views.sale_new, name="sale-new"),
    path("jobs/new", views.job_new, name="job-new"),
    path("bills", views.bills_page, name="bills"),
    path("bills/<int:bill_id>", views.bill_page, name="bill"),
    path("bills/<int:bill_id>/pay", views.bill_pay, name="bill-pay"),
    path("bills/<int:bill_id>/payments/<int:entry_id>/remove", views.bill_unpay, name="bill-unpay"),
    path("wallet", views.wallet_page, name="wallet"),
    path("wallet/new", views.wallet_new, name="wallet-new"),
    path("more", views.more_page, name="more"),
    path("settings", views.settings_page, name="settings"),
    path("settings/shops", views.settings_shop, name="settings-shop"),
    path("settings/users", views.settings_user, name="settings-user"),
]
