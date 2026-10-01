from celery.schedules import crontab


def cron(expr: str) -> crontab:
    """Standard 5-field cron string -> Celery crontab."""
    minute, hour, day_of_month, month_of_year, day_of_week = expr.split()
    return crontab(
        minute=minute, hour=hour, day_of_month=day_of_month,
        month_of_year=month_of_year, day_of_week=day_of_week,
    )