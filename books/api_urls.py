from django.urls import path

from books import api

urlpatterns = [
    path("health", api.health),
    path("auth/status", api.auth_status),
    path("auth/setup", api.auth_setup),
    path("auth/login", api.auth_login),
    path("auth/logout", api.auth_logout),
    path("auth/me", api.auth_me),
    path("shops", api.shops),
    path("users", api.users),
    path("items", api.items),
    path("items/<int:item_id>", api.item_update),
    path("vendors", api.vendors),
    path("shops/<int:shop_id>/stock", api.stock),
    path("shops/<int:shop_id>/stock/adjust", api.stock_adjust),
    path("shops/<int:shop_id>/customers", api.customers),
    path("shops/<int:shop_id>/purchases", api.purchases),
    path("shops/<int:shop_id>/purchases/<int:purchase_id>", api.purchase_detail),
    path("shops/<int:shop_id>/bills", api.bills),
    path("shops/<int:shop_id>/bills/<int:bill_id>", api.bill_detail),
    path("shops/<int:shop_id>/today", api.today),
    path("shops/<int:shop_id>/wallet", api.wallet),
]
