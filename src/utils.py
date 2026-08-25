import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def is_first_friday_of_month(date: datetime = None) -> bool:
    """Check if given date is the first Friday of its month"""
    if date is None:
        date = datetime.now()
    
    # Friday is weekday 4 (Monday=0)
    if date.weekday() != 4:
        return False
    
    # Check if this Friday is in the first week (1-7)
    return 1 <= date.day <= 7

def get_this_month_first_friday() -> datetime:
    """Get the date of the first Friday of the current month"""
    today = datetime.now()
    year = today.year
    month = today.month
    
    # Start from the first day of the month
    first_day = datetime(year, month, 1)
    
    # Find the first Friday
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)
    
    return first_friday


def format_alert_content(alert_type, details):
    if alert_type == "deforestation":
        return f"Alert: Deforestation detected! Details: {details}"
    elif alert_type == "built_area":
        return f"Alert: Built area expansion detected! Details: {details}"
    elif alert_type == "land_cover":
        return f"Alert: Land cover change detected! Details: {details}"
    else:
        return "Unknown alert type."

def validate_email(email):
    import re
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def prepare_email_body(template, context):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('src/templates'))
    template = env.get_template(template)
    return template.render(context)