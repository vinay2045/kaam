import json
from datetime import timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Max, Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import Seller, Product, Order, OrderItem, Notification, ContactMessage


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_seller(request):
    if not request.user.is_authenticated:
        return None
    if not hasattr(request, '_seller_cache'):
        try:
            request._seller_cache = request.user.seller
        except Exception:
            request._seller_cache = None
    return request._seller_cache

def get_unread_count(request):
    seller = get_seller(request)
    if not seller:
        return 0
    if not hasattr(request, '_unread_count_cache'):
        request._unread_count_cache = seller.notifications.filter(is_read=False).count()
    return request._unread_count_cache

def require_seller(view_func):
    def wrapper(request, *args, **kwargs):
        seller = get_seller(request)
        if not seller:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────

def landing(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id', '').strip()
        if order_id:
            return redirect('trace_order_detail', order_id=order_id)
    return render(request, 'landing/index.html')


def contact_us(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        if name and email and message:
            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message
            )
            messages.success(request, 'Your message was successfully received.')
            return redirect('contact')
            
    return render(request, 'landing/contact.html')


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def seller_login(request):
    if request.user.is_authenticated:
        if get_seller(request):
            return redirect('dashboard')
        if request.user.is_superuser:
            from django.conf import settings
            admin_url = getattr(settings, 'ADMIN_URL', 'admin/')
            if not admin_url.startswith('/'):
                admin_url = '/' + admin_url
            return redirect(admin_url)
        logout(request)
        return redirect('login')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            try:
                seller = user.seller
                if not seller.is_active:
                    messages.error(request, 'Your account has been suspended. Contact support.')
                    return render(request, 'auth/login.html')
                if not seller.subscription_active:
                    messages.error(request, 'Your subscription has expired. Contact support to renew.')
                    return render(request, 'auth/login.html')
                login(request, user)
                return redirect('dashboard')
            except Seller.DoesNotExist:
                if user.is_superuser:
                    login(request, user)
                    from django.conf import settings
                    admin_url = getattr(settings, 'ADMIN_URL', 'admin/')
                    if not admin_url.startswith('/'):
                        admin_url = '/' + admin_url
                    return redirect(admin_url)
                else:
                    messages.error(request, 'No seller account found. Contact support.')
        else:
            messages.error(request, 'Incorrect username or password.')
    return render(request, 'auth/login.html')


def seller_logout(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@require_seller
def dashboard(request):
    seller = get_seller(request)
    tab = request.GET.get('tab', 'new')

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    all_orders = seller.orders.all()
    new_orders = all_orders.filter(status__iexact='placed', is_confirmed=False)
    pending_orders = all_orders.filter(is_confirmed=True).exclude(status__iexact='delivered')
    completed_orders = all_orders.filter(status__iexact='delivered').exclude(return_status__in=['requested', 'approved'])
    return_orders = all_orders.filter(return_status__in=['requested', 'approved']).order_by('-updated_at')

    import urllib.parse

    if tab == 'new':
        orders = new_orders
    elif tab == 'pending':
        orders = pending_orders
    elif tab == 'completed':
        orders = completed_orders
    elif tab == 'returns':
        orders = return_orders
    else:
        orders = all_orders

    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_q:
        orders = orders.filter(
            Q(buyer_name__icontains=search_q) |
            Q(buyer_whatsapp__icontains=search_q) |
            Q(buyer_email__icontains=search_q) |
            Q(order_id__icontains=search_q) |
            Q(items__product__product_id__icontains=search_q) |
            Q(items__product_title__icontains=search_q)
        ).distinct()
    
    if status_filter:
        orders = orders.filter(status=status_filter)

    # OPTIMIZATION: Combine multiple DB counts/sums into a single TRIP
    stats = all_orders.aggregate(
        monthly_revenue=Sum('total_amount', filter=Q(status__iexact='delivered', created_at__gte=month_start) & ~Q(return_status='refunded')),
        monthly_orders_count=Count('id', filter=Q(created_at__gte=month_start)),
        packed_count=Count('id', filter=Q(status__iexact='packed')),
        shipped_count=Count('id', filter=Q(status__iexact='shipped')),
        out_count=Count('id', filter=Q(status__iexact='out_for_delivery')),
        delivered_count=Count('id', filter=Q(status__iexact='delivered'))
    )

    monthly_revenue = stats['monthly_revenue'] or 0
    monthly_orders = stats['monthly_orders_count'] or 0
    packed_count = stats['packed_count'] or 0
    shipped_count = stats['shipped_count'] or 0
    out_count = stats['out_count'] or 0
    delivered_count = stats['delivered_count'] or 0

    notifications = seller.notifications.filter(is_read=False).order_by('-created_at')[:5]

    page_num = request.GET.get('page', '1')
    per_page_raw = request.GET.get('per_page', '25')
    try:
        per_page = int(per_page_raw)
    except (TypeError, ValueError):
        per_page = 25
    per_page = max(5, min(per_page, 100))
    orders_paginator = Paginator(orders, per_page)
    page_obj = orders_paginator.get_page(page_num)

    context = {
        'seller': seller,
        'tab': tab,
        'search_q': search_q,
        'status_filter': status_filter,
        'orders': page_obj.object_list,
        'page_obj': page_obj,
        'orders_paginator': orders_paginator,
        'per_page': per_page,
        'order_counts': {
            'new': new_orders.count(),
            'pending': pending_orders.count(),
            'completed': completed_orders.count(),
            'returns': return_orders.count(),
            'all': all_orders.count(),
        },
        'stats': {
            'monthly_revenue': monthly_revenue,
            'monthly_orders': monthly_orders,
            'packed': packed_count,
            'shipped': shipped_count,
            'out_for_delivery': out_count,
            'delivered': delivered_count,
        },
        'notifications': notifications,
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/index.html', context)


@require_seller
def confirm_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    seller = get_seller(request)
    order = get_object_or_404(Order, order_id=order_id, seller=seller)
    order.is_confirmed = True
    order.confirmed_at = timezone.now()
    order.status = 'confirmed'
    order.save()
    return JsonResponse({'success': True, 'order_id': order_id})


@require_seller
def delete_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    seller = get_seller(request)
    order = get_object_or_404(Order, order_id=order_id, seller=seller)
    deleted_order_id = order.order_id
    order.delete()
    return JsonResponse({'success': True, 'order_id': deleted_order_id})


@require_seller
def order_detail(request, order_id):
    seller = get_seller(request)
    order = get_object_or_404(Order, order_id=order_id, seller=seller)
    return render(request, 'dashboard/order_detail.html', {
        'seller': seller,
        'order': order,
        'unread_count': seller.notifications.filter(is_read=False).count(),
    })


@require_seller
def bulk_delete_orders(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    seller = get_seller(request)
    order_ids = request.POST.getlist('order_ids[]') or request.POST.getlist('order_ids')
    queryset = seller.orders.all()

    if order_ids:
        queryset = queryset.filter(order_id__in=order_ids)
    else:
        tab = request.POST.get('tab', 'all')
        search_q = request.POST.get('q', '').strip()
        status_filter = request.POST.get('status', '').strip()

        if tab == 'new':
            queryset = queryset.filter(status__iexact='placed', is_confirmed=False)
        elif tab == 'pending':
            queryset = queryset.filter(is_confirmed=True).exclude(status__iexact='delivered')
        elif tab == 'completed':
            queryset = queryset.filter(status__iexact='delivered').exclude(return_status__in=['requested', 'approved'])
        elif tab == 'returns':
            queryset = queryset.filter(return_status__in=['requested', 'approved'])

        if search_q:
            queryset = queryset.filter(
                Q(buyer_name__icontains=search_q) |
                Q(buyer_whatsapp__icontains=search_q) |
                Q(buyer_email__icontains=search_q) |
                Q(order_id__icontains=search_q) |
                Q(items__product__product_id__icontains=search_q) |
                Q(items__product_title__icontains=search_q)
            ).distinct()
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

    count = queryset.count()
    queryset.delete()
    return JsonResponse({'success': True, 'deleted_count': count})


@require_seller
def update_order_status(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    seller = get_seller(request)
    order = get_object_or_404(Order, order_id=order_id, seller=seller)
    new_status = request.POST.get('status')

    valid = ['confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']
    if new_status not in valid:
        return JsonResponse({'success': False, 'error': 'Invalid status'})

    order.status = new_status
    if new_status == 'delivered':
        order.is_confirmed = True
        if order.payment_method == 'cod':
            order.payment_status = 'paid'
        elif order.payment_method == 'online' and (order.utr_number or order.payment_screenshot):
            order.payment_status = 'paid'
    order.save()

    status_labels = dict(Order.STATUS_CHOICES)
    return JsonResponse({
        'success': True,
        'new_status': new_status,
        'status_label': status_labels.get(new_status, new_status),
    })

@require_seller
def update_return_status(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    seller = get_seller(request)
    order = get_object_or_404(Order, order_id=order_id, seller=seller)
    action = request.POST.get('action')
    note = request.POST.get('note', '')

    if action == 'approve':
        order.return_status = 'approved'
    elif action == 'decline':
        order.return_status = 'declined'
        order.return_declined_reason = note
    elif action == 'refunded':
        order.return_status = 'refunded'
    elif action == 'exchanged':
        order.return_status = 'exchanged'
        order.status = 'confirmed' # Push back to pending

        # Update order details with the new selected variant
        if order.return_exchange_variant:
            item = order.items.first()
            if item:
                new_var = order.return_exchange_variant.split('—')[-1].strip() if '—' in order.return_exchange_variant else order.return_exchange_variant
                item.selected_size_color = new_var + " (Exchange Replacement)"
                item.save()
    else:
        return JsonResponse({'success': False, 'error': 'Invalid status'})
        
    order.save()
    return JsonResponse({'success': True, 'reload': True})

# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────

@require_seller
def product_list(request):
    seller = get_seller(request)
    products = seller.products.all()
    q = request.GET.get('q', '')
    category = request.GET.get('category', '')

    if q:
        products = products.filter(
            Q(title__icontains=q) | Q(category__icontains=q) | Q(subcategory__icontains=q) | Q(product_id__icontains=q)
        )
    if category:
        products = products.filter(category__iexact=category)

    categories = seller.products.values_list('category', flat=True).distinct()

    page = int(request.GET.get('page', 1))
    per_page = 20
    total = products.count()
    products = products[(page - 1) * per_page: page * per_page]

    context = {
        'seller': seller,
        'products': products,
        'categories': categories,
        'q': q,
        'category': category,
        'page': page,
        'total': total,
        'has_prev': page > 1,
        'has_next': (page * per_page) < total,
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/products.html', context)


@require_seller
def product_add(request):
    seller = get_seller(request)
    if request.method == 'POST':
        image = request.FILES.get('image')
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', '').strip()
        subcategory = request.POST.get('subcategory', '').strip()
        price_str = request.POST.get('price', '').strip()
        variants_json_str = request.POST.get('variants_json', '[]').strip()

        errors = []
        if not image:
            errors.append('Product image is required.')
        if not title:
            errors.append('Product title is required.')
        if not category:
            errors.append('Category is required.')
        if not subcategory:
            errors.append('Subcategory is required.')
        try:
            price = float(price_str)
            if price <= 0:
                errors.append('Price must be greater than 0.')
        except (ValueError, TypeError):
            errors.append('Enter a valid price.')
            price = None
            
        try:
            parsed_variants = json.loads(variants_json_str)
            if not isinstance(parsed_variants, list) or len(parsed_variants) == 0:
                errors.append('Please add at least one stock entry or variant.')
        except json.JSONDecodeError:
            errors.append('Invalid variants data. Please try adding variants again.')
            parsed_variants = []

        if errors:
            context = {
                'seller': seller, 'errors': errors,
                'form_data': request.POST, 'mode': 'add',
                'unread_count': seller.notifications.filter(is_read=False).count(),
            }
            return render(request, 'dashboard/product_form.html', context)

        product = Product.objects.create(
            seller=seller, image=image, title=title, category=category,
            subcategory=subcategory, price=price,
            size_color_raw='',  # Deprecated
            variants_json=json.dumps(parsed_variants),
        )
        messages.success(request, f'"{title}" added successfully.')
        return redirect('product_list')

    context = {
        'seller': seller, 'mode': 'add',
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/product_form.html', context)


@require_seller
def product_edit(request, pk):
    seller = get_seller(request)
    product = get_object_or_404(Product, pk=pk, seller=seller)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', '').strip()
        subcategory = request.POST.get('subcategory', '').strip()
        price_str = request.POST.get('price', '').strip()
        variants_json_str = request.POST.get('variants_json', '[]').strip()
        is_available = request.POST.get('is_available') == 'on'

        errors = []
        if not title:
            errors.append('Product title is required.')
        try:
            price = float(price_str)
            if price <= 0:
                errors.append('Price must be greater than 0.')
        except (ValueError, TypeError):
            errors.append('Enter a valid price.')
            price = None

        try:
            parsed_variants = json.loads(variants_json_str)
            if not isinstance(parsed_variants, list) or len(parsed_variants) == 0:
                errors.append('Please add at least one stock entry or variant.')
        except json.JSONDecodeError:
            errors.append('Invalid variants data. Please try adding variants again.')
            parsed_variants = []

        if errors:
            context = {
                'seller': seller, 'product': product, 'errors': errors,
                'form_data': request.POST, 'mode': 'edit',
                'unread_count': seller.notifications.filter(is_read=False).count(),
            }
            return render(request, 'dashboard/product_form.html', context)

        product.title = title
        product.category = category
        product.subcategory = subcategory
        product.price = price
        product.is_available = is_available
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        
        product.size_color_raw = ''
        product.variants_json = json.dumps(parsed_variants)
        product.save()
        messages.success(request, f'"{title}" updated successfully.')
        return redirect('product_list')

    context = {
        'seller': seller, 'product': product, 'mode': 'edit',
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/product_form.html', context)


@require_seller
def product_delete(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    seller = get_seller(request)
    product = get_object_or_404(Product, pk=pk, seller=seller)
    title = product.title
    product.delete()
    return JsonResponse({'success': True, 'title': title})

@require_seller
def bulk_delete_products(request):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    seller = get_seller(request)
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        if not product_ids:
            return JsonResponse({'success': False, 'error': 'No products selected.'})
        
        products = seller.products.filter(pk__in=product_ids)
        count = products.count()
        products.delete()
        return JsonResponse({'success': True, 'count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

@require_seller
def analytics(request):
    seller = get_seller(request)
    now = timezone.now()

    period_days = int(request.GET.get('period', 30))
    period_start = now - timedelta(days=period_days)
    prev_start = period_start - timedelta(days=period_days)

    orders_this = seller.orders.filter(created_at__gte=period_start)
    orders_prev = seller.orders.filter(created_at__gte=prev_start, created_at__lt=period_start)

    delivered_orders_this = orders_this.filter(status='delivered')
    delivered_orders_prev = orders_prev.filter(status='delivered')
    total_revenue = delivered_orders_this.aggregate(t=Sum('total_amount'))['t'] or 0
    prev_revenue = delivered_orders_prev.aggregate(t=Sum('total_amount'))['t'] or 0
    revenue_change = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue else 0

    total_orders = orders_this.count()
    prev_orders = orders_prev.count()
    orders_change = ((total_orders - prev_orders) / prev_orders * 100) if prev_orders else 0

    # Delivery counts
    all_orders = seller.orders.all()
    packed_count = all_orders.filter(status='packed').count()
    shipped_count = all_orders.filter(status='shipped').count()
    out_count = all_orders.filter(status='out_for_delivery').count()
    delivered_count = all_orders.filter(status='delivered').count()

    # Dynamic Charts based on period
    import math
    daily_orders = []
    daily_revenue = []

    if period_days <= 31:
        # Group by 1 day
        for i in range(period_days):
            start = period_start + timedelta(days=i)
            end = start + timedelta(days=1)
            lbl = start.strftime('%d %b')
            qs = seller.orders.filter(created_at__gte=start, created_at__lt=end)
            daily_orders.append({'day': lbl, 'count': qs.count()})
            rev = qs.filter(status='delivered').aggregate(t=Sum('total_amount'))['t'] or 0
            daily_revenue.append({'day': lbl, 'amount': float(rev)})

    elif period_days <= 90:
        # Group by 7 days
        points = math.ceil(period_days / 7.0)
        for i in range(points):
            start = period_start + timedelta(days=i*7)
            end = min(now, start + timedelta(days=7))
            lbl = start.strftime('%d %b') + ' - ' + end.strftime('%d %b')
            qs = seller.orders.filter(created_at__gte=start, created_at__lt=end)
            daily_orders.append({'day': lbl, 'count': qs.count()})
            rev = qs.filter(status='delivered').aggregate(t=Sum('total_amount'))['t'] or 0
            daily_revenue.append({'day': lbl, 'amount': float(rev)})
            
    else:
        # Group by 30 days
        points = math.ceil(period_days / 30.0)
        for i in range(points):
            start = period_start + timedelta(days=i*30)
            end = min(now, start + timedelta(days=30))
            lbl = start.strftime('%b') + ' ' + start.strftime('%d')
            qs = seller.orders.filter(created_at__gte=start, created_at__lt=end)
            daily_orders.append({'day': lbl, 'count': qs.count()})
            rev = qs.filter(status='delivered').aggregate(t=Sum('total_amount'))['t'] or 0
            daily_revenue.append({'day': lbl, 'amount': float(rev)})


    # Category analytics
    from django.db.models import F
    items_qs = OrderItem.objects.filter(order__seller=seller, order__created_at__gte=period_start, order__status='delivered')
    cat_data = {}
    for item in items_qs.select_related('order'):
        key = (item.product_category, item.product_subcategory)
        if key not in cat_data:
            cat_data[key] = {'count': 0, 'revenue': 0}
        cat_data[key]['count'] += item.quantity
        cat_data[key]['revenue'] += float(item.subtotal)
    top_categories = sorted(
        [{'category': k[0], 'subcategory': k[1], 'count': v['count'], 'revenue': v['revenue']}
         for k, v in cat_data.items()],
        key=lambda x: x['count'], reverse=True
    )
    total_items = sum(c['count'] for c in top_categories)
    for c in top_categories:
        c['pct'] = round(c['count'] / total_items * 100) if total_items else 0

    # Business summary
    delivered_orders_count = delivered_orders_this.count()
    avg_order_value = (total_revenue / delivered_orders_count) if delivered_orders_count else 0
    biggest_sale_obj = delivered_orders_this.order_by('-total_amount').first()
    biggest_sale = biggest_sale_obj.total_amount if biggest_sale_obj else 0
    biggest_sale_date = biggest_sale_obj.created_at.strftime('%d %b %Y') if biggest_sale_obj else '-'
    days_active = max((now - seller.created_at).days, 1)
    all_revenue = seller.orders.filter(status='delivered').aggregate(t=Sum('total_amount'))['t'] or 0
    daily_earnings = float(all_revenue) / days_active

    # Payments
    payment_orders = delivered_orders_this
    online_paid = payment_orders.filter(payment_method='online', payment_status='paid')
    cod_orders = payment_orders.filter(payment_method='cod', payment_status='pending')
    online_paid_count = online_paid.count()
    online_paid_amount = online_paid.aggregate(t=Sum('total_amount'))['t'] or 0
    cod_pending_count = cod_orders.count()
    cod_pending_amount = cod_orders.aggregate(t=Sum('total_amount'))['t'] or 0

    # Best selling products
    product_sales = {}
    for item in items_qs:
        pid = item.product_id or item.product_title
        if pid not in product_sales:
            product_sales[pid] = {
                'title': item.product_title,
                'category': item.product_category,
                'subcategory': item.product_subcategory,
                'count': 0, 'revenue': 0,
                'image_url': item.product_image_url
            }
        product_sales[pid]['count'] += item.quantity
        product_sales[pid]['revenue'] += float(item.subtotal)
    best_products = sorted(product_sales.values(), key=lambda x: x['count'], reverse=True)[:5]

    # Products never ordered
    ordered_product_ids = set(
        items_qs.values_list('product_id', flat=True).distinct()
    )
    products_never_ordered = seller.products.filter(
        is_available=True
    ).exclude(id__in=ordered_product_ids)[:5]

    # Buyer insights
    repeat_buyers = (
        orders_this.values('buyer_whatsapp', 'buyer_name')
        .annotate(order_count=Count('id'))
        .filter(order_count__gte=2)
        .order_by('-order_count')[:5]
    )
    avg_feedback = orders_this.filter(
        feedback_stars__isnull=False
    ).aggregate(avg=Avg('feedback_stars'))['avg']
    not_received_count = orders_this.filter(is_received=False).count()

    # Recent feedbacks
    recent_feedbacks = orders_this.filter(
        feedback_stars__isnull=False
    ).order_by('-created_at')[:5]

    # Star breakdown
    star_breakdown = {}
    for i in range(1, 6):
        star_breakdown[i] = orders_this.filter(feedback_stars=i).count()

    # Not received orders
    not_received_orders = orders_this.filter(is_received=False).order_by('-created_at')[:5]

    context = {
        'seller': seller,
        'period_days': period_days,
        'total_revenue': float(total_revenue),
        'revenue_change': revenue_change,
        'total_orders': total_orders,
        'orders_change': orders_change,
        'avg_feedback': avg_feedback,
        'items_sold': items_qs.aggregate(t=Sum('quantity'))['t'] or 0,
        'packed_count': packed_count,
        'shipped_count': shipped_count,
        'out_count': out_count,
        'delivered_count': delivered_count,
        'daily_orders': daily_orders,
        'daily_revenue': daily_revenue,
        'top_categories': top_categories[:8],
        'avg_order_value': float(avg_order_value),
        'biggest_sale': float(biggest_sale),
        'biggest_sale_date': biggest_sale_date,
        'daily_earnings': daily_earnings,
        'online_paid_count': online_paid_count,
        'online_paid_amount': float(online_paid_amount),
        'cod_pending_count': cod_pending_count,
        'cod_pending_amount': float(cod_pending_amount),
        'best_products': best_products,
        'products_never_ordered': products_never_ordered,
        'repeat_buyers': repeat_buyers,
        'star_breakdown': star_breakdown,
        'not_received_count': not_received_count,
        'not_received_orders': not_received_orders,
        'recent_feedbacks': recent_feedbacks,
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/analytics.html', context)


def repeat_queries_len(qs):
    return len(list(qs))


# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────

@require_seller
def seller_settings(request):
    seller = get_seller(request)
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'profile':
            business_name = request.POST.get('business_name', '').strip()
            username = request.POST.get('username', '').strip().lower()
            instagram = request.POST.get('instagram_link', '').strip()
            facebook = request.POST.get('facebook_link', '').strip()
            whatsapp = request.POST.get('whatsapp_number', '').strip()
            upi_id = request.POST.get('upi_id', '').strip()
            category = request.POST.get('category', '').strip()

            errors = []
            if not business_name:
                errors.append('Business name is required.')
            if not username or len(username) < 3:
                errors.append('Username must be at least 3 characters.')
            if not username.replace('-', '').isalnum():
                errors.append('Username can only contain letters, numbers, and hyphens.')
            if username != seller.username and Seller.objects.filter(username=username).exists():
                errors.append('This username is already taken.')

            if errors:
                context = {
                    'seller': seller, 'errors': errors,
                    'unread_count': seller.notifications.filter(is_read=False).count(),
                }
                return render(request, 'dashboard/settings.html', context)

            old_username = seller.username
            seller.business_name = business_name
            seller.username = username
            seller.instagram_link = instagram
            seller.facebook_link = facebook
            seller.whatsapp_number = whatsapp
            seller.upi_id = upi_id
            seller.category = category
            seller.save()
            messages.success(request, 'Profile updated successfully.')

        elif action == 'password':
            current_pw = request.POST.get('current_password', '')
            new_pw = request.POST.get('new_password', '')
            confirm_pw = request.POST.get('confirm_password', '')
            user = request.user

            if not user.check_password(current_pw):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_pw) < 8:
                messages.error(request, 'New password must be at least 8 characters.')
            elif new_pw != confirm_pw:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_pw)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Password updated successfully.')

    context = {
        'seller': seller,
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/settings.html', context)


# ─────────────────────────────────────────────
# FEEDBACKS
# ─────────────────────────────────────────────

@require_seller
def feedbacks(request):
    seller = get_seller(request)
    all_feedbacks = seller.orders.filter(feedback_stars__isnull=False).order_by('-created_at')
    issues = seller.orders.filter(is_received=False).order_by('-updated_at')
    avg_stars = all_feedbacks.aggregate(avg=Avg('feedback_stars'))['avg']
    star_breakdown = {i: all_feedbacks.filter(feedback_stars=i).count() for i in range(1, 6)}

    context = {
        'seller': seller,
        'feedbacks': all_feedbacks,
        'issues': issues,
        'avg_stars': avg_stars,
        'star_breakdown': star_breakdown,
        'total_feedbacks': all_feedbacks.count(),
        'unread_count': seller.notifications.filter(is_read=False).count(),
    }
    return render(request, 'dashboard/feedbacks.html', context)


# ─────────────────────────────────────────────
# STOREFRONT (BUYER)
# ─────────────────────────────────────────────

def storefront(request, username):
    # Prevent conflicting routes from reaching here
    reserved = ['login', 'logout', 'dashboard', 'trace', 'admin', 'api', 'static', 'media']
    if username in reserved:
        from django.http import Http404
        raise Http404

    try:
        seller = Seller.objects.get(username=username)
    except Seller.DoesNotExist:
        return render(request, 'storefront/store_inactive.html', {
            'message': 'Store not found.',
            'username': username,
        }, status=404)

    if not seller.is_active:
        return render(request, 'storefront/store_inactive.html', {
            'seller': seller,
            'message': 'This store is currently unavailable.',
        })

    if not seller.subscription_active:
        return render(request, 'storefront/store_inactive.html', {
            'seller': seller,
            'message': 'This store is temporarily unavailable.',
        })

    products = seller.products.filter(is_available=True)

    if request.method == 'POST':
        if 'data' in request.POST:
            try:
                data = json.loads(request.POST.get('data'))
            except Exception:
                return JsonResponse({'success': False, 'error': 'Invalid request format.'})
        else:
            try:
                data = json.loads(request.body)
            except Exception:
                return JsonResponse({'success': False, 'error': 'Invalid request.'})

        # Re-verify seller is still active
        seller.refresh_from_db()
        if not seller.is_active or not seller.subscription_active:
            return JsonResponse({'success': False, 'error': 'This store is currently unavailable.'})

        buyer = data.get('buyer', {})
        address = data.get('address', {})
        items_data = data.get('items', [])
        payment_method = data.get('payment_method', '')
        utr_number = data.get('utr_number', '')
        screenshot_file = request.FILES.get('payment_screenshot')

        if not items_data:
            return JsonResponse({'success': False, 'error': 'No products selected.'})
        if payment_method not in ['cod', 'online']:
            return JsonResponse({'success': False, 'error': 'Invalid payment method.'})

        # Duplicate check: same buyer + seller in last 60 seconds
        recent = Order.objects.filter(
            seller=seller,
            buyer_whatsapp=buyer.get('whatsapp', ''),
            created_at__gte=timezone.now() - timedelta(seconds=60)
        ).first()
        if recent:
            return JsonResponse({'success': True, 'order_id': recent.order_id})

        order = Order.objects.create(
            seller=seller,
            buyer_name=buyer.get('name', ''),
            buyer_email=buyer.get('email', ''),
            buyer_whatsapp=buyer.get('whatsapp', ''),
            buyer_instagram=buyer.get('instagram', ''),
            country=address.get('country', 'India'),
            address_line1=address.get('line1', ''),
            address_line2=address.get('line2', ''),
            city=address.get('city', ''),
            state=address.get('state', ''),
            pincode=address.get('pincode', ''),
            payment_method=payment_method,
            utr_number=utr_number,
            payment_status='paid' if (payment_method == 'online' and (utr_number or screenshot_file)) else 'pending',
        )
        
        if screenshot_file:
            order.payment_screenshot = screenshot_file
            order.save()

        total = 0
        for item_data in items_data:
            product_id = item_data.get('product_id')
            try:
                product = Product.objects.get(id=product_id, seller=seller, is_available=True)
            except Product.DoesNotExist:
                continue
            qty = max(1, int(item_data.get('qty', 1)))
            size_color = item_data.get('size_color', '')
            variant_label = item_data.get('variant_label', size_color)
            image_url = product.image.url if product.image else ''
            item = OrderItem(
                order=order,
                product=product,
                product_title=product.title,
                product_image_url=image_url,
                product_category=product.category,
                product_subcategory=product.subcategory,
                selected_size_color=variant_label or size_color,
                quantity=qty,
                unit_price=product.price,
                subtotal=product.price * qty,
            )
            item.save()
            total += float(product.price) * qty

            # Decrement stock for the chosen variant
            if product.variants_json and product.variants_json != '[]':
                try:
                    variants = json.loads(product.variants_json)
                    for v in variants:
                        if v.get('label') == variant_label:
                            v['stock'] = max(0, v.get('stock', 0) - qty)
                            break
                    product.variants_json = json.dumps(variants)
                    product.save(update_fields=['variants_json'])
                except Exception:
                    pass

        order.total_amount = total
        order.save()

        # Create notification for seller
        Notification.objects.create(
            seller=seller,
            message=f"New order from {order.buyer_name} — {order.order_id}",
            order=order,
        )

        # Send Real-Time Email to Buyer (if email provided)
        buyer_email = order.buyer_email
        if buyer_email:
            from django.core.mail import send_mail
            
            subject = f"Order Confirmed: #{order.order_id} - {seller.business_name}"
            
            # Construct a dynamic tracking URL based on current host
            host = request.get_host()
            trace_url = f"{request.scheme}://{host}/trace/{order.order_id}/"
            
            item_lines = "\n".join([f"- {it.quantity}x {it.product_title} (₹{float(it.unit_price)})" for it in order.items.all()])
            
            message = (
                f"Hi {order.buyer_name},\n\n"
                f"Thank you for your purchase from {seller.business_name}!\n\n"
                f"--- ORDER SUMMARY ---\n"
                f"Order ID: #{order.order_id}\n"
                f"Payment Method: {order.payment_method.upper()}\n"
                f"Total Amount: ₹{order.total_amount}\n\n"
                f"Items Ordered:\n{item_lines}\n\n"
                f"You can track the live shipping status of your order anytime here:\n"
                f"{trace_url}\n\n"
                f"Thank you,\n"
                f"Powered by Kaam Commerce"
            )
            
            # In production, ensure EMAIL_BACKEND and SMTP are configured in settings.py
            try:
                import os
                send_mail(
                    subject,
                    message,
                    os.environ.get('DEFAULT_FROM_EMAIL', 'orders@kaam.app'),
                    [buyer_email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Failed to send email: {e}")


        return JsonResponse({'success': True, 'order_id': order.order_id})

    products_data = {}
    for p in products:
        try:
            variants = json.loads(p.variants_json) if p.variants_json else []
        except Exception:
            variants = []
        products_data[str(p.id)] = {
            'id': p.id,
            'title': p.title,
            'category': p.category,
            'subcategory': p.subcategory,
            'price': float(p.price),
            'size_color_raw': p.size_color_raw,
            'variants': variants,
            'image_url': p.image.url if p.image else '',
        }

    context = {
        'seller': seller,
        'products': products,
        'products_json': json.dumps(products_data),
    }
    return render(request, 'storefront/store.html', context)


def order_placed(request, username, order_id):
    try:
        seller = Seller.objects.get(username=username)
    except Seller.DoesNotExist:
        from django.http import Http404
        raise Http404
    order = get_object_or_404(Order, order_id=order_id, seller=seller)
    return render(request, 'storefront/order_placed.html', {
        'seller': seller, 'order': order,
    })


# ─────────────────────────────────────────────
# ORDER TRACKING
# ─────────────────────────────────────────────

def trace_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id', '').strip()
        if order_id:
            return redirect('trace_order_detail', order_id=order_id)
    return render(request, 'trace/trace.html')


def trace_order_detail(request, order_id):
    try:
        order = Order.objects.get(order_id=order_id)
    except Order.DoesNotExist:
        return render(request, 'trace/trace.html', {
            'error': f'Order "{order_id}" not found. Check the ID and try again.',
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        from .models import Notification
        
        if action == 'mark_received' and order.status == 'delivered':
            order.is_received = True
            order.save()
            messages.success(request, 'Order marked as received! You can now leave a review.')
            
        elif action == 'feedback' and order.status == 'delivered' and order.is_received == True and order.feedback_stars is None:
            stars = request.POST.get('stars')
            text = request.POST.get('feedback_text', '')
            try:
                stars = int(stars)
                if 1 <= stars <= 5:
                    order.feedback_stars = stars
                    order.feedback_text = text
                    order.save()
                    messages.success(request, 'Thank you for your feedback!')
                    Notification.objects.create(
                        seller=order.seller,
                        order=order,
                        message=f"★ New {stars}-star review from {order.buyer_name} for order {order.order_id}"
                    )
            except (ValueError, TypeError):
                messages.error(request, 'Please select a star rating.')
                
        elif action == 'not_received' and order.status == 'delivered':
            reason = request.POST.get('reason', '')
            order.is_received = False
            order.not_received_reason = reason
            order.save()
            messages.success(request, 'Report submitted. The seller will be notified.')
            Notification.objects.create(
                seller=order.seller,
                order=order,
                message=f"⚠️ URGENT: {order.buyer_name} reported they did NOT receive order {order.order_id}. Reason: {reason}"
            )
            
        elif action == 'request_return' and order.status == 'delivered' and order.is_received == True:
            r_type = request.POST.get('return_type')
            if r_type in ['refund', 'exchange'] and not order.return_status:
                order.return_type = r_type
                order.return_reason = request.POST.get('return_reason', '')
                order.return_description = request.POST.get('return_description', '')
                order.return_exchange_variant = request.POST.get('return_exchange_variant', '')
                proof = request.FILES.get('return_proof')
                if proof:
                    order.return_proof_image = proof
                
                order.return_status = 'requested'
                order.save()
                
                type_label = 'Refund' if r_type == 'refund' else 'Exchange'
                messages.success(request, f'Your {type_label} request has been submitted for review.')
                Notification.objects.create(
                    seller=order.seller,
                    order=order,
                    message=f"🔄 {type_label} Requested: {order.buyer_name} requested a {r_type} for order {order.order_id}."
                )

        return redirect('trace_order_detail', order_id=order_id)

    status_order = ['placed', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']
    current_idx = status_order.index(order.status) if order.status in status_order else 0
    timeline = []
    for i, s in enumerate(status_order):
        label = dict(Order.STATUS_CHOICES).get(s, s)
        if i < current_idx:
            state = 'done'
        elif i == current_idx:
            state = 'current'
        else:
            state = 'future'
        timeline.append({'status': s, 'label': label, 'state': state})

    exchange_options = []
    if order and getattr(order, 'items', None):
        import json
        for item in order.items.all():
            if item.product and getattr(item.product, 'variants_json', None):
                try:
                    variants = json.loads(item.product.variants_json)
                    if isinstance(variants, list):
                        for v in variants:
                            label_parts = []
                            if v.get('color_flavor'):
                                label_parts.append(v['color_flavor'])
                            if v.get('size_weight'):
                                label_parts.append(v['size_weight'])
                            
                            label = " / ".join(label_parts) if label_parts else "Default"
                            stock = 0
                            try:
                                stock = float(v.get('stock', 0))
                            except ValueError:
                                pass
                                
                            if stock > 0:
                                opt_text = f"{item.product.title} — {label}"
                                # Only add if we don't have this exact label yet (simple deduplication)
                                if not any(o['value'] == opt_text for o in exchange_options):
                                    exchange_options.append({
                                        'value': opt_text,
                                        'label': f"{opt_text} ({int(stock)} left)"
                                    })
                except Exception:
                    pass

    context = {
        'order': order,
        'timeline': timeline,
        'exchange_options': exchange_options,
    }
    return render(request, 'trace/trace.html', context)


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@require_seller
def api_realtime_analytics(request):
    seller = get_seller(request)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    all_orders = seller.orders.all()
    new_orders = all_orders.filter(status='placed', is_confirmed=False)

    monthly_revenue = all_orders.filter(
        status='delivered', created_at__gte=month_start
    ).aggregate(t=Sum('total_amount'))['t'] or 0
    monthly_orders = all_orders.filter(created_at__gte=month_start).count()

    latest = new_orders.order_by('-created_at').first()

    return JsonResponse({
        'new_orders_count': new_orders.count(),
        'latest_order_id': latest.order_id if latest else None,
        'monthly_revenue': float(monthly_revenue),
        'monthly_orders': monthly_orders,
        'packed': all_orders.filter(status__iexact='packed').count(),
        'shipped': all_orders.filter(status__iexact='shipped').count(),
        'out_for_delivery': all_orders.filter(status__iexact='out_for_delivery').count(),
        'delivered': all_orders.filter(status__iexact='delivered').count(),
        'tabs': {
            'new': new_orders.count(),
            'pending': all_orders.filter(is_confirmed=True).exclude(status__iexact='delivered').count(),
            'completed': all_orders.filter(status__iexact='delivered').exclude(return_status__in=['requested', 'approved']).count(),
            'returns': all_orders.filter(return_status__in=['requested', 'approved']).count(),
            'all': all_orders.count()
        },
        'unread_count': seller.notifications.filter(is_read=False).count(),
        'notifications': [
            {'message': n.message, 'time': n.created_at.isoformat()} 
            for n in seller.notifications.filter(is_read=False).order_by('-created_at')[:5]
        ],
        'timestamp': now.isoformat(),
    })


@require_seller
def api_category_analytics(request):
    seller = get_seller(request)
    period = int(request.GET.get('period', 30))
    period_start = timezone.now() - timedelta(days=period)
    items_qs = OrderItem.objects.filter(
        order__seller=seller, order__created_at__gte=period_start
    )

    cat_data = {}
    for item in items_qs:
        cat = item.product_category
        sub = item.product_subcategory
        if cat not in cat_data:
            cat_data[cat] = {'count': 0, 'revenue': 0, 'subcategories': {}}
        cat_data[cat]['count'] += item.quantity
        cat_data[cat]['revenue'] += float(item.subtotal)
        if sub not in cat_data[cat]['subcategories']:
            cat_data[cat]['subcategories'][sub] = {'count': 0, 'revenue': 0}
        cat_data[cat]['subcategories'][sub]['count'] += item.quantity
        cat_data[cat]['subcategories'][sub]['revenue'] += float(item.subtotal)

    result = []
    for cat, data in cat_data.items():
        subs = [{'name': k, 'count': v['count'], 'revenue': v['revenue']}
                for k, v in data['subcategories'].items()]
        subs.sort(key=lambda x: x['count'], reverse=True)
        result.append({
            'name': cat,
            'count': data['count'],
            'revenue': data['revenue'],
            'subcategories': subs,
        })
    result.sort(key=lambda x: x['count'], reverse=True)
    return JsonResponse({'categories': result})


@require_seller
def api_notifications(request):
    seller = get_seller(request)
    notifs = seller.notifications.order_by('-created_at')[:5]
    data = [
        {
            'id': n.id,
            'message': n.message,
            'is_read': n.is_read,
            'order_id': n.order.order_id if n.order else None,
            'time': n.created_at.isoformat(),
        }
        for n in notifs
    ]
    return JsonResponse({
        'notifications': data,
        'unread_count': seller.notifications.filter(is_read=False).count(),
    })


@require_seller
@require_POST
def api_mark_notifications_read(request):
    seller = get_seller(request)
    seller.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@require_seller
def check_username(request):
    username = request.GET.get('username', '').strip().lower()
    if not username:
        return JsonResponse({'available': True, 'message': ''})
    
    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Too short (min 3 chars)'})
    
    import re
    if not re.match(r'^[a-zA-Z0-9\-]+$', username):
        return JsonResponse({'available': False, 'message': 'Alphanumeric & hyphens only'})

    seller = get_seller(request)
    exists = Seller.objects.filter(username=username)
    if seller:
        exists = exists.exclude(id=seller.id)
    
    if exists.exists():
        return JsonResponse({'available': False, 'message': '❌ Name already taken'})
    else:
        return JsonResponse({'available': True, 'message': '✅ Name is available'})


@require_seller
def export_orders(request):
    import csv
    from django.http import HttpResponse

    seller = get_seller(request)
    fmt = request.GET.get('format', 'csv').lower()
    orders = seller.orders.all().order_by('-created_at')

    if fmt == 'json':
        data = []
        for o in orders.prefetch_related('items'):
            items = []
            for item in o.items.all():
                items.append({
                    'product': item.product_title,
                    'variant': item.selected_size_color,
                    'qty': item.quantity,
                    'price': float(item.unit_price)
                })
            data.append({
                'order_id': o.order_id,
                'buyer_name': o.buyer_name,
                'buyer_whatsapp': o.buyer_whatsapp,
                'buyer_email': o.buyer_email,
                'buyer_instagram': o.buyer_instagram,
                'address': f"{o.address_line1}, {o.address_line2}, {o.city}, {o.state} - {o.pincode}",
                'status': o.status,
                'is_confirmed': o.is_confirmed,
                'total_amount': float(o.total_amount),
                'utr_number': o.utr_number,
                'items': items,
                'created_at': o.created_at.isoformat(),
            })
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="kaam_orders.json"'
        return response
    else:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="kaam_orders.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order ID', 'Date', 'Customer', 'WhatsApp', 'Email', 'Instagram',
            'Address Line 1', 'Address Line 2', 'City', 'State', 'Pincode', 
            'Items Ordered', 'Payment Method', 'UTR Number', 'Status', 'Confirmed', 'Total Amount'
        ])
        
        for o in orders.prefetch_related('items'):
            # Build item string: "1x Title (Variant), 2x Title..."
            item_list = []
            for item in o.items.all():
                product_token = item.product.product_id if item.product else item.product_title
                item_list.append(f"{item.quantity}x {product_token} ({item.selected_size_color})")
            items_str = " | ".join(item_list)

            writer.writerow([
                o.order_id,
                o.created_at.strftime('%Y-%m-%d %H:%M'),
                o.buyer_name,
                o.buyer_whatsapp,
                o.buyer_email,
                o.buyer_instagram,
                o.address_line1,
                o.address_line2,
                o.city,
                o.state,
                o.pincode,
                items_str,
                o.payment_method.upper(),
                o.utr_number,
                o.status.lower(),
                'Yes' if o.is_confirmed else 'No',
                o.total_amount
            ])
        return response

@require_seller
def export_analytics(request):
    import csv
    from django.http import HttpResponse

    seller = get_seller(request)
    fmt = request.GET.get('format', 'csv').lower()
    
    # Simple summary analytics
    all_orders = seller.orders.all()
    revenue = all_orders.filter(status='delivered').aggregate(t=Sum('total_amount'))['t'] or 0
    total_orders = all_orders.count()
    
    # Category summary
    items_qs = OrderItem.objects.filter(order__seller=seller)
    cat_summary = {}
    for item in items_qs:
        cat = item.product_category
        if cat not in cat_summary:
            cat_summary[cat] = {'units': 0, 'revenue': 0}
        cat_summary[cat]['units'] += item.quantity
        cat_summary[cat]['revenue'] += float(item.subtotal)

    if fmt == 'json':
        data = {
            'overall': {
                'total_revenue': float(revenue),
                'total_orders': total_orders,
            },
            'categories': cat_summary
        }
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="kaam_analytics.json"'
        return response
    else:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="kaam_analytics.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Analysis Category', 'Metric', 'Value'])
        writer.writerow(['Overall', 'Total Revenue', float(revenue)])
        writer.writerow(['Overall', 'Total Orders', total_orders])
        writer.writerow([])
        writer.writerow(['Product Category', 'Units Sold', 'Revenue (₹)'])
        for cat, vals in cat_summary.items():
            writer.writerow([cat, vals['units'], vals['revenue']])
            
        return response


@require_seller
@require_POST
def manual_order_create(request):
    seller = get_seller(request)
    
    # Customer Details
    name = request.POST.get('buyer_name')
    whatsapp = request.POST.get('buyer_whatsapp')
    email = request.POST.get('buyer_email', '')
    address = request.POST.get('address_line1')
    city = request.POST.get('city')
    state = request.POST.get('state')
    pincode = request.POST.get('pincode')
    
    # Order Meta
    status = request.POST.get('status', 'confirmed')
    payment_method = request.POST.get('payment_method', 'cod')
    utr_number = request.POST.get('utr_number', '').strip()
    payment_status = 'paid' if (payment_method == 'online' and utr_number) else 'pending'
    
    # Lists of items
    product_ids = request.POST.getlist('product_ids[]')
    variant_names = request.POST.getlist('variant_names[]')
    quantities = request.POST.getlist('quantities[]')

    if not all([name, whatsapp, address, city, pincode, product_ids]):
        messages.error(request, "Please fill all required shipping and item fields.")
        return redirect('dashboard')

    try:
        # Initial Order instance
        order = Order.objects.create(
            seller=seller,
            buyer_name=name,
            buyer_whatsapp=whatsapp,
            buyer_email=email,
            address_line1=address,
            city=city,
            state=state,
            pincode=pincode,
            status=status,
            payment_method=payment_method,
            payment_status=payment_status,
            utr_number=utr_number,
            is_confirmed=True,
            confirmed_at=timezone.now(),
            total_amount=0 # Will update after adding items
        )

        total_order_amount = 0
        
        for i in range(len(product_ids)):
            pid = product_ids[i]
            v_name = variant_names[i] if i < len(variant_names) else 'Standard'
            qty = int(quantities[i]) if i < len(quantities) else 1
            
            product = Product.objects.get(id=pid, seller=seller)
            subtotal = product.price * qty
            
            OrderItem.objects.create(
                order=order,
                product=product,
                product_title=product.title,
                product_image_url=product.image.url if product.image else '',
                product_category=product.category,
                product_subcategory=product.subcategory,
                selected_size_color=v_name,
                quantity=qty,
                unit_price=product.price,
                subtotal=subtotal
            )
            total_order_amount += subtotal
            
        # Update final total
        order.total_amount = total_order_amount
        order.save()
        
        messages.success(request, f"Manual Order {order_id} recorded successfully (Total: ₹{total_order_amount})")
    except Exception as e:
        messages.error(request, f"Error creating manual order: {str(e)}")

    return redirect('dashboard')

@require_seller
@require_POST
def import_orders_csv(request):
    import csv, io, json, re
    seller = get_seller(request)
    file = request.FILES.get('csv_file')
    tab_name = request.POST.get('target_status', 'new')
    
    # Map TAB names to internal STATUS names
    tab_to_status = {
        'new': 'placed',
        'pending': 'confirmed',
        'completed': 'delivered'
    }
    status_fallback = tab_to_status.get(tab_name, 'placed')

    if not file:
        messages.error(request, "No file uploaded")
        return redirect('dashboard')

    try:
        if file.name.endswith('.json'):
            rows = json.load(file)
        else:
            decoded_file = file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded_file))
            rows = list(reader)

        success_count = 0
        error_count = 0
        skip_details = []
        
        for idx, row in enumerate(rows, start=2): # Headers are Row 1, data starts at 2
            try:
                # Basic Identity
                name = row.get('Customer', '').strip()
                whatsapp = row.get('WhatsApp', '').strip()
                email = row.get('Email', '').strip()
                instagram = row.get('Instagram', '').strip()
                
                # Shipping
                addr1 = row.get('Address Line 1', '').strip()
                addr2 = row.get('Address Line 2', '').strip()
                city = row.get('City', '').strip()
                state = row.get('State', '').strip()
                pin = row.get('Pincode', '').strip()
                
                # Meta
                row_status_raw = row.get('Status', '').strip().lower()
                status_alias = {
                    'pending': 'confirmed',
                    'new': 'placed',
                    'order placed': 'placed',
                    'out for delivery': 'out_for_delivery',
                }
                row_status = status_alias.get(row_status_raw, row_status_raw) or status_fallback.lower()
                pay_method = row.get('Payment Method', 'COD').lower()
                utr = row.get('UTR Number', '').strip()
                total_val = row.get('Total Amount', '0').replace(',', '')
                
                if not any(row.values()): continue # skip actual empty rows

                if not all([name, whatsapp, addr1]):
                    error_count += 1
                    skip_details.append(f"Row {idx}: Missing Name, WhatsApp or Address")
                    continue

                # Everything is valid, let's create
                csv_order_id = row.get('Order ID', '').strip()
                if csv_order_id and not csv_order_id.startswith('ORD-'):
                    csv_order_id = None
                
                if csv_order_id and Order.objects.filter(order_id=csv_order_id, seller=seller).exists():
                    error_count += 1
                    skip_details.append(f"Row {idx}: Order {csv_order_id} already exists")
                    continue

                # Item Parsing Logic (STRICT PRODUCT ID ONLY)
                items_raw = row.get('Items Ordered', '')
                item_blocks = [b.strip() for b in items_raw.split('|')] if items_raw else []
                
                if not item_blocks:
                    error_count += 1
                    skip_details.append(f"Row {idx}: No items ordered")
                    continue

                order_valid = True
                parsed_items = []
                
                for block in item_blocks:
                    match = re.match(r'(\d+)x\s+(.*?)(?:\s+\((.*?)\))?$', block)
                    if match:
                        qty = int(match.group(1))
                        pid = match.group(2).strip()
                        variant = match.group(3).strip() if match.group(3) else 'Standard'
                        
                        product = seller.products.filter(product_id__iexact=pid, is_available=True).first()
                        if not product:
                            title_matches = seller.products.filter(title__iexact=pid, is_available=True)
                            title_count = title_matches.count()
                            if title_count == 1:
                                product = title_matches.first()
                            elif title_count > 1:
                                order_valid = False
                                skip_details.append(f"Row {idx}: '{pid}' matches multiple products, use Product ID in Items Ordered")
                                break
                        if not product:
                            order_valid = False
                            skip_details.append(f"Row {idx}: Product ID '{pid}' not found in your store")
                            break
                        
                        parsed_items.append({'product': product, 'qty': qty, 'variant': variant})
                    else:
                        order_valid = False
                        skip_details.append(f"Row {idx}: Invalid item format '{block}'")
                        break

                if not order_valid:
                    error_count += 1
                    continue

                conf_col = row.get('Confirmed', '').strip().lower()
                is_confirmed_from_col = conf_col in ['yes', 'true', '1', 'y']
                valid_statuses = ['placed', 'confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']
                row_status = row_status if row_status in valid_statuses else status_fallback.lower()
                status_implies_confirmed = row_status in ['confirmed', 'packed', 'shipped', 'out_for_delivery', 'delivered']
                is_confirmed = is_confirmed_from_col or status_implies_confirmed
                payment_status = 'paid' if ('online' in pay_method and utr) else 'pending'
                
                create_kwargs = {
                    'seller': seller,
                    'buyer_name': name,
                    'buyer_whatsapp': whatsapp,
                    'buyer_email': email,
                    'buyer_instagram': instagram,
                    'address_line1': addr1,
                    'address_line2': addr2,
                    'city': city,
                    'state': state,
                    'pincode': pin,
                    'status': row_status,
                    'payment_method': 'online' if 'online' in pay_method else 'cod',
                    'payment_status': payment_status,
                    'utr_number': utr,
                    'is_confirmed': is_confirmed,
                    'confirmed_at': timezone.now() if is_confirmed else None,
                    'total_amount': float(total_val or 0)
                }
                if csv_order_id:
                    create_kwargs['order_id'] = csv_order_id

                order = Order.objects.create(**create_kwargs)

                for pi in parsed_items:
                    p = pi['product']
                    OrderItem.objects.create(
                        order=order, product=p, product_title=p.title,
                        product_image_url=p.image.url if p.image else '',
                        product_category=p.category, product_subcategory=p.subcategory,
                        selected_size_color=pi['variant'], quantity=pi['qty'],
                        unit_price=p.price, subtotal=p.price * pi['qty']
                    )
                success_count += 1
            except Exception as e:
                error_count += 1
                skip_details.append(f"Row {idx}: Error - {str(e)}")

        # Final Feedback
        result_msg = f"Import Finished: {success_count} success, {error_count} skipped."
        if skip_details:
            result_msg += " Reasons: " + "; ".join(skip_details[:3])
            if len(skip_details) > 3: result_msg += " ..."
        
        if success_count > 0: messages.success(request, result_msg)
        else: messages.warning(request, result_msg)

    except Exception as e:
        messages.error(request, f"Bulk Import Error: {str(e)}")
        
    return redirect('dashboard')


# ─────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────

def error_404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)
