from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path('', views.homepage),
    path('aboutus/', views.about),
    path('contactus/', views.contactus, name='contactus'),

    path('menu/', views.menu_page, name='menu_page'),
    path('register/', views.register_page, name='register_page'),
    path('login/', views.login_page, name='login_page'),
    path('success/', views.success, name='success'),

    # Admin / Owner
    path('adminheader/', views.adminheader, name='adminheader'),
    path('adminregister/', views.adminregister, name='adminregister'),
    path('adminlogin/', views.adminlogin, name='adminlogin'),
    path('admin_forgot_password/', views.admin_forgot_password, name='admin_forgot_password'),
    path('admin_logout/', views.adminlogout, name='adminlogout'),
    path('admin_profile/', views.admin_profile, name='admin_profile'),
    path('admin_profile/edit/<int:admin_id>/', views.admin_profile_edit, name='admin_profile_edit'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('check_notifications/', views.check_notifications, name='check_notifications'),
    path('mark_notifications_read/', views.mark_notifications_read, name='mark_notifications_read'),

    # Food
    path('addfood/', views.addfood, name='addfood'),
    path('food_list/', views.food_list, name='food_list'),
    path('view_food/', views.view_food_items, name='view_food'),
    path('foods/edit/<int:food_id>/', views.edit_food, name='edit_food'),
    path('foods/delete/<int:food_id>/', views.delete_food, name='delete_food'),
    path('foods/toggle-availability/<int:food_id>/', views.toggle_food_availability, name='toggle_food_availability'),
    path('bulk_delete_foods/', views.bulk_delete_foods, name='bulk_delete_foods'),

    # Auth helpers
    path('logout/', views.logout_user, name='logout'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),
    path('send-otp/', views.send_otp, name='send_otp'),

    # Cart & Orders
    path('cart/', views.cart_page, name='cart_page'),
    path('add-to-cart/<int:food_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/increase/<int:cart_item_id>/', views.increase_quantity, name='increase_quantity'),
    path('cart/decrease/<int:cart_item_id>/', views.decrease_quantity, name='decrease_quantity'),
    path('cart/remove/<int:cart_item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('checkout/wallet_payment/', views.wallet_payment_checkout, name='wallet_payment_checkout'),
    path('checkout/get_payment_order/', views.get_payment_order, name='get_payment_order'),
    path('wallet/', views.wallet_page, name='wallet_page'),
    path('wallet/add/callback/', views.wallet_add_callback, name='wallet_add_callback'),
    path('paymenthandler/', views.paymenthandler, name='paymenthandler'),
    path('my_orders/', views.my_orders, name='my_orders'),
    path('my_orders/download/<int:order_id>/', views.download_bill, name='download_bill'),
    path('my_orders/rate/<int:order_id>/', views.rate_order, name='rate_order'),
    path('my_orders/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),

    # Profile
    path('profile/', views.profile_view, name='profile_page'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/save_location/', views.save_user_location, name='save_user_location'),

    # Discounts
    path('add-discount/', views.add_discount, name='add_discount'),
    path('quick-add-discount/', views.quick_add_discount, name='quick_add_discount'),
    path('discount-list/', views.discount_list, name='discount_list'),
    path('toggle-discount/<int:discount_id>/', views.toggle_discount_status, name='toggle_discount'),
    path('discount/edit/<int:discount_id>/', views.edit_discount, name='edit_discount'),
    path('discount/<int:id>/delete/', views.delete_discount, name='delete_discount'),

    # Restaurant (Owner)
    path('add_restaurant/', views.add_resto, name='add_restaurant'),
    path('restaurant_list/', views.resto_list, name='resto_list'),
    path('restaurants/toggle-status/<int:id>/', views.toggle_resto_status, name='toggle_resto_status'),
    path('restaurants/edit/<int:id>/', views.edit_restaurant, name='edit_restaurant'),
    path('restaurants/delete/<int:id>/', views.delete_restaurant, name='delete_restaurant'),
    path('restaurants/delete-all/', views.delete_all_restaurants, name='delete-all-restaurants'),

    # Restaurant (User side)
    path('restaurant_view/', views.restaurant_list, name='restaurant_list'),
    path('book_table/<int:restaurant_id>/', views.book_table, name='book_table'),

    # Bookings (User)
    path('my-bookings/', views.my_booking, name='my_booking'),
    path('booking/edit/<int:id>/', views.edit_booking, name='edit_booking'),
    path('booking/delete/<int:id>/', views.delete_booking, name='delete_booking'),
    path('booking/cancel/<int:id>/', views.cancel_booking, name='cancel_booking'),

    # Bookings (Owner)
    path('owner_bookings/', views.owner_bookings, name='owner_bookings'),
    path('owner_bookings/toggle-status/', views.toggle_restaurant_accepting_orders, name='toggle_restaurant_accepting_orders'),

    # Super Admin
    path('super_register/', views.super_register, name='super_register'),
    path('super_login/', views.super_login, name='super_login'),
    path('super_forgot_password/', views.super_forgot_password, name='super_forgot_password'),
    path('super_logout/', views.super_logout, name='super_logout'),
    path('super_profile/', views.super_profile, name='super_profile'),
    path('super_profile_edit/', views.super_profile_edit, name='super_profile_edit'),
    path('super_dashboard/', views.super_dashboard, name='super_dashboard'),
    path('admin_contact_list/', views.admin_contact_list, name='admin_contact_list'),
    path('super_admin/contact-delete/<int:message_id>/', views.admin_contact_delete, name='admin_contact_delete'),
    path('super_admin/contact-reply/<int:message_id>/', views.admin_contact_reply, name='admin_contact_reply'),
    path('show_owners/', views.show_owners, name='show_owners'),
    path('show_users/', views.showsuper_users, name='showsuper_users'),
    path('show_food/', views.show_food, name='show_food'),
    path('show_orders/', views.show_orders, name='show_orders'),
    path('show_booking/', views.show_booking, name='show_booking'),
    path('super_admin/users/send_email/<int:pk>/', views.send_email_to_user, name='send_email_to_user'),
    path('super_admin/users/toggle_block/<int:pk>/', views.toggle_user_block, name='toggle_user_block'),
    path('super_admin/users/manage_wallet/<int:user_id>/', views.super_manage_user_wallet, name='super_manage_user_wallet'),
    path('super_admin/users/manage_wallet/all/', views.super_manage_all_wallets, name='super_manage_all_wallets'),
    path('super_admin/owners/toggle_block/<int:pk>/', views.toggle_owner_block, name='toggle_owner_block'),
    path('super_admin/owners/send_email/<int:pk>/', views.send_email_to_owner, name='send_email_to_owner'),
    path('admin_verify_otp/', views.admin_verify_otp, name='admin_verify_otp'),
    path('super_admin/owners/toggle_approval/<int:pk>/', views.toggle_owner_approval, name='toggle_owner_approval'),
    path('super_admin/notifications/', views.super_notifications, name='super_notifications'),
    
    # User Saved Addresses
    path('profile/add_address/', views.add_user_address, name='add_user_address'),
    path('profile/edit_address/<int:address_id>/', views.edit_user_address, name='edit_user_address'),
    path('profile/delete_address/<int:address_id>/', views.delete_user_address, name='delete_user_address'),

    # Delivery Boy Panel URLs
    path('delivery/register/', views.delivery_register, name='delivery_register'),
    path('delivery/verify-otp/', views.delivery_verify_otp, name='delivery_verify_otp'),
    path('delivery/login/', views.delivery_login, name='delivery_login'),
    path('delivery/forgot-password/', views.delivery_forgot_password, name='delivery_forgot_password'),
    path('delivery/dashboard/', views.delivery_dashboard, name='delivery_dashboard'),
    path('delivery/check_orders/', views.delivery_check_orders, name='delivery_check_orders'),
    path('delivery/accept/<int:order_id>/', views.delivery_accept_order, name='delivery_accept'),
    path('delivery/update-status/<int:order_id>/', views.delivery_update_order_status, name='delivery_update_status'),
    path('delivery/logout/', views.delivery_logout, name='delivery_logout'),

    # Delivery Flow Integration URLs
    path('admin_owner/order/pack/<int:order_id>/', views.owner_pack_order, name='owner_pack_order'),
    path('delivery/request-otp/<int:order_id>/', views.delivery_request_otp, name='delivery_request_otp'),
    path('delivery/verify-delivery/<int:order_id>/', views.delivery_verify_order, name='delivery_verify_order'),
    path('delivery/toggle-duty/', views.delivery_toggle_duty, name='delivery_toggle_duty'),
    path('delivery/profile/edit/', views.delivery_profile_edit, name='delivery_profile_edit'),
    path('delivery/vehicle-info/', views.delivery_vehicle_info, name='delivery_vehicle_info'),
    path('delivery/bank-details/', views.delivery_bank_details, name='delivery_bank_details'),
    path('delivery/help/', views.delivery_help_support, name='delivery_help_support'),
    
    # Delivery Notifications
    path('delivery/notifications/', views.delivery_notifications, name='delivery_notifications'),
    path('delivery/notifications/read/<int:notif_id>/', views.delivery_mark_notification_read, name='delivery_mark_notification_read'),
    path('delivery/notifications/read-all/', views.delivery_mark_all_notifications_read, name='delivery_mark_all_notifications_read'),

    # Super Admin Delivery Boy Management
    path('super_admin/delivery_tasks/', views.super_delivery_tasks, name='super_delivery_tasks'),
    path('super_admin/delivery_boys/', views.super_delivery_boys, name='super_delivery_boys'),
    path('super_admin/delivery_boys/toggle-verify/<int:boy_id>/', views.super_toggle_verify_boy, name='super_toggle_verify_boy'),
    path('super_admin/delivery_boys/toggle-block/<int:boy_id>/', views.super_toggle_block_boy, name='super_toggle_block_boy'),
    path('super_admin/delivery_boys/delete/<int:boy_id>/', views.super_delete_boy, name='super_delete_boy'),
    path('super_admin/platform_settings/', views.super_platform_settings, name='super_platform_settings'),

    # Restaurant Owner Notifications
    path('owner/notifications/', views.owner_notifications, name='owner_notifications'),
    path('owner/notifications/read/<int:notif_id>/', views.owner_mark_notification_read, name='owner_mark_notification_read'),
    path('owner/notifications/read-all/', views.owner_mark_all_notifications_read, name='owner_mark_all_notifications_read'),

    # Super Admin Notifications
    path('super_admin/notifications_page/', views.super_notifications_page, name='super_notifications_page'),
    path('super_admin/notifications/read/<int:notif_id>/', views.super_mark_notification_read, name='super_mark_notification_read'),
    path('super_admin/notifications/read-all/', views.super_mark_all_notifications_read, name='super_mark_all_notifications_read'),
]
