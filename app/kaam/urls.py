from django.urls import path
from kaam import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('contact/', views.contact_us, name='contact'),
    path('login/', views.seller_login, name='login'),
    path('logout/', views.seller_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/products/', views.product_list, name='product_list'),
    path('dashboard/products/add/', views.product_add, name='product_add'),
    path('dashboard/products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('dashboard/products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('dashboard/products/bulk_delete/', views.bulk_delete_products, name='bulk_delete_products'),
    path('dashboard/analytics/', views.analytics, name='analytics'),
    path('dashboard/settings/', views.seller_settings, name='settings'),
    path('dashboard/feedbacks/', views.feedbacks, name='feedbacks'),
    path('dashboard/orders/', views.orders_page, name='orders_page'),
    path('dashboard/orders/<str:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('dashboard/orders/<str:order_id>/confirm/', views.confirm_order, name='confirm_order'),
    path('dashboard/orders/<str:order_id>/view/', views.order_detail, name='order_detail'),
    path('dashboard/orders/<str:order_id>/delete/', views.delete_order, name='delete_order'),
    path('dashboard/orders/bulk-delete/', views.bulk_delete_orders, name='bulk_delete_orders'),
    path('dashboard/orders/<str:order_id>/return/update/', views.update_return_status, name='update_return_status'),
    path('trace/', views.trace_order, name='trace_order'),
    path('trace/<str:order_id>/', views.trace_order_detail, name='trace_order_detail'),

    # AJAX endpoints
    path('api/analytics/realtime/', views.api_realtime_analytics, name='api_realtime_analytics'),
    path('api/analytics/category/', views.api_category_analytics, name='api_category_analytics'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
    path('api/notifications/read/', views.api_mark_notifications_read, name='api_mark_notifications_read'),
    path('api/check-username/', views.check_username, name='check_username'),

    # Data Exports
    path('dashboard/export/orders/', views.export_orders, name='export_orders'),
    path('dashboard/export/analytics/', views.export_analytics, name='export_analytics'),

    # Manual & Bulk Order Creation
    path('manual-order/create/', views.manual_order_create, name='manual_order_create'),
    path('orders/import-csv/', views.import_orders_csv, name='import_orders_csv'),

    # Buyer storefront — MUST be last
    path('<str:username>/', views.storefront, name='storefront'),
    path('<str:username>/order-placed/<str:order_id>/', views.order_placed, name='order_placed'),
]
