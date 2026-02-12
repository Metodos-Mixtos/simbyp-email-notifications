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