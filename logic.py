"""Pure functions for MTA arrival logic. Desktop-testable (no hardware deps)."""

from datetime import datetime


def get_arrival_in_minutes_from_now(now, date_str):
    train_date = datetime.fromisoformat(date_str).replace(tzinfo=None)
    return round((train_date - now).total_seconds() / 60.0)


def filter_arrivals(now, time_strings):
    minutes = [get_arrival_in_minutes_from_now(now, t) for t in time_strings]
    return [m for m in minutes if m >= 0]


def format_arrival_triple(minutes_list):
    v0 = str(minutes_list[0]) if len(minutes_list) > 0 else '-'
    v1 = str(minutes_list[1]) if len(minutes_list) > 1 else '-'
    v2 = str(minutes_list[2]) if len(minutes_list) > 2 else '-'
    return v0, v1, v2
