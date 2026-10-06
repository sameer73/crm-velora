from django import template

from books.money import format_inr, paise_to_input, pretty_date
from books.present import ledger_label

register = template.Library()


@register.filter
def inr(value):
    if value is None:
        return "—"
    return format_inr(int(value))


@register.filter
def input_paise(value):
    return paise_to_input(int(value or 0))


@register.filter
def pretty(value):
    return pretty_date(value)


@register.filter
def billno(value):
    return f"#{int(value):04d}"


@register.filter
def kind(value):
    return "Installation" if value == "job" else "Counter sale"


@register.filter
def entry_label(entry):
    return ledger_label(entry)


@register.filter
def qty_of(stock, item_id):
    return (stock or {}).get(item_id, 0)
