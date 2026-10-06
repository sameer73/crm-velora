from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.money import format_inr, paise_to_input, pretty_date

TEMPLATES = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES))
templates.env.filters["inr"] = format_inr
templates.env.filters["input_paise"] = paise_to_input
templates.env.filters["pretty"] = pretty_date
templates.env.filters["billno"] = lambda number: f"#{int(number):04d}"
templates.env.filters["kind"] = lambda kind: "Installation" if kind == "job" else "Counter sale"


def render(request, name: str, context: dict, status_code: int = 200):
    payload = {"request": request, **context}
    return templates.TemplateResponse(request, name, payload, status_code=status_code)
