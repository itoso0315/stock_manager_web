import calendar
from datetime import date, timedelta

import holidays


EVENT_STYLES = {
    "last_day": ("権利付最終", "#16803c"),
    "ex_date": ("権利落ち", "#c2413b"),
    "record_date": ("権利確定", "#2563eb"),
}


def is_exchange_business_day(value):
    if value.weekday() >= 5 or value in holidays.JP(years=[value.year]):
        return False
    return not ((value.month == 1 and value.day in (2, 3)) or (value.month == 12 and value.day == 31))


def previous_business_day(value):
    value -= timedelta(days=1)
    while not is_exchange_business_day(value):
        value -= timedelta(days=1)
    return value


def rights_dates(year, month):
    record_date = date(year, month, calendar.monthrange(year, month)[1])
    ex_date = previous_business_day(record_date)
    last_day = previous_business_day(ex_date)
    return {"last_day": last_day, "ex_date": ex_date, "record_date": record_date}


def build_month_events(stocks, year, month):
    events = {}
    dates = rights_dates(year, month)
    for stock in stocks:
        if stock.get("shares", 0) <= 0 or month not in stock.get("dividend_months", []):
            continue
        for event_type, event_date in dates.items():
            events.setdefault(event_date, []).append({
                "type": event_type,
                "name": stock["name"],
                "code": stock["code"],
            })
    return events
