from myapp.models import AddResto, AdminOwner


def admin_user(request):
    admin_id = request.session.get('admin_id')
    user = None
    owner_restaurant = None
    if admin_id:
        try:
            user = AdminOwner.objects.get(pk=admin_id)
            owner_restaurant = AddResto.objects.filter(name__iexact=user.restaurant_name).first()
        except AdminOwner.DoesNotExist:
            pass
    return {'admin_user': user, 'owner_restaurant': owner_restaurant}


from .models import Cart, Registration

def cart_item_count(request):
    user_id = request.session.get('user_id')
    count = 0
    if user_id:
        try:
            user = Registration.objects.get(id=user_id)
            count = Cart.objects.filter(user=user).count()
        except Registration.DoesNotExist:
            pass
    return {'cart_count': count}


def user_wallet(request):
    user_id = request.session.get('user_id')
    wallet_balance = 0.00
    if user_id:
        try:
            user = Registration.objects.get(id=user_id)
            wallet_balance = float(user.wallet_balance)
        except Registration.DoesNotExist:
            pass
    return {'user_wallet_balance': wallet_balance}


def delivery_boy_notifications(request):
    boy_id = request.session.get('delivery_boy_id')
    unread_count = 0
    boy = None
    if boy_id:
        try:
            from .models import DeliveryBoy, DeliveryBoyNotification
            boy = DeliveryBoy.objects.get(id=boy_id)
            unread_count = DeliveryBoyNotification.objects.filter(delivery_boy=boy, is_read=False).count()
        except Exception:
            pass
    return {
        'boy': boy,
        'unread_notifications_count': unread_count
    }


def owner_notifications_count(request):
    admin_id = request.session.get('admin_id')
    unread_count = 0
    if admin_id:
        try:
            from .models import AdminOwner, RestaurantNotification
            admin_user = AdminOwner.objects.get(id=admin_id)
            unread_count = RestaurantNotification.objects.filter(
                restaurant_name__iexact=admin_user.restaurant_name,
                is_read=False
            ).count()
        except Exception:
            pass
    return {'owner_unread_count': unread_count}


def super_notifications_count(request):
    super_id = request.session.get('super_id')
    unread_count = 0
    if super_id:
        try:
            from .models import SuperAdminNotification
            unread_count = SuperAdminNotification.objects.filter(is_read=False).count()
        except Exception:
            pass
    return {'super_unread_count': unread_count}
