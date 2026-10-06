from books.money import today_ist


def shop_context(request):
    return {
        "shop": getattr(request, "shop", None),
        "shops": getattr(request, "shops", []),
        "nav": getattr(request, "nav", ""),
        "today": today_ist(),
    }
