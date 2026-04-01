from django import template
import locale

register = template.Library()


@register.filter
def indian_currency(value):
    """Format number as Indian currency: ₹1,23,456"""
    try:
        value = float(value)
        s = f"{value:,.0f}"
        # Convert to Indian numbering: after first 3 from right, group by 2
        parts = s.split(',')
        if len(parts) > 1:
            # Rebuild with Indian grouping
            num = int(value)
            s = format_indian(num)
        return f"₹{s}"
    except (ValueError, TypeError):
        return value


def format_indian(n):
    n = int(n)
    s = str(abs(n))
    if len(s) <= 3:
        result = s
    else:
        result = s[-3:]
        s = s[:-3]
        while s:
            result = s[-2:] + ',' + result
            s = s[:-2]
    return ('-' if n < 0 else '') + result


@register.filter
def stars_range(value):
    """Return range for star rating"""
    try:
        return range(1, int(value) + 1)
    except (ValueError, TypeError):
        return range(0)


@register.filter
def empty_stars(value):
    try:
        return range(int(value) + 1, 6)
    except (ValueError, TypeError):
        return range(1, 6)


@register.filter
def timesince_short(value):
    from django.utils import timezone
    from datetime import timedelta
    if not value:
        return ''
    now = timezone.now()
    diff = now - value
    if diff < timedelta(minutes=1):
        return 'just now'
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    elif diff < timedelta(days=1):
        hrs = int(diff.total_seconds() / 3600)
        return f"{hrs}h ago"
    elif diff < timedelta(days=7):
        days = diff.days
        return f"{days}d ago"
    else:
        return value.strftime('%d %b')


@register.filter
def status_badge_class(status):
    mapping = {
        'placed': 'badge-new',
        'confirmed': 'badge-confirmed',
        'packed': 'badge-pending',
        'shipped': 'badge-shipped',
        'out_for_delivery': 'badge-out-delivery',
        'delivered': 'badge-delivered',
    }
    return mapping.get(status, 'badge-new')


@register.filter
def payment_badge_class(method):
    return 'badge-cod' if method == 'cod' else 'badge-online'


@register.simple_tag
def status_step_class(order_status, step_status):
    order = ['placed', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']
    try:
        current_idx = order.index(order_status)
        step_idx = order.index(step_status)
    except ValueError:
        return 'step-future'
    if step_idx < current_idx:
        return 'step-done'
    elif step_idx == current_idx:
        return 'step-current'
    else:
        return 'step-future'
