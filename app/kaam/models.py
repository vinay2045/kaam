from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string
import secrets
import json

def generate_order_id():
    # 8-digit numeric ID (no prefix, no separators), retry on collision.
    for _ in range(25):
        candidate = str(secrets.randbelow(90000000) + 10000000)
        try:
            if not Order.objects.filter(order_id=candidate).exists():
                return candidate
        except Exception:
            # During startup/migrations table may not be queryable; return candidate.
            return candidate
    # Extremely unlikely fallback if many collisions happen.
    return str(secrets.randbelow(90000000) + 10000000)

def generate_product_id():
    return str(random.randint(1000, 9999))

class Seller(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller')
    username = models.SlugField(unique=True, max_length=50)
    business_name = models.CharField(max_length=200)
    instagram_link = models.URLField(blank=True)
    facebook_link = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20)
    upi_id = models.CharField(max_length=50, blank=True, null=True, help_text="Leave blank to default to whatsapp_number@upi")
    category = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    subscription_active = models.BooleanField(default=True)
    subscription_expires = models.DateField(null=True, blank=True)
    allow_online_payment = models.BooleanField(default=True)
    allow_cod = models.BooleanField(default=True)
    allow_refunds = models.BooleanField(default=True)
    allow_exchanges = models.BooleanField(default=True)
    order_delivery_days = models.PositiveSmallIntegerField(default=3)
    email = models.EmailField(blank=True, help_text="Business email for contact")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business_name} (@{self.username})"


class Product(models.Model):
    product_id = models.CharField(max_length=20, unique=True, default=generate_product_id, editable=False)
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='products')
    image = models.ImageField(upload_to='products/%Y/%m/')
    title = models.CharField(max_length=300)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size_color_raw = models.TextField(blank=True)
    variants_json = models.TextField(blank=True, default='[]', help_text="JSON list of parsed variants with stock counts")
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.seller.business_name}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Order Placed'),
        ('confirmed', 'Confirmed'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
    ]
    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('online', 'Online Payment'),
    ]

    order_id = models.CharField(max_length=50, unique=True, default=generate_order_id)
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='orders')

    buyer_name = models.CharField(max_length=200)
    buyer_email = models.EmailField()
    buyer_whatsapp = models.CharField(max_length=30)
    buyer_instagram = models.CharField(max_length=100, blank=True)

    country = models.CharField(max_length=100, default='India')
    address_line1 = models.TextField()
    address_line2 = models.TextField(blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    payment_status = models.CharField(max_length=20, default='pending')
    utr_number = models.CharField(max_length=100, blank=True)
    payment_screenshot = models.ImageField(upload_to='payments/%Y/%m/', blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='placed')

    is_received = models.BooleanField(null=True, blank=True)
    feedback_text = models.TextField(blank=True)
    feedback_stars = models.IntegerField(null=True, blank=True)
    not_received_reason = models.TextField(blank=True)

    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    # Return & Exchange Fields
    RETURN_STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('refunded', 'Returned & Refunded'),
        ('exchanged', 'Returned & Exchanged'),
    ]
    return_status = models.CharField(max_length=20, choices=RETURN_STATUS_CHOICES, null=True, blank=True)
    return_type = models.CharField(max_length=10, choices=[('refund', 'Refund'), ('exchange', 'Exchange')], null=True, blank=True)
    return_reason = models.CharField(max_length=100, blank=True)
    return_description = models.TextField(blank=True)
    return_exchange_variant = models.TextField(blank=True)  # Stores exchange selection details
    return_items_json = models.TextField(blank=True, default='[]')  # Selected order items for return/refund/exchange
    return_refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_proof_image = models.ImageField(upload_to='returns/%Y/%m/', blank=True, null=True)
    return_declined_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_id

    @property
    def formatted_return_variants(self):
        """Returns a list of human-readable variant selections for exchange."""
        if not self.return_exchange_variant:
            return None
        try:
            data = json.loads(self.return_exchange_variant)
            if isinstance(data, dict):
                # Returns individual items as a list of strings
                return [f"{v}" for k, v in data.items()]
            return [str(data)]
        except:
            return [self.return_exchange_variant]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_title = models.CharField(max_length=300)
    product_image_url = models.CharField(max_length=500, blank=True)
    product_category = models.CharField(max_length=100)
    product_subcategory = models.CharField(max_length=100, blank=True)
    selected_size_color = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_title} x{self.quantity}"


class Notification(models.Model):
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.seller.business_name}: {self.message[:50]}"


# ─────────────────────────────────────────────
# CONTACT MEASURES (PUBLIC)
# ─────────────────────────────────────────────

class ContactMessage(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Contact from {self.name} ({self.email})"
