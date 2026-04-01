from django.contrib import admin
from django import forms
from django.contrib.auth.models import User
from .models import Seller, Product, Order, OrderItem, Notification, ContactMessage

admin.site.site_header = "Kaam Admin"
admin.site.site_title = "Kaam Admin Portal"
admin.site.index_title = "Welcome to Kaam Administration"


class SellerForm(forms.ModelForm):
    login_username = forms.CharField(
        label="Login Username", 
        help_text="Used for the seller to login to the Kaam dashboard.", 
        required=False
    )
    login_password = forms.CharField(
        label="Login Password", 
        widget=forms.PasswordInput, 
        help_text="Set a password. Leave it blank when editing to keep the current password.", 
        required=False
    )
    upi_id = forms.CharField(
        label="UPI ID / VPA",
        required=True,
        help_text="Mandatory UPI ID limit for this seller. e.g. 9999999999@upi"
    )

    class Meta:
        model = Seller
        exclude = ('user',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['login_username'].required = True
            self.fields['login_password'].required = True
        else:
            if getattr(self.instance, 'user', None):
                self.fields['login_username'].initial = self.instance.user.username

    def clean_login_username(self):
        login_username = self.cleaned_data.get('login_username')
        if not self.instance.pk and User.objects.filter(username=login_username).exists():
            raise forms.ValidationError("A user with this login username already exists.")
        if self.instance.pk and getattr(self.instance, 'user', None) and self.instance.user.username != login_username and User.objects.filter(username=login_username).exists():
            raise forms.ValidationError("A user with this login username already exists.")
        return login_username

    def save(self, commit=True):
        seller = super().save(commit=False)
        if not seller.pk:
            user = User.objects.create_user(
                username=self.cleaned_data['login_username'],
                password=self.cleaned_data['login_password']
            )
            seller.user = user
        else:
            if getattr(seller, 'user', None):
                if self.cleaned_data.get('login_password'):
                    seller.user.set_password(self.cleaned_data['login_password'])
                if self.cleaned_data.get('login_username'):
                    seller.user.username = self.cleaned_data['login_username']
                seller.user.save()
            
        if commit:
            seller.save()
        return seller

@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    form = SellerForm
    list_display = ['business_name', 'username', 'whatsapp_number', 'upi_id',
                    'is_active', 'subscription_active', 'subscription_expires',
                    'created_at', 'total_orders_count']
    list_filter = ['is_active', 'subscription_active', 'category']
    search_fields = ['business_name', 'username', 'user__email']
    actions = ['terminate_subscription', 'activate_subscription']

    def terminate_subscription(self, request, queryset):
        queryset.update(is_active=False, subscription_active=False)
        self.message_user(request, f"Terminated {queryset.count()} seller(s).")
    terminate_subscription.short_description = "Terminate selected sellers"

    def activate_subscription(self, request, queryset):
        queryset.update(is_active=True, subscription_active=True)
        self.message_user(request, f"Activated {queryset.count()} seller(s).")
    activate_subscription.short_description = "Activate selected sellers"

    def total_orders_count(self, obj):
        return obj.orders.count()
    total_orders_count.short_description = "Total Orders"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'seller', 'buyer_name', 'status',
                    'payment_method', 'total_amount', 'created_at']
    list_filter = ['status', 'payment_method', 'seller']
    search_fields = ['order_id', 'buyer_name', 'buyer_email', 'buyer_whatsapp']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'seller', 'category', 'subcategory', 'price', 'is_available']
    list_filter = ['seller', 'category', 'is_available']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['product_title', 'order', 'quantity', 'unit_price', 'subtotal']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['seller', 'message', 'is_read', 'created_at']
    list_filter = ['is_read', 'seller']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'is_resolved', 'created_at']
    list_filter = ['is_resolved', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    list_editable = ['is_resolved']

