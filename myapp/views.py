import os
import random
import json
from random import randint
from decimal import Decimal
from datetime import date, datetime, time

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.utils.timezone import now
from django.core.files import File
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User 
from django.contrib.sessions.models import Session
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, F
from django.db.models.functions import TruncDate
from django.contrib.auth.signals import user_logged_in

from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

try:
    import razorpay
except ImportError:
    razorpay = None

from myproject.views import food_add
from .models import (
    Registration, AdminOwner, FoodItem, OrderItem, AddResto, Booking, 
    SuperRegister, Cart, Order_pay, ContactMessage, Discount, Order, UserAddress, DeliveryBoy,
    RestaurantNotification, SuperAdminNotification, WalletTransaction
)
from .forms import (
    RegistrationForm, LoginForm, ForgotPasswordForm, OTPForm, ResetPasswordForm,
    FoodItemForm, AdminLoginForm, AdminOwnerRegisterForm, AddRestoForm, 
    SuperRegisterForm, SuperLoginForm, ContactMessageForm, EmailForm, DiscountForm
)


def profile_view(request):
    from .models import Order, Booking_resto
    user_id = request.session.get('user_id')
    user = None
    orders_count = 0
    bookings_count = 0
    saved_addresses = []
    if user_id:
        user = Registration.objects.filter(id=user_id).first()
        if user:
            if user.is_blocked:
                request.session.flush()
                messages.error(request, "Your account has been blocked by the Super Admin.")
                return redirect('login_page')
            orders_count = Order.objects.filter(user=user).count()
            bookings_count = Booking_resto.objects.filter(contact_number=user.phone).count()
            saved_addresses = UserAddress.objects.filter(user=user).order_by('-id')

    return render(request, 'profile.html', {
        'user': user,
        'orders_count': orders_count,
        'bookings_count': bookings_count,
        'saved_addresses': saved_addresses,
    })


def edit_profile(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_page')

    user = Registration.objects.get(id=user_id)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.phone = request.POST.get('phone')
        user.city = request.POST.get('city')
        user.gender = request.POST.get('gender')
        
        if 'profile_image' in request.FILES:
            user.profile_image = request.FILES['profile_image']

        user.save()        

        if user.profile_image:
            request.session['image'] = user.profile_image.url
        else:
            request.session['image'] = None

        return redirect('profile_page')  

    return render(request, 'edit_profile.html', {'user': user})


def save_user_location(request):
    if 'user_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'User not logged in'}, status=403)
        
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            address = data.get('address', '').strip()
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            
            user = Registration.objects.get(id=request.session['user_id'])
            user.address = address
            if latitude is not None:
                user.latitude = latitude
            if longitude is not None:
                user.longitude = longitude
            user.save()
            return JsonResponse({'status': 'success', 'message': 'Location saved successfully!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def add_user_address(request):
    if 'user_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'User not logged in'}, status=403)
        
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            user = Registration.objects.get(id=request.session['user_id'])
            
            address_type = data.get('address_type', 'Home')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            house_no = data.get('house_no', '').strip()
            building_name = data.get('building_name', '').strip()
            floor = data.get('floor', '').strip()
            landmark = data.get('landmark', '').strip()
            complete_address = data.get('complete_address', '').strip()
            
            details = []
            if address_type == 'Home':
                if house_no: details.append(f"House/Flat: {house_no}")
                if building_name: details.append(f"Building: {building_name}")
            elif address_type == 'Work':
                if building_name: details.append(f"Office: {building_name}")
                if floor: details.append(f"Floor: {floor}")
            else: # Other
                label = data.get('other_label', '').strip() or 'Other'
                building_name = label
                house_no = data.get('house_no', '').strip()
                if label: details.append(f"Label: {label}")
                if house_no: details.append(f"Details: {house_no}")
            
            if landmark:
                details.append(f"Landmark: {landmark}")
            
            formatted_details = ", ".join(details)
            full_address = complete_address
            if formatted_details:
                full_address = f"{formatted_details}, {complete_address}"
            
            user_address = UserAddress.objects.create(
                user=user,
                address_type=address_type,
                latitude=latitude,
                longitude=longitude,
                house_no=house_no,
                building_name=building_name,
                floor=floor,
                landmark=landmark,
                complete_address=complete_address
            )
            
            # Also update user's primary/default address for backward compatibility
            user.address = user_address.full_address
            user.latitude = latitude
            user.longitude = longitude
            user.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Address added successfully!',
                'address': {
                    'id': user_address.id,
                    'address_type': user_address.address_type,
                    'complete_address': user_address.complete_address
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def edit_user_address(request, address_id):
    if 'user_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'User not logged in'}, status=403)
        
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            user = Registration.objects.get(id=request.session['user_id'])
            user_address = get_object_or_404(UserAddress, id=address_id, user=user)
            
            address_type = data.get('address_type', 'Home')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            house_no = data.get('house_no', '').strip()
            building_name = data.get('building_name', '').strip()
            floor = data.get('floor', '').strip()
            landmark = data.get('landmark', '').strip()
            complete_address = data.get('complete_address', '').strip()
            
            details = []
            if address_type == 'Home':
                if house_no: details.append(f"House/Flat: {house_no}")
                if building_name: details.append(f"Building: {building_name}")
            elif address_type == 'Work':
                if building_name: details.append(f"Office: {building_name}")
                if floor: details.append(f"Floor: {floor}")
            else: # Other
                label = data.get('other_label', '').strip() or 'Other'
                building_name = label
                house_no = data.get('house_no', '').strip()
                if label: details.append(f"Label: {label}")
                if house_no: details.append(f"Details: {house_no}")
            
            if landmark:
                details.append(f"Landmark: {landmark}")
            
            user_address.address_type = address_type
            if latitude: user_address.latitude = latitude
            if longitude: user_address.longitude = longitude
            user_address.house_no = house_no
            user_address.building_name = building_name
            user_address.floor = floor
            user_address.landmark = landmark
            user_address.complete_address = complete_address
            user_address.save()
            
            # Also update user default address for compatibility
            user.address = user_address.full_address
            user.latitude = latitude
            user.longitude = longitude
            user.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Address updated successfully!',
                'address': {
                    'id': user_address.id,
                    'address_type': user_address.address_type,
                    'complete_address': user_address.complete_address
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def delete_user_address(request, address_id):
    if 'user_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'User not logged in'}, status=403)
        
    if request.method == 'POST' or request.method == 'DELETE':
        try:
            user = Registration.objects.get(id=request.session['user_id'])
            address = get_object_or_404(UserAddress, id=address_id, user=user)
            address.delete()
            return JsonResponse({'status': 'success', 'message': 'Address deleted successfully!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


from django.shortcuts import render, redirect
from .models import Registration, Booking_resto

def my_booking(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('/login')

    user = Registration.objects.get(id=user_id)

    # Auto-mark past Pending bookings as Completed
    Booking_resto.objects.filter(
        contact_number=user.phone,
        status='Pending',
        booking_time__lt=timezone.now()
    ).update(status='Completed')

    user_bookings = Booking_resto.objects.filter(contact_number=user.phone).select_related('restaurant').order_by('-id')

    return render(request, 'my_booking.html', {
        'bookings': user_bookings,
        'user': user,
    })


def send_otp(request):
    if request.method == "POST":
        email = request.POST.get("email")
        if not email:
            return JsonResponse({"success": False, "message": "Email is required"})

        request.session["registration_data"] = request.POST.dict()
        
        if "profile_image" in request.FILES:
            uploaded_file = request.FILES["profile_image"]
            temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            temp_filename = f"{now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
            temp_path = os.path.join(temp_dir, temp_filename)
            with open(temp_path, "wb+") as dest:
                for chunk in uploaded_file.chunks():
                    dest.write(chunk)
            request.session["temp_profile_image"] = temp_path

        otp = str(random.randint(100000, 999999))
        request.session["otp"] = otp
        request.session["email_for_otp"] = email

        # Print the OTP to console logs immediately so it is visible on Render
        print(f"\n========================================\nUSER REGISTRATION OTP FOR {email}: {otp}\n========================================\n")

        import threading
        def send_email_thread():
            try:
                import os
                api_key = os.environ.get('BREVO_API_KEY')
                print(f"DEBUG: BREVO_API_KEY status: {'Loaded (len=' + str(len(api_key)) + ')' if api_key else 'NOT LOADED'}", flush=True)
                send_mail(
                    subject="Your OTP Code",
                    message=f"Your OTP is {otp}",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[email],
                    fail_silently=False,
                )
                print(f"Async email sending completed successfully for {email}", flush=True)
            except Exception as e:
                print(f"Async email sending failed for {email}: {e}", flush=True)

        threading.Thread(target=send_email_thread).start()
        return JsonResponse({"success": True, "message": "OTP sent successfully"})
    
    return JsonResponse({"success": False, "message": "Invalid request"})


def register_page(request):
    form = RegistrationForm()

    if request.method == "POST":
        if "create_user" in request.POST:
            user_otp = request.POST.get("otp")
            session_otp = request.session.get("otp")
            data = request.session.get("registration_data")

            if user_otp == session_otp and data:
                form = RegistrationForm(data)
                if form.is_valid():
                    instance = form.save(commit=False)
                    instance.password = make_password(data["password"])

                    temp_image_path = request.session.get("temp_profile_image")
                    if temp_image_path and os.path.exists(temp_image_path):
                        with open(temp_image_path, "rb") as f:
                            instance.profile_image.save(os.path.basename(temp_image_path), File(f))
                        os.remove(temp_image_path)

                    instance.save()

                    for key in ["registration_data", "otp", "email_for_otp", "temp_profile_image"]:
                        request.session.pop(key, None)

                    messages.success(request, "Registration successful! Please log in.")
                    return redirect("login_page")
                else:
                    messages.error(request, "Invalid form data. Try again.")

            else:
                messages.error(request, "Invalid OTP or expired session. Please try again.")

    return render(request, "register.html", {"form": form})



def login_page(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            login_input = form.cleaned_data['email']
            password = form.cleaned_data['password']

            from django.db.models import Q
            try:
                user = Registration.objects.get(Q(email=login_input) | Q(phone=login_input))
                
                if user.is_blocked:
                    messages.error(request, "Your account has been blocked by the Super Admin. Please contact support.")
                    return render(request, 'login.html', {'form': form})

                if check_password(password, user.password):
                    request.session['user_name'] = user.first_name + ' ' + user.last_name
                    request.session['user_id'] = user.id
                    request.session['image'] = user.profile_image.url if user.profile_image else None
                    request.session['user_phone'] = user.phone    

                    messages.success(request, f"Welcome {user.first_name}!")
                    return redirect('/')
                else:
                    messages.error(request, "Incorrect password!")
            except Registration.DoesNotExist:
                messages.error(request, "User with this email or mobile number does not exist!")

    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})



def logout_user(request):
    request.session.pop('user_name', None)
    request.session.pop('user_id', None)
    request.session.pop('image', None)
    
    request.session.pop('cart', None)
    
    messages.success(request, "You have successfully logged out.")
    return redirect('/')


def success(request):
    return render(request, 'success.html')

def homepage(request):
    food_items = FoodItem.objects.filter(is_available=True).order_by('-id')
    data = {
        'title': 'Wel-Come Zomato',
        'food_items': food_items,
    }
    return render(request,"homepage.html",data)

def about(request):
    data={'title' : 'About-Us'}

    return render(request,"aboutus.html",data)

def contact(request):
    data={'title' : 'Contact-Us'}

    return render(request,"contactus.html",data)

def menu(request):
    data={'title' : 'Menu'}

    return render(request,"menu.html",data)

def restaurant(request):
    data={'title' : 'Menu'}

    return render(request,"restaurant.html",data)



def forgot_password(request):
    
    
    if 'otp_sent' not in request.session:
        request.session['otp_sent'] = False
        request.session['otp_verified'] = False
    
    
    
    if request.method == 'POST' and not request.session['otp_sent']:
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = Registration.objects.get(email=email)
                otp = randint(100000, 999999)
                request.session['reset_email'] = email
                request.session['otp_code'] = str(otp)
                request.session['otp_sent'] = True
                request.session['otp_verified'] = False               
                
                # Print the OTP to console logs immediately
                print(f"\n========================================\nFORGOT PASSWORD OTP FOR {email}: {otp}\n========================================\n")

                import threading
                def send_email_thread():
                    try:
                        import os
                        api_key = os.environ.get('BREVO_API_KEY')
                        print(f"DEBUG: BREVO_API_KEY status: {'Loaded (len=' + str(len(api_key)) + ')' if api_key else 'NOT LOADED'}", flush=True)
                        send_mail(
                            'Your OTP for Foodeat Password Reset',
                            f'Your OTP is: {otp}',
                            settings.EMAIL_HOST_USER,
                            [email],
                            fail_silently=False,
                        )
                        print(f"Async email sending completed successfully for {email}", flush=True)
                    except Exception as e:
                        print(f"Async email sending failed for {email}: {e}", flush=True)

                threading.Thread(target=send_email_thread).start()
                messages.success(request, "OTP has been generated. If you don't receive it, please check the Render logs.")
                return redirect('forgot_password')
            except Registration.DoesNotExist:
                messages.error(request, "Email not registered")
   
    
    elif request.method == 'POST' and request.session.get('otp_sent') and not request.session.get('otp_verified'):
        form = OTPForm(request.POST)
        if form.is_valid():
            otp_input = form.cleaned_data['otp']
            if otp_input == request.session.get('otp_code'):
                request.session['otp_verified'] = True
                messages.success(request, "OTP verified. Please set your new password.")
                return redirect('forgot_password')
            else:
                messages.error(request, "Invalid OTP. Try again.")    
  
    
    elif request.method == 'POST' and request.session.get('otp_verified'):
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            email = request.session.get('reset_email')
            try:
                user = Registration.objects.get(email=email)
                user.password = make_password(password)
                user.save()
                messages.success(request, "Password reset successful!")               
                
                
                request.session.pop('otp_sent')
                request.session.pop('otp_verified')
                request.session.pop('otp_code')
                request.session.pop('reset_email')
                return redirect('/login/')
            except Registration.DoesNotExist:
                messages.error(request, "Something went wrong. Try again.")   
   
    
    if not request.session.get('otp_sent'):
        form = ForgotPasswordForm()
    elif request.session.get('otp_sent') and not request.session.get('otp_verified'):
        form = OTPForm()
    else:
        form = ResetPasswordForm()
    
    return render(request, "forgot_password.html", {'form': form})

    

def add_to_cart(request, food_id):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please log in first.")
        return redirect('/login')

    user = get_object_or_404(Registration, id=user_id)

    try:
        food = FoodItem.objects.get(id=food_id)
    except FoodItem.DoesNotExist:
        messages.error(request, "Food item does not exist.")
        return redirect('/menu')

    restaurant = restaurant_for_food(food)
    if restaurant and not restaurant.is_accepting_orders:
        messages.error(request, f"{restaurant.name} is currently closed for booking and orders.")
        return redirect('/menu')

    cart_item, created = Cart.objects.get_or_create(user=user, food=food)
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, f"{food.food_name} added to your cart.")
    return redirect(request.META.get('HTTP_REFERER', '/menu'))

def cart_page(request):
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "Please log in to view your cart.")
        return redirect('/login')

    user = get_object_or_404(Registration, id=user_id)
    cart_items = Cart.objects.filter(user=user)

    total = 0
    total_after_discount = 0
    today = timezone.now().date()

    for item in cart_items:
        item.subtotal = item.food.price * item.quantity

        discount = (
            Discount.objects.filter(
                product=item.food,
                active=True,
                start_date__lte=today,
                end_date__gte=today
            )
            .order_by('-discount_percentage')
            .first()
        )

        item.discount_percent = discount.discount_percentage if discount else 0
        item.discounted_unit_price = float(item.food.price) * (1 - float(item.discount_percent) / 100.0)
        item.final_price = item.subtotal - (item.subtotal * item.discount_percent / 100)

        total += item.subtotal
        total_after_discount += item.final_price

    discount_difference = total - total_after_discount

    from .models import PlatformSettings
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    delivery_charge = float(platform_settings.base_delivery_charge)
    final_payable_amount = float(total_after_discount) + delivery_charge

    context = {
        'cart_items': cart_items,
        'total': float(total),
        'total_after_discount': float(total_after_discount),
        'discount_difference': float(discount_difference),  
        'delivery_charge': delivery_charge,
        'final_payable_amount': final_payable_amount,
    }
    return render(request, 'cart.html', context)


def cart_view(request):
    user_id = request.session.get('user_id') 
    if not user_id:
        cart_items = []
    else:
        user = get_object_or_404(Registration, id=user_id)
        cart_items = Cart.objects.filter(user=user)

    return render(request, 'cart.html', {'cart_items': cart_items})


def merge_session_cart(sender, user, request, **kwargs):
    session_cart = request.session.get('cart', {})
    for food_id_str, quantity in session_cart.items():
        food = FoodItem.objects.get(id=int(food_id_str))
        cart_item, created = Cart.objects.get_or_create(
            user=user,     
            food=food,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
    request.session['cart'] = {}

user_logged_in.connect(merge_session_cart)

def increase_quantity(request, cart_item_id):
    cart_item = get_object_or_404(Cart, id=cart_item_id)
    cart_item.quantity += 1
    cart_item.save()
    messages.info(request, f"Updated quantity for {cart_item.food.food_name}.")
    return redirect('cart_page')

def decrease_quantity(request, cart_item_id):
    cart_item = get_object_or_404(Cart, id=cart_item_id)
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
        messages.info(request, f"Updated quantity for {cart_item.food.food_name}.")
    else:
        cart_item.delete()
        messages.warning(request, f"{cart_item.food.food_name} has been removed from your cart.")
    return redirect('cart_page')

def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(Cart, id=cart_item_id)
    food_name = cart_item.food.food_name
    cart_item.delete()
    messages.warning(request, f"{food_name} has been removed from your cart.")
    return redirect('cart_page')


def restaurant_list(request):
    restaurants = AddResto.objects.all()
    return render(request, "restaurant_view.html", {"restaurants": restaurants})


def normalize_restaurant_closing_time(opening_time, closing_time):
    if closing_time == time(12, 0) and opening_time > closing_time:
        return time(0, 0)
    return closing_time


def is_booking_time_within_hours(selected_time, opening_time, closing_time):
    closing_time = normalize_restaurant_closing_time(opening_time, closing_time)

    if opening_time <= closing_time:
        return opening_time <= selected_time <= closing_time

    return selected_time >= opening_time or selected_time <= closing_time


def format_restaurant_time(value):
    return datetime.combine(date.today(), value).strftime('%I:%M %p')


def restaurant_for_food(food):
    return AddResto.objects.filter(name__iexact=food.restaurant_name).first()


def unavailable_restaurants_for_cart(cart_items):
    unavailable = []
    seen = set()

    for item in cart_items:
        restaurant_name = item.food.restaurant_name
        key = restaurant_name.lower()
        if key in seen:
            continue

        restaurant = restaurant_for_food(item.food)
        if restaurant and not restaurant.is_accepting_orders:
            unavailable.append(restaurant.name)
            seen.add(key)

    return unavailable


def book_table(request, restaurant_id):
    restaurant = get_object_or_404(AddResto, id=restaurant_id)
    closing_time = normalize_restaurant_closing_time(restaurant.opening_time, restaurant.closing_time)

    if request.method == "POST":
        name = request.POST.get("customer_name")
        contact = request.POST.get("contact_number")
        members = request.POST.get("members")

        Booking.objects.create(
            restaurant=restaurant,
            customer_name=name,
            contact_number=contact,
            members=members
        )
        messages.success(request, f"Your table has been booked at {restaurant.name}!")

    if request.method == "POST":
        name = request.POST.get("customer_name")
        contact = request.POST.get("contact_number")
        members = request.POST.get("members")

        Booking.objects.create(
            restaurant=restaurant,
            customer_name=name,
            contact_number=contact,
            members=members
        )
        messages.success(request, f"Your table has been booked at {restaurant.name}!")
        return redirect("restaurant_list")

    return redirect("restaurant_list")  


def edit_booking(request, id):
    booking = get_object_or_404(Booking_resto, id=id)

    if request.method == "POST":
        booking.customer_name = request.POST['customer_name']
        booking.contact_number = request.POST['contact_number']
        booking.members = request.POST['members']
        
        booking_time_value = request.POST.get('booking_time')
        try:
            booking_time = datetime.strptime(booking_time_value, "%Y-%m-%dT%H:%M")
            if timezone.is_naive(booking_time):
                booking_time = timezone.make_aware(booking_time, timezone.get_default_timezone())
            booking.booking_time = booking_time
        except ValueError:
            try:
                booking_time = datetime.strptime(booking_time_value, "%Y-%m-%dT%H:%M:%S")
                if timezone.is_naive(booking_time):
                    booking_time = timezone.make_aware(booking_time, timezone.get_default_timezone())
                booking.booking_time = booking_time
            except ValueError:
                booking.booking_time = booking_time_value

        booking.save()
        return redirect('my_booking')

    return render(request, 'edit_booking.html', {'booking': booking})


def delete_booking(request, id):
    booking = get_object_or_404(Booking_resto, id=id)
    booking.delete()
    return redirect('my_booking')


def cancel_booking(request, id):
    booking = get_object_or_404(Booking_resto, id=id)
    if request.method == 'POST':
        booking.status = 'Cancelled'
        booking.save()
    return redirect('my_booking')


def checkout_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please login first.")
        return redirect('/login')

    user = get_object_or_404(Registration, id=user_id)

    # Force location selection before checkout/ordering
    saved_addresses = UserAddress.objects.filter(user=user).order_by('-id')
    if not saved_addresses.exists():
        messages.error(request, "Please add a saved address in your profile before placing an order.")
        return redirect('profile_page')

    cart_items = Cart.objects.filter(user=user)

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty!")
        return redirect('/menu')

    unavailable_restaurants = unavailable_restaurants_for_cart(cart_items.select_related('food'))
    if unavailable_restaurants:
        messages.error(
            request,
            ", ".join(unavailable_restaurants) + " is currently closed for booking and orders. Please remove its items from your cart."
        )
        return redirect('cart_page')

    subtotal = 0
    total_discount = 0
    today = timezone.now().date()

    for item in cart_items:
        item_subtotal = item.food.price * item.quantity
        discount = (
            Discount.objects.filter(
                product=item.food,
                active=True,
                start_date__lte=today,
                end_date__gte=today
            )
            .order_by('-discount_percentage')
            .first()
        )
        discount_percent = discount.discount_percentage if discount else 0
        item.discount_percent = discount_percent
        item.discounted_unit_price = float(item.food.price) * (1 - float(discount_percent) / 100.0)
        discount_amount = item_subtotal * discount_percent / 100

        subtotal += item_subtotal
        total_discount += discount_amount

    from .models import PlatformSettings
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    delivery_charge = float(platform_settings.base_delivery_charge)

    final_total = float(subtotal - total_discount) + delivery_charge
    final_total_paise = int(final_total * 100)

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))
    DATA = {
        "amount": final_total_paise,
        "currency": "INR",
        "payment_capture": 1,
    }
    try:
        razorpay_order = client.order.create(data=DATA)
        razorpay_order_id = razorpay_order['id']
        is_offline = False
    except Exception as e:
        import uuid
        razorpay_order_id = f"offline_order_{uuid.uuid4().hex[:12]}"
        is_offline = True

    order = Order_pay.objects.create(
        user=user,
        razorpay_order_id=razorpay_order_id,
        amount=final_total,
        wallet_used=0.00,
        status='created'
    )

    context = {
        "cart_items": cart_items,
        "subtotal": float(subtotal),
        "total_discount": float(total_discount),
        "delivery_charge": delivery_charge,
        "final_total": float(final_total),
        "final_total_paise": final_total_paise,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "callback_url": "/paymenthandler/",
        "saved_addresses": saved_addresses,
        "user_wallet_balance": float(user.wallet_balance),
        "is_offline": is_offline,
    }
    return render(request, "checkout.html", context)


def wallet_payment_checkout(request):
    from django.http import JsonResponse
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Please login first.'}, status=403)
        
    user = get_object_or_404(Registration, id=user_id)
    cart_items = Cart.objects.filter(user=user)
    if not cart_items.exists():
        return JsonResponse({'status': 'error', 'message': 'Your cart is empty!'}, status=400)
        
    # Check if restaurant is closed
    unavailable_restaurants = unavailable_restaurants_for_cart(cart_items.select_related('food'))
    if unavailable_restaurants:
        return JsonResponse({
            'status': 'error',
            'message': ", ".join(unavailable_restaurants) + " is currently closed. Please remove its items."
        }, status=400)

    # Calculate final payable amount
    subtotal = 0
    total_discount = 0
    today = timezone.now().date()
    for item in cart_items:
        item_subtotal = item.food.price * item.quantity
        discount = Discount.objects.filter(
            product=item.food,
            active=True,
            start_date__lte=today,
            end_date__gte=today
        ).order_by('-discount_percentage').first()
        
        discount_percent = discount.discount_percentage if discount else 0
        discount_amount = item_subtotal * discount_percent / 100
        subtotal += item_subtotal
        total_discount += discount_amount

    from .models import PlatformSettings
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    delivery_charge = float(platform_settings.base_delivery_charge)
    final_payable_amount = float(subtotal - total_discount) + delivery_charge

    # Check if user has sufficient wallet balance
    if float(user.wallet_balance) < final_payable_amount:
        return JsonResponse({'status': 'error', 'message': 'Insufficient wallet balance.'}, status=400)

    # Deduct wallet balance
    from decimal import Decimal
    user.wallet_balance -= Decimal(str(final_payable_amount))
    user.save()

    # Address
    address_id = request.POST.get('address_id')
    delivery_address = user.address or user.city or "Not provided"
    if address_id:
        try:
            saved_addr = UserAddress.objects.get(id=address_id, user=user)
            delivery_address = saved_addr.full_address
        except UserAddress.DoesNotExist:
            pass

    # Auto-assign delivery boy (Round-Robin/Least Load logic for online boys)
    from django.db.models import Count, Q
    from .models import DeliveryBoy, RestaurantNotification, SuperAdminNotification
    
    online_boys = DeliveryBoy.objects.filter(is_verified=True, is_blocked=False).exclude(status='Off-duty')
    assigned_boy = None
    if online_boys.exists():
        today_date = timezone.localdate()
        online_boys_with_counts = online_boys.annotate(
            today_orders_count=Count(
                'orders',
                filter=Q(orders__order_date__date=today_date) & ~Q(orders__status='Cancelled')
            )
        ).order_by('today_orders_count', 'id')
        assigned_boy = online_boys_with_counts.first()
        if assigned_boy.status == 'Available':
            assigned_boy.status = 'Delivering'
            assigned_boy.save()

    # Create Order object
    rider_share = float(platform_settings.rider_share_percentage)
    resto_commission_rate = float(platform_settings.restaurant_commission_percentage)
    rider_earning = delivery_charge * (rider_share / 100.0)
    restaurant_commission = float(subtotal) * (resto_commission_rate / 100.0)

    order = Order.objects.create(
        user=user, 
        razorpay_order_id="WALLET_PAYMENT",
        payment_id="WALLET_PAYMENT",
        total_amount=float(subtotal),
        total_discount=float(total_discount),
        final_amount=float(final_payable_amount),
        delivery_name=f"{user.first_name} {user.last_name}",
        delivery_phone=user.phone,
        delivery_address=delivery_address,
        delivery_boy=assigned_boy,
        delivery_charge=delivery_charge,
        rider_earning=rider_earning,
        restaurant_commission=restaurant_commission,
        status='paid'
    )

    if not assigned_boy:
        for _ in range(5):
            SuperAdminNotification.objects.create(
                title="No Riders Online!",
                message=f"Order #{order.id} was placed but no delivery boy is online to deliver it.",
                link='/show_orders/'
            )

    for item in cart_items:
        disc_percent = get_food_discount(item.food)
        disc_amount = float(item.food.price) * (disc_percent / 100.0)
        item_commission = float(item.food.price) * item.quantity * (resto_commission_rate / 100.0)
        OrderItem.objects.create(
            order=order,
            food=item.food,
            quantity=item.quantity,
            price=float(item.food.price),
            discount=disc_amount,
            restaurant_commission=item_commission
        )

    # Create notifications for restaurant(s) whose food was ordered
    restaurants_to_notify = set(item.food.restaurant_name for item in cart_items)
    for r_name in restaurants_to_notify:
        RestaurantNotification.objects.create(
            restaurant_name=r_name,
            message=f"New Order #{order.id} placed containing your menu items!",
            order=order
        )

    # Empty the cart
    cart_items.delete()

    return JsonResponse({'status': 'success', 'message': 'Order placed successfully using wallet!', 'redirect_url': '/success/'})


def get_payment_order(request):
    from django.http import JsonResponse
    import razorpay
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'status': 'error', 'message': 'Please login first.'}, status=403)
        
    user = get_object_or_404(Registration, id=user_id)
    cart_items = Cart.objects.filter(user=user)
    if not cart_items.exists():
        return JsonResponse({'status': 'error', 'message': 'Your cart is empty!'}, status=400)
        
    subtotal = 0
    total_discount = 0
    today = timezone.now().date()
    for item in cart_items:
        item_subtotal = item.food.price * item.quantity
        discount = Discount.objects.filter(
            product=item.food,
            active=True,
            start_date__lte=today,
            end_date__gte=today
        ).order_by('-discount_percentage').first()
        
        discount_percent = discount.discount_percentage if discount else 0
        discount_amount = item_subtotal * discount_percent / 100
        subtotal += item_subtotal
        total_discount += discount_amount
        
    from .models import PlatformSettings
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    delivery_charge = float(platform_settings.base_delivery_charge)
    final_total = float(subtotal - total_discount) + delivery_charge

    use_wallet = request.GET.get('use_wallet') == 'true'
    wallet_balance = float(user.wallet_balance)
    
    wallet_used = 0.0
    payable_amount = final_total
    
    if use_wallet:
        if wallet_balance >= final_total:
            wallet_used = final_total
            payable_amount = 0.0
        else:
            wallet_used = wallet_balance
            payable_amount = final_total - wallet_balance

    if payable_amount > 0:
        payable_amount_paise = int(payable_amount * 100)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))
        DATA = {
            "amount": payable_amount_paise,
            "currency": "INR",
            "payment_capture": 1,
        }
        try:
            razorpay_order = client.order.create(data=DATA)
            razorpay_order_id = razorpay_order['id']
            is_offline = False
        except Exception as e:
            import uuid
            razorpay_order_id = f"offline_order_{uuid.uuid4().hex[:12]}"
            is_offline = True
        
        # Save order_pay record
        Order_pay.objects.create(
            user=user,
            razorpay_order_id=razorpay_order_id,
            amount=payable_amount,
            wallet_used=wallet_used,
            status='created'
        )
        
        return JsonResponse({
            'status': 'success',
            'razorpay_order_id': razorpay_order_id,
            'amount_paise': payable_amount_paise,
            'amount': payable_amount,
            'wallet_used': wallet_used,
            'requires_razorpay': True,
            'is_offline': is_offline
        })
    else:
        return JsonResponse({
            'status': 'success',
            'amount': 0.0,
            'wallet_used': wallet_used,
            'requires_razorpay': False
        })


def wallet_page(request):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please login first.")
        return redirect('/login')

    user = get_object_or_404(Registration, id=user_id)

    if request.method == 'POST':
        amount_str = request.POST.get('amount')
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            messages.error(request, "Please enter a valid deposit amount.")
            return redirect('wallet_page')

        import razorpay
        from django.conf import settings
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))
        amount_paise = int(amount * 100)
        DATA = {
            "amount": amount_paise,
            "currency": "INR",
            "payment_capture": 1,
        }
        razorpay_order = client.order.create(data=DATA)

        context = {
            'user': user,
            'deposit_amount': amount,
            'deposit_amount_paise': amount_paise,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'trigger_payment': True,
        }
        return render(request, "wallet.html", context)

    context = {
        'user': user,
        'trigger_payment': False,
    }
    return render(request, "wallet.html", context)


def wallet_add_callback(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('/login')

    payment_id = request.GET.get('payment_id')
    amount_str = request.GET.get('amount')
    
    user = get_object_or_404(Registration, id=user_id)
    try:
        amount = float(amount_str)
        from decimal import Decimal
        user.wallet_balance += Decimal(str(amount))
        user.save()
        
        # Record Deposit Transaction
        from .models import WalletTransaction
        WalletTransaction.objects.create(
            user=user,
            amount=Decimal(str(amount)),
            transaction_type='Deposit'
        )
        messages.success(request, f"Successfully deposited ₹{amount:.2f} into your Foodeat Wallet!")
    except ValueError:
        messages.error(request, "Failed to deposit funds.")

    return redirect('wallet_page')


def get_food_discount(food_item):
    from django.utils import timezone
    today = timezone.now().date()
    discount = (
        Discount.objects.filter(
            product=food_item,
            active=True,
            start_date__lte=today,
            end_date__gte=today
        )
        .order_by('-discount_percentage')
        .first()
    )
    return discount.discount_percentage if discount else 0


@csrf_exempt
def payment_success(request):
    import json
    data = json.loads(request.body)

    razorpay_order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")

    try:
        order_payment = Order_pay.objects.get(razorpay_order_id=razorpay_order_id)
        user = order_payment.user

        # Deduct wallet contribution if any (only if status is not 'paid' yet to prevent double-deduction)
        if order_payment.status != 'paid':
            wallet_used = float(order_payment.wallet_used)
            if wallet_used > 0.005:
                from decimal import Decimal
                user.wallet_balance = max(Decimal('0.00'), user.wallet_balance - Decimal(str(wallet_used)))
                user.save()
                
                # Save a Wallet Transaction
                from .models import WalletTransaction
                WalletTransaction.objects.create(
                    user=user,
                    amount=Decimal(str(wallet_used)),
                    transaction_type='Order Payment'
                )

        order_payment.payment_id = payment_id
        order_payment.status = "paid"
        order_payment.save()

        user = order_payment.user
        cart_items = Cart.objects.filter(user=user)
        
        # Calculate totals with active discounts
        total_amount = 0
        total_discount = 0
        for item in cart_items:
            price = item.food.price
            disc_percent = get_food_discount(item.food)
            disc_amount = price * (Decimal(disc_percent) / 100)
            total_amount += price * item.quantity
            total_discount += disc_amount * item.quantity

        # Get active platform configurations
        from .models import PlatformSettings
        platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
        
        delivery_charge = float(platform_settings.base_delivery_charge)
        rider_share = float(platform_settings.rider_share_percentage)
        resto_commission_rate = float(platform_settings.restaurant_commission_percentage)

        food_subtotal = float(total_amount - total_discount)
        
        # Calculate fees
        rider_earning = delivery_charge * (rider_share / 100.0)
        restaurant_commission = float(total_amount) * (resto_commission_rate / 100.0)
        final_payable_amount = food_subtotal + delivery_charge

        # Auto-assign delivery boy (Round-Robin/Least Load logic for online boys)
        from django.db.models import Count, Q
        from .models import DeliveryBoy, RestaurantNotification, SuperAdminNotification
        
        online_boys = DeliveryBoy.objects.filter(is_verified=True, is_blocked=False).exclude(status='Off-duty')
        assigned_boy = None
        if online_boys.exists():
            today_date = timezone.localdate()
            online_boys_with_counts = online_boys.annotate(
                today_orders_count=Count(
                    'orders',
                    filter=Q(orders__order_date__date=today_date) & ~Q(orders__status='Cancelled')
                )
            ).order_by('today_orders_count', 'id')
            assigned_boy = online_boys_with_counts.first()
            if assigned_boy.status == 'Available':
                assigned_boy.status = 'Delivering'
                assigned_boy.save()

        order = Order.objects.create(
            user=user,
            razorpay_order_id=razorpay_order_id,
            payment_id=payment_id,
            total_amount=float(total_amount),
            total_discount=float(total_discount),
            final_amount=float(final_payable_amount),
            delivery_name=f"{user.first_name} {user.last_name}",
            delivery_phone=user.phone,
            delivery_address=user.city or "Not provided",
            delivery_boy=assigned_boy,
            delivery_charge=delivery_charge,
            rider_earning=rider_earning,
            restaurant_commission=restaurant_commission,
            status='paid'
        )

        if not assigned_boy:
            for _ in range(5):
                SuperAdminNotification.objects.create(
                    title="No Riders Online!",
                    message=f"Order #{order.id} was placed but no delivery boy is online to deliver it.",
                    link='/show_orders/'
                )

        for item in cart_items:
            disc_percent = get_food_discount(item.food)
            disc_amount = float(item.food.price) * (disc_percent / 100.0)
            item_commission = float(item.food.price) * item.quantity * (resto_commission_rate / 100.0)
            OrderItem.objects.create(
                order=order,
                food=item.food,
                quantity=item.quantity,
                price=float(item.food.price),
                discount=disc_amount,
                restaurant_commission=item_commission
            )

        # Create notifications for restaurant(s) whose food was ordered
        restaurants_to_notify = set(item.food.restaurant_name for item in cart_items)
        for r_name in restaurants_to_notify:
            RestaurantNotification.objects.create(
                restaurant_name=r_name,
                message=f"New Order #{order.id} placed containing your menu items!",
                order=order
            )

        cart_items.delete()
    except Order_pay.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Order not found"})

    return JsonResponse({"status": "success"})


def paymenthandler(request):
    payment_id = request.GET.get('payment_id')
    razorpay_order_id = request.GET.get('order_id')

    order_payment = get_object_or_404(Order_pay, razorpay_order_id=razorpay_order_id)
    user = order_payment.user

    # Deduct wallet contribution if any (only if status is not 'paid' yet to prevent double-deduction)
    if order_payment.status != 'paid':
        wallet_used = float(order_payment.wallet_used)
        if wallet_used > 0.005:
            user.wallet_balance = max(Decimal('0.00'), user.wallet_balance - Decimal(str(wallet_used)))
            user.save()
            
            # Save a Wallet Transaction
            from .models import WalletTransaction
            WalletTransaction.objects.create(
                user=user,
                amount=Decimal(str(wallet_used)),
                transaction_type='Order Payment'
            )

    order_payment.payment_id = payment_id
    order_payment.status = 'paid'
    order_payment.save()

    cart_items = Cart.objects.filter(user=user)

    total_amount = 0
    total_discount = 0
    for item in cart_items:
        price = item.food.price
        disc_percent = get_food_discount(item.food)
        disc_amount = price * (Decimal(disc_percent) / 100)
        total_amount += price * item.quantity
        total_discount += disc_amount * item.quantity

    # Get active platform configurations
    from .models import PlatformSettings
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    
    delivery_charge = float(platform_settings.base_delivery_charge)
    rider_share = float(platform_settings.rider_share_percentage)
    resto_commission_rate = float(platform_settings.restaurant_commission_percentage)

    food_subtotal = float(total_amount - total_discount)
    
    # Calculate fees
    rider_earning = delivery_charge * (rider_share / 100.0)
    restaurant_commission = float(total_amount) * (resto_commission_rate / 100.0)
    final_payable_amount = food_subtotal + delivery_charge

    address_id = request.GET.get('address_id')
    delivery_address = user.address or user.city or "Not provided"
    if address_id:
        try:
            saved_addr = UserAddress.objects.get(id=address_id, user=user)
            delivery_address = saved_addr.full_address
        except UserAddress.DoesNotExist:
            pass

    # Auto-assign delivery boy (Round-Robin/Least Load logic for online boys)
    from django.db.models import Count, Q
    from .models import DeliveryBoy, RestaurantNotification, SuperAdminNotification
    
    online_boys = DeliveryBoy.objects.filter(is_verified=True, is_blocked=False).exclude(status='Off-duty')
    assigned_boy = None
    if online_boys.exists():
        today_date = timezone.localdate()
        online_boys_with_counts = online_boys.annotate(
            today_orders_count=Count(
                'orders',
                filter=Q(orders__order_date__date=today_date) & ~Q(orders__status='Cancelled')
            )
        ).order_by('today_orders_count', 'id')
        assigned_boy = online_boys_with_counts.first()
        if assigned_boy.status == 'Available':
            assigned_boy.status = 'Delivering'
            assigned_boy.save()

    order = Order.objects.create(
        user=user, 
        razorpay_order_id=razorpay_order_id,
        payment_id=payment_id,
        total_amount=float(total_amount),
        total_discount=float(total_discount),
        final_amount=float(final_payable_amount),
        delivery_name=f"{user.first_name} {user.last_name}",
        delivery_phone=user.phone,
        delivery_address=delivery_address,
        delivery_boy=assigned_boy,
        delivery_charge=delivery_charge,
        rider_earning=rider_earning,
        restaurant_commission=restaurant_commission,
        status='paid'
    )

    if not assigned_boy:
        for _ in range(5):
            SuperAdminNotification.objects.create(
                title="No Riders Online!",
                message=f"Order #{order.id} was placed but no delivery boy is online to deliver it.",
                link='/show_orders/'
            )

    for item in cart_items:
        disc_percent = get_food_discount(item.food)
        disc_amount = float(item.food.price) * (disc_percent / 100.0)
        item_commission = float(item.food.price) * item.quantity * (resto_commission_rate / 100.0)
        OrderItem.objects.create(
            order=order,
            food=item.food,
            quantity=item.quantity,
            price=float(item.food.price),
            discount=disc_amount,
            restaurant_commission=item_commission
        )

    # Create notifications for restaurant(s) whose food was ordered
    restaurants_to_notify = set(item.food.restaurant_name for item in cart_items)
    for r_name in restaurants_to_notify:
        RestaurantNotification.objects.create(
            restaurant_name=r_name,
            message=f"New Order #{order.id} placed containing your menu items!",
            order=order
        )

    cart_items.delete()

    messages.success(request, "Payment successful! Your order has been placed.")
    return redirect('/menu')


def my_orders(request):
    user_id = request.session.get('user_id') 
    if not user_id:
        return redirect('/login')
    
    user = Registration.objects.get(id=user_id)
    orders = Order.objects.filter(user=user).order_by('-id')
    return render(request, 'my_orders.html', {'orders': orders})


def rate_order(request, order_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('/login')
    
    user = get_object_or_404(Registration, id=user_id)
    order = get_object_or_404(Order, id=order_id, user=user)
    
    if request.method == 'POST':
        food_rating = request.POST.get('food_rating')
        delivery_rating = request.POST.get('delivery_rating')
        if food_rating and delivery_rating:
            try:
                order.food_rating = int(food_rating)
                order.delivery_rating = int(delivery_rating)
                order.save()
                messages.success(request, "Thank you for your rating! Feedback submitted successfully.")
            except ValueError:
                messages.error(request, "Invalid rating values.")
        else:
            messages.error(request, "Please rate both food quality and delivery service.")
            
    return redirect('my_orders')


def cancel_order(request, order_id):
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please log in first.")
        return redirect('/login')
        
    user = get_object_or_404(Registration, id=user_id)
    order = get_object_or_404(Order, id=order_id, user=user)
    
    if order.status in ['paid', 'Pending']:
        order.status = 'Cancelled'
        order.delivery_boy = None
        order.save()
        
        # Mark all associated items status as 'Cancelled' as well
        OrderItem.objects.filter(order=order).update(status='Cancelled')
        
        messages.success(request, f"Order #{order.id} has been successfully cancelled.")
    else:
        messages.error(request, f"Order #{order.id} cannot be cancelled as it is already {order.status.lower()}.")
        
    return redirect('my_orders')


def download_bill(request, order_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('/login/')

    user = get_object_or_404(Registration, id=user_id)
    order = get_object_or_404(Order, id=order_id, user=user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bill_{order.id}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Navy Header background strip
    p.setFillColorRGB(0.09, 0.15, 0.25)
    p.rect(0, height - 80, width, 80, fill=1, stroke=0)
    # Orange bottom line accent
    p.setFillColorRGB(0.94, 0.44, 0.0)
    p.rect(0, height - 83, width, 3, fill=1, stroke=0)

    # Title text
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, height - 50, "ZESTY BITE — INVOICE RECEIPT")
    
    # Invoice details
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, height - 120, "INVOICE DETAILS:")
    p.setFont("Helvetica", 9)
    p.drawString(50, height - 138, f"Invoice ID: #{order.id}")
    p.drawString(50, height - 152, f"Order Date: {order.order_date.strftime('%d %b %Y %H:%M')}")
    p.drawString(50, height - 166, f"Razorpay Order ID: {order.razorpay_order_id or '—'}")
    p.drawString(50, height - 180, f"Payment ID: {order.payment_id or '—'}")

    # Customer details
    p.setFont("Helvetica-Bold", 10)
    p.drawString(width - 250, height - 120, "CUSTOMER DETAILS:")
    p.setFont("Helvetica", 9)
    p.drawString(width - 250, height - 138, f"Name: {user.first_name} {user.last_name}")
    p.drawString(width - 250, height - 152, f"Email: {user.email}")
    p.drawString(width - 250, height - 166, f"Status: {order.status}")

    # Items table header
    y_table = height - 220
    p.setFillColorRGB(0.95, 0.95, 0.95)
    p.rect(50, y_table - 20, width - 100, 20, fill=1, stroke=0)
    
    p.setFillColorRGB(0.2, 0.2, 0.2)
    p.setFont("Helvetica-Bold", 9)
    p.drawString(55, y_table - 14, "#")
    p.drawString(85, y_table - 14, "Food Item")
    p.drawRightString(300, y_table - 14, "Price")
    p.drawCentredString(360, y_table - 14, "Qty")
    p.drawRightString(440, y_table - 14, "Discount")
    p.drawRightString(540, y_table - 14, "Subtotal")

    # Draw items
    y_row = y_table - 40
    order_items = order.orderitem_set.all()
    calculated_subtotal = 0.0
    
    p.setFont("Helvetica", 9)
    for idx, item in enumerate(order_items, start=1):
        if y_row < 100:  # Page break condition
            p.showPage()
            y_row = height - 50
            p.setFont("Helvetica", 9)
            
        p.setFillColorRGB(0.3, 0.3, 0.3)
        p.drawString(55, y_row, str(idx))
        p.drawString(85, y_row, item.food.food_name)
        p.drawRightString(300, y_row, f"₹{item.price:.2f}")
        p.drawCentredString(360, y_row, str(item.quantity))
        p.drawRightString(440, y_row, f"₹{item.discount:.2f}")
        p.drawRightString(540, y_row, f"₹{item.subtotal:.2f}")
        
        calculated_subtotal += float(item.subtotal)
        
        # Grid line
        p.setStrokeColorRGB(0.92, 0.92, 0.92)
        p.setLineWidth(0.5)
        p.line(50, y_row - 6, width - 50, y_row - 6)
        y_row -= 22

    # Draw summary table (Subtotal, GST, Grand Total)
    y_summary = y_row - 15
    if y_summary < 120:
        p.showPage()
        y_summary = height - 80

    # Draw lines
    p.setStrokeColorRGB(0.8, 0.8, 0.8)
    p.line(width - 250, y_summary, width - 50, y_summary)
    
    p.setFillColorRGB(0.3, 0.3, 0.3)
    p.setFont("Helvetica", 9)
    p.drawString(width - 250, y_summary - 18, "Subtotal:")
    p.drawRightString(width - 55, y_summary - 18, f"₹{calculated_subtotal:.2f}")
    
    # Calculate 5% GST
    gst_tax = calculated_subtotal * 0.05
    p.drawString(width - 250, y_summary - 34, "GST (5%):")
    p.drawRightString(width - 55, y_summary - 34, f"₹{gst_tax:.2f}")
    
    # Grand Total
    p.setStrokeColorRGB(0.7, 0.7, 0.7)
    p.line(width - 250, y_summary - 42, width - 50, y_summary - 42)
    p.setFillColorRGB(0.94, 0.44, 0.0) # Brand orange
    p.setFont("Helvetica-Bold", 12)
    p.drawString(width - 250, y_summary - 58, "Grand Total:")
    p.drawRightString(width - 55, y_summary - 58, f"₹{order.final_amount:.2f}")

    # Notes section
    y_notes = y_summary - 110
    if y_notes < 80:
        p.showPage()
        y_notes = height - 100
        
    p.setFillColorRGB(0.2, 0.2, 0.2)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y_notes, "INVOICE NOTES:")
    p.setFont("Helvetica", 8.5)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.drawString(50, y_notes - 18, "1. This is a computer-generated invoice transaction receipt. No signature is required.")
    p.drawString(50, y_notes - 30, "2. For refund or support requests, email contact@zestybite.com quoting the Invoice ID.")

    # Copyright/Footer
    p.setFont("Helvetica-Bold", 8)
    p.setFillColorRGB(0.6, 0.6, 0.6)
    p.drawCentredString(width / 2, 45, "Thank you for dining with Zesty Bite!")
    p.setFont("Helvetica", 8)
    p.drawCentredString(width / 2, 32, "© 2026 Zesty Bite Private Limited. All rights reserved.")

    p.showPage()
    p.save()

    return response


    #--------------------------- Admin Restaurant---------------------------
def admin_profile(request):
    if 'admin_id' not in request.session:
        return redirect('adminlogin')
    admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    return render(request, 'admin_owner/admin_profile.html', {'admin_user': admin_user})


def admin_profile_edit(request, admin_id):
    if 'admin_id' not in request.session:
        messages.error(request, "You must log in first.")
        return redirect('adminlogin')

    if request.session.get('admin_id') != admin_id:
        messages.error(request, "You can edit only your own profile.")
        return redirect('admin_profile')

    admin_user = get_object_or_404(AdminOwner, id=admin_id)

    if request.method == "POST":
        old_restaurant_name = admin_user.restaurant_name
        full_name = request.POST.get('full_name', '').strip()
        restaurant_name = request.POST.get('restaurant_name', '').strip()
        restaurant_address = admin_user.restaurant_address or 'N/A'
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not full_name or not restaurant_name or not email:
            messages.error(request, "Please fill all required profile details.")
            return render(request, 'admin_owner/admin_profile_edit.html', {'admin_user': admin_user})

        if AdminOwner.objects.filter(email=email).exclude(id=admin_user.id).exists():
            messages.error(request, "This email is already registered with another owner.")
            return render(request, 'admin_owner/admin_profile_edit.html', {'admin_user': admin_user})

        admin_user.full_name = full_name
        admin_user.restaurant_name = restaurant_name
        admin_user.restaurant_address = restaurant_address
        admin_user.email = email
        if password:
            admin_user.password = password

        if 'profile_image' in request.FILES and request.FILES['profile_image']:
            admin_user.profile_image = request.FILES['profile_image']

        if 'aadhar_card_img' in request.FILES and request.FILES['aadhar_card_img']:
            admin_user.aadhar_card_img = request.FILES['aadhar_card_img']

        admin_user.save()
        restaurant_records = AddResto.objects.filter(name__iexact=old_restaurant_name)
        if old_restaurant_name != restaurant_name:
            FoodItem.objects.filter(restaurant_name=old_restaurant_name).update(restaurant_name=restaurant_name)
        restaurant_records.update(
            name=restaurant_name,
            email=email,
            address=restaurant_address
        )

        request.session['admin_name'] = admin_user.full_name
        request.session['restaurant_name'] = admin_user.restaurant_name
        messages.success(request, "Profile updated successfully.")
        return redirect('admin_profile')

    return render(request, 'admin_owner/admin_profile_edit.html', {'admin_user': admin_user})


def dashboard(request):
    if 'admin_id' not in request.session:
        return redirect('adminlogin')

    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        from django.contrib import messages
        messages.error(request, "Invalid admin session. Please log in again.")
        return redirect('adminlogin')

    from django.utils import timezone
    from datetime import datetime
    from django.db.models import Sum, Count, F
    from django.db.models.functions import TruncDate
    from .models import PlatformSettings
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    commission_rate = float(platform_settings.restaurant_commission_percentage)

    # Date filtering - defaults to today
    selected_date_str = request.GET.get('date')
    today = timezone.now().date()
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Fetch total items in the owner's restaurant
    total_items = FoodItem.objects.filter(restaurant_name=admin_user.restaurant_name).count()

    # Fetch total restaurants under this name
    restaurants = AddResto.objects.filter(name__iexact=admin_user.restaurant_name)
    total_restaurants = restaurants.count()

    # Fetch today's bookings for these restaurants
    total_bookings = Booking_resto.objects.filter(
        restaurant__in=restaurants,
        booking_time__date=selected_date
    ).count()

    # Fetch total discounts for products in the restaurant
    total_discounts = Discount.objects.filter(product__restaurant_name=admin_user.restaurant_name).count()

    # Lifetime metrics
    lifetime_sales_query = OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name
    ).exclude(order__status='Cancelled').aggregate(
        total=Sum(F('price') * F('quantity') - F('discount') * F('quantity')),
        commission=Sum('restaurant_commission')
    )
    lifetime_sales = float(lifetime_sales_query['total']) if lifetime_sales_query['total'] is not None else 0.0
    lifetime_commission = float(lifetime_sales_query['commission']) if lifetime_sales_query['commission'] is not None else 0.0
    lifetime_net_payout = lifetime_sales - lifetime_commission

    lifetime_orders = OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name
    ).exclude(order__status='Cancelled').values('order').distinct().count()

    # Selected Date metrics (Today by default)
    selected_sales_query = OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name,
        order__order_date__date=selected_date
    ).exclude(order__status='Cancelled').aggregate(
        total=Sum(F('price') * F('quantity') - F('discount') * F('quantity')),
        commission=Sum('restaurant_commission')
    )
    selected_sales = float(selected_sales_query['total']) if selected_sales_query['total'] is not None else 0.0
    selected_commission = float(selected_sales_query['commission']) if selected_sales_query['commission'] is not None else 0.0
    selected_net_payout = selected_sales - selected_commission

    selected_orders = OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name,
        order__order_date__date=selected_date
    ).exclude(order__status='Cancelled').values('order').distinct().count()

    # Today's metrics (always today, regardless of selected_date filter)
    today_sales_query = OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name,
        order__order_date__date=today
    ).exclude(order__status='Cancelled').aggregate(
        total=Sum(F('price') * F('quantity') - F('discount') * F('quantity')),
        commission=Sum('restaurant_commission')
    )
    today_sales = float(today_sales_query['total']) if today_sales_query['total'] is not None else 0.0
    today_commission = float(today_sales_query['commission']) if today_sales_query['commission'] is not None else 0.0
    today_net_payout = today_sales - today_commission

    today_orders = OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name,
        order__order_date__date=today
    ).exclude(order__status='Cancelled').values('order').distinct().count()

    # Fetch restaurant-specific order items (orders that have food from this restaurant) for the SELECTED DATE
    order_items = list(OrderItem.objects.filter(
        food__restaurant_name=admin_user.restaurant_name,
        order__order_date__date=selected_date
    ).select_related('order', 'food').order_by('-order__order_date'))

    for item in order_items:
        gross_item_amount = float(item.price) * item.quantity
        item.commission_amount = gross_item_amount * (commission_rate / 100.0)
        item.net_earning = float(item.subtotal) - item.commission_amount

    # Day-wise payment and order count stats (filtered by selected_date, which defaults to today)
    day_wise_query = (
        OrderItem.objects.filter(
            food__restaurant_name=admin_user.restaurant_name,
            order__order_date__date=selected_date
        )
        .exclude(order__status='Cancelled')
        .values('order__order_date__date')
        .annotate(
            order_count=Count('order', distinct=True),
            total_amount=Sum(F('price') * F('quantity') - F('discount') * F('quantity')),
            gross_amount=Sum(F('price') * F('quantity'))
        )
        .order_by('-order__order_date__date')
    )

    day_wise_payments = []
    for entry in day_wise_query:
        entry_date = entry['order__order_date__date']
        if entry_date is not None:
            net_amount = float(entry['total_amount']) if entry['total_amount'] is not None else 0.0
            gross_amount = float(entry['gross_amount']) if entry['gross_amount'] is not None else 0.0
            commission = gross_amount * (commission_rate / 100.0)
            net_payout = net_amount - commission
            day_wise_payments.append({
                'date': entry_date,
                'order_count': entry['order_count'],
                'total_amount': net_amount,
                'commission': commission,
                'net_payout': net_payout,
            })

    from django.utils import timezone
    import datetime
    cutoff_time = timezone.now() - datetime.timedelta(days=1)
    notifications = RestaurantNotification.objects.filter(
        restaurant_name=admin_user.restaurant_name,
        created_at__gte=cutoff_time
    ).order_by('-created_at')[:15]

    max_notif = RestaurantNotification.objects.filter(
        restaurant_name=admin_user.restaurant_name
    ).order_by('-id').first()
    max_notif_id = max_notif.id if max_notif else 0

    has_unread = RestaurantNotification.objects.filter(
        restaurant_name=admin_user.restaurant_name,
        is_read=False
    ).exists()

    context = {
        'admin_user': admin_user,
        'total_items': total_items,
        'total_restaurants': total_restaurants,
        'total_bookings': total_bookings,
        'total_discounts': total_discounts,
        'order_items': order_items,
        'lifetime_sales': lifetime_sales,
        'lifetime_orders': lifetime_orders,
        'lifetime_net_payout': lifetime_net_payout,
        'lifetime_commission': lifetime_commission,
        'selected_sales': selected_sales,
        'selected_commission': selected_commission,
        'selected_net_payout': selected_net_payout,
        'selected_orders': selected_orders,
        'selected_date': selected_date,
        'today': today,
        'today_sales': today_sales,
        'today_orders': today_orders,
        'today_net_payout': today_net_payout,
        'today_commission': today_commission,
        'day_wise_payments': day_wise_payments,
        'notifications': notifications,
        'max_notif_id': max_notif_id,
        'has_unread': has_unread,
        'commission_rate': commission_rate,
    }
    return render(request, 'admin_owner/dashboard.html', context)


from django.http import JsonResponse

def check_notifications(request):
    if 'admin_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    
    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
        
    last_id = request.GET.get('last_id', 0)
    try:
        last_id = int(last_id)
    except ValueError:
        last_id = 0
        
    from django.utils import timezone
    import datetime
    cutoff_time = timezone.now() - datetime.timedelta(days=1)
    new_notifications = RestaurantNotification.objects.filter(
        restaurant_name=admin_user.restaurant_name,
        created_at__gte=cutoff_time,
        id__gt=last_id
    ).order_by('id')
    notif_list = []
    from django.utils import timezone
    for notif in new_notifications:
        notif_list.append({
            'id': notif.id,
            'message': notif.message,
            'created_at': timezone.localtime(notif.created_at).strftime('%d %b, %I:%M %p')
        })
        
    return JsonResponse({'status': 'success', 'notifications': notif_list})

def mark_notifications_read(request):
    if 'admin_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    
    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
        
    from .models import RestaurantNotification
    RestaurantNotification.objects.filter(
        restaurant_name=admin_user.restaurant_name,
        is_read=False
    ).update(is_read=True)
    
    return JsonResponse({'status': 'success'})



def adminheader(request):
    return render(request, 'admin_owner/adminheader.html')

otp_store = {} 
def adminregister(request):
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    
    if request.method == 'POST':
        form = AdminOwnerRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data['email']
            if AdminOwner.objects.filter(email=email).exists():
                messages.error(request, "This email is already registered.")
                return render(request, 'admin_owner/adminregister.html', {'form': form})
                
            otp = str(random.randint(100000, 999999))
            
            temp_profile_path = ""
            if request.FILES.get('profile_image'):
                profile_file = request.FILES['profile_image']
                temp_profile_path = default_storage.save(f"temp_uploads/{random.randint(1000, 9999)}_{profile_file.name}", ContentFile(profile_file.read()))
                
            temp_aadhar_path = ""
            if request.FILES.get('aadhar_card_img'):
                aadhar_file = request.FILES['aadhar_card_img']
                temp_aadhar_path = default_storage.save(f"temp_uploads/{random.randint(1000, 9999)}_{aadhar_file.name}", ContentFile(aadhar_file.read()))
                
            reg_data = {
                'full_name': form.cleaned_data['full_name'],
                'email': email,
                'password': form.cleaned_data['password'],
                'restaurant_name': form.cleaned_data['restaurant_name'],
                'temp_profile_image': temp_profile_path,
                'temp_aadhar_card_img': temp_aadhar_path,
            }
            
            request.session['temp_owner_reg'] = reg_data
            request.session['owner_reg_otp'] = otp
            
            # Send Email
            subject = 'Verification OTP for Restaurant Registration - Foodeat'
            message = f"Hello {reg_data['full_name']},\n\nYour OTP for verifying your restaurant registration on Foodeat is: {otp}\n\nPlease enter this OTP on the verification page to complete your email verification.\n\nBest regards,\nFoodeat Team"
            
            # Print the OTP to console logs immediately
            print(f"\n========================================\nRESTAURANT OWNER OTP FOR {email}: {otp}\n========================================\n")

            import threading
            def send_email_thread():
                try:
                    import os
                    api_key = os.environ.get('BREVO_API_KEY')
                    print(f"DEBUG: BREVO_API_KEY status: {'Loaded (len=' + str(len(api_key)) + ')' if api_key else 'NOT LOADED'}", flush=True)
                    send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
                    print(f"Async email sending completed successfully for {email}", flush=True)
                except Exception as e:
                    print(f"Async email sending failed for {email}: {e}", flush=True)

            threading.Thread(target=send_email_thread).start()
            messages.success(request, "An OTP has been generated. If you don't receive it, please check the Render logs.")
            return redirect('admin_verify_otp')
    else:
        form = AdminOwnerRegisterForm()

    return render(request, 'admin_owner/adminregister.html', {'form': form})


def admin_verify_otp(request):
    from django.core.files.storage import default_storage
    
    if 'temp_owner_reg' not in request.session or 'owner_reg_otp' not in request.session:
        messages.error(request, "No registration session found. Please register first.")
        return redirect('adminregister')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        expected_otp = request.session.get('owner_reg_otp')

        if entered_otp == expected_otp:
            reg_data = request.session.get('temp_owner_reg')
            
            # Create AdminOwner
            admin_owner = AdminOwner(
                full_name=reg_data['full_name'],
                email=reg_data['email'],
                password=reg_data['password'],
                restaurant_name=reg_data['restaurant_name'],
                is_approved=False
            )
            
            # Save files if they exist
            if reg_data.get('temp_profile_image') and default_storage.exists(reg_data['temp_profile_image']):
                profile_file = default_storage.open(reg_data['temp_profile_image'])
                admin_owner.profile_image.save(os.path.basename(reg_data['temp_profile_image']), File(profile_file), save=False)
                
            if reg_data.get('temp_aadhar_card_img') and default_storage.exists(reg_data['temp_aadhar_card_img']):
                aadhar_file = default_storage.open(reg_data['temp_aadhar_card_img'])
                admin_owner.aadhar_card_img.save(os.path.basename(reg_data['temp_aadhar_card_img']), File(aadhar_file), save=False)
                
            admin_owner.save()
            
            # Clean up temp files
            try:
                if reg_data.get('temp_profile_image') and default_storage.exists(reg_data['temp_profile_image']):
                    default_storage.delete(reg_data['temp_profile_image'])
                if reg_data.get('temp_aadhar_card_img') and default_storage.exists(reg_data['temp_aadhar_card_img']):
                    default_storage.delete(reg_data['temp_aadhar_card_img'])
            except Exception:
                pass
                
            # Clean session
            request.session.pop('temp_owner_reg', None)
            request.session.pop('owner_reg_otp', None)
            
            messages.success(request, "OTP verified successfully! Your account is pending approval by the Super Admin.")
            return redirect('adminlogin')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, 'admin_owner/admin_verify_otp.html')


def adminlogin(request):
    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                admin = AdminOwner.objects.get(email=email)  
                if admin.password == password:  
                    if not admin.is_approved:
                        messages.error(request, "Your restaurant owner account is pending approval by the Super Admin.")
                        return render(request, 'admin_owner/adminlogin.html', {'form': form})
                    request.session['admin_id'] = admin.id
                    request.session['admin_name'] = admin.full_name
                    request.session['restaurant_name'] = admin.restaurant_name  
                    messages.success(request, f"Welcome, {admin.full_name}!")
                    return redirect('/dashboard') 
                else:
                    messages.error(request, "Incorrect password")
            except AdminOwner.DoesNotExist:
                messages.error(request, "Admin with this email does not exist")
    else:
        form = AdminLoginForm()
    return render(request, 'admin_owner/adminlogin.html', {'form': form})

def adminlogout(request):
    if 'admin_id' in request.session:
        del request.session['admin_id']
    if 'admin_name' in request.session:
        del request.session['admin_name']
    if 'restaurant_name' in request.session:
        del request.session['restaurant_name']

    messages.success(request, "Admin has been logged out successfully.")
    return redirect('adminlogin')


def admin_forgot_password(request):
    if 'admin_otp_sent' not in request.session:
        request.session['admin_otp_sent'] = False
        request.session['admin_otp_verified'] = False

    form = None
    if request.method == 'POST':
        if not request.session['admin_otp_sent']:
            form = ForgotPasswordForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                try:
                    user = AdminOwner.objects.get(email=email)
                    otp = randint(100000, 999999)
                    request.session['admin_reset_email'] = email
                    request.session['admin_otp_code'] = str(otp)
                    request.session['admin_otp_sent'] = True
                    request.session['admin_otp_verified'] = False               
                    
                    subject = 'Foodeat - Admin Owner Password Reset Code'
                    message_text = f'Your verification code is: {otp}'
                    html_message = f"""
                    <div style="font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; border-radius: 24px; background: #ffffff; border: 1px solid #e2e8f0; color: #1e293b; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
                        <div style="text-align: center; margin-bottom: 25px;">
                            <span style="font-size: 28px; font-weight: 800; color: #ff6f00; letter-spacing: -1px;">Foodeat</span>
                            <span style="display: block; font-size: 10px; font-weight: 700; text-transform: uppercase; color: #94a3b8; letter-spacing: 2px; margin-top: 5px;">Admin Security Verification</span>
                        </div>
                        <div style="border-top: 3px solid #ff6f00; padding-top: 25px;">
                            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">Hello {user.full_name},</p>
                            <p style="font-size: 14px; line-height: 1.6; margin: 0 0 25px 0; color: #475569;">We received a request to reset your restaurant owner password. Use the following security verification code to proceed. This code is active for 10 minutes.</p>
                            
                            <div style="text-align: center; margin: 30px 0; background: #f8fafc; border-radius: 16px; padding: 25px; border: 1px dashed #cbd5e1;">
                                <span style="display: block; font-size: 10px; font-weight: 800; text-transform: uppercase; color: #64748b; letter-spacing: 1.5px; margin-bottom: 8px;">Your Verification Code</span>
                                <span style="font-family: monospace; font-size: 36px; font-weight: 900; color: #0f172a; letter-spacing: 6px; padding-left: 6px;">{otp}</span>
                            </div>
                            
                            <p style="font-size: 12px; line-height: 1.6; color: #64748b; margin: 25px 0 0 0;">If you did not request a password reset, please ignore this email or contact support immediately.</p>
                        </div>
                        <div style="border-top: 1px solid #e2e8f0; margin-top: 35px; padding-top: 20px; text-align: center; font-size: 11px; color: #94a3b8;">
                            &copy; 2026 Foodeat. All rights reserved.
                        </div>
                    </div>
                    """
                    
                    try:
                        send_mail(
                            subject,
                            message_text,
                            settings.EMAIL_HOST_USER,
                            [email],
                            fail_silently=False,
                            html_message=html_message
                        )
                        messages.success(request, f"OTP sent to {email}")
                    except Exception:
                        messages.warning(request, f"For local testing, your verification OTP code is: {otp}")
                    
                    return redirect('admin_forgot_password')
                except AdminOwner.DoesNotExist:
                    messages.error(request, "Email not registered as Restaurant Owner")
        
        elif request.session.get('admin_otp_sent') and not request.session.get('admin_otp_verified'):
            form = OTPForm(request.POST)
            if form.is_valid():
                otp_input = form.cleaned_data['otp']
                if otp_input == request.session.get('admin_otp_code'):
                    request.session['admin_otp_verified'] = True
                    messages.success(request, "OTP verified. Please set your new password.")
                    return redirect('admin_forgot_password')
                else:
                    messages.error(request, "Invalid OTP. Try again.")    
        
        elif request.session.get('admin_otp_verified'):
            form = ResetPasswordForm(request.POST)
            if form.is_valid():
                password = form.cleaned_data['password']
                email = request.session.get('admin_reset_email')
                try:
                    user = AdminOwner.objects.get(email=email)
                    user.password = password
                    user.save()
                    messages.success(request, "Password reset successful!")               
                    
                    request.session.pop('admin_otp_sent', None)
                    request.session.pop('admin_otp_verified', None)
                    request.session.pop('admin_otp_code', None)
                    request.session.pop('admin_reset_email', None)
                    return redirect('adminlogin')
                except AdminOwner.DoesNotExist:
                    messages.error(request, "Something went wrong. Try again.")   
    else:
        if not request.session.get('admin_otp_sent'):
            form = ForgotPasswordForm()
        elif request.session.get('admin_otp_sent') and not request.session.get('admin_otp_verified'):
            form = OTPForm()
        else:
            form = ResetPasswordForm()

    return render(request, 'admin_owner/admin_forgot_password.html', {'form': form})

def addfood(request):
    if 'admin_id' not in request.session:
        messages.error(request, "You must log in first.")
        return redirect('adminlogin') 

    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        messages.error(request, "Invalid admin session. Please log in again.")
        return redirect('adminlogin')

    if request.method == "POST":
        form = FoodItemForm(request.POST, request.FILES)
        if form.is_valid():
            food = form.save(commit=False)
            food.restaurant_name = admin_user.restaurant_name  
            food.save()
            messages.success(request, "Food item added successfully!")
            return redirect("food_list")
    else:
        form = FoodItemForm(initial={'restaurant_name': admin_user.restaurant_name})
        form.fields['restaurant_name'].widget.attrs['readonly'] = True

    return render(request, "admin_owner/addfood.html", {
        "form": form,
        "admin_user": admin_user, 
    })


def food_list(request):
    if 'admin_id' not in request.session:
        messages.error(request, "You must log in first.")
        return redirect('adminlogin')

    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        messages.error(request, "Invalid admin session. Please log in again.")
        return redirect('adminlogin')

    foods = FoodItem.objects.filter(restaurant_name=admin_user.restaurant_name)

    foods_with_discount = []
    for food in foods:
        active_discount = food.discounts.filter(active=True).first()
        foods_with_discount.append({
            "food": food,
            "discount": active_discount
        })

    return render(request, "admin_owner/food_list.html", {
        "foods_with_discount": foods_with_discount,
        "admin_user": admin_user,
    })

def view_food_items(request): 
    restaurant_name = request.session.get('restaurant_name')
    if restaurant_name: 
        food_items = FoodItem.objects.filter(restaurant_name=restaurant_name)
    else: 
        food_items = FoodItem.objects.none()
        messages.error(request, "Please log in to view your food items.")

    return render(request, 'view_food.html', {'food_items': food_items})



def menu_page(request):
    food_items = FoodItem.objects.all()
    restaurant_status = {}
    for resto in AddResto.objects.all():
        restaurant_status[resto.name.lower()] = resto.is_accepting_orders
    for owner in AdminOwner.objects.all():
        restaurant_status[owner.restaurant_name.lower()] = owner.is_accepting_orders

    today = timezone.now().date()

    for item in food_items:
        item.restaurant_is_accepting_orders = restaurant_status.get(item.restaurant_name.lower(), True)
        item.active_discount = item.discounts.filter(
            start_date__lte=today,
            end_date__gte=today,
            active=True
        ).first() 

        if item.active_discount:
            discount_percent = Decimal(item.active_discount.discount_percentage) / Decimal(100)
            item.discounted_price = item.price * (Decimal(1) - discount_percent)
        else:
            item.discounted_price = item.price

    return render(request, 'menu.html', {'food_items': food_items})


def edit_food(request, food_id):
    admin_id = request.session.get('admin_id')
    food = get_object_or_404(FoodItem, pk=food_id)

    if request.method == "POST":
        form = FoodItemForm(request.POST, request.FILES, instance=food) 
        if form.is_valid():
            form.save()
            messages.success(request, f"Food item '{food.food_name}' updated successfully!")
            return redirect('food_list')
    else:
        form = FoodItemForm(instance=food) 

    return render(request, 'admin_owner/edit_food.html', {'form': form})

def delete_food(request, id):
    food = get_object_or_404(FoodItem, id=id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                food.delete()
        except Exception as e:
            print("Error deleting food:", e)
        return redirect('food_list')
    return redirect('food_list')

def toggle_food_availability(request, food_id):
    if 'admin_id' not in request.session:
        messages.error(request, "You must log in first.")
        return redirect('adminlogin')

    admin_user = get_object_or_404(AdminOwner, id=request.session['admin_id'])
    food = get_object_or_404(FoodItem, id=food_id, restaurant_name=admin_user.restaurant_name)

    if request.method == 'POST':
        food.is_available = not food.is_available
        food.save(update_fields=['is_available'])
        status = "available" if food.is_available else "unavailable"
        messages.success(request, f"{food.food_name} marked as {status}.")

    return redirect('food_list')

def bulk_delete_foods(request):
    if request.method == 'POST':
        selected_food_ids = request.POST.getlist('selected_foods')
        if selected_food_ids:
            try:
                with transaction.atomic():
                    deleted_count, _ = FoodItem.objects.filter(id__in=selected_food_ids).delete()
                    messages.success(request, f"{deleted_count} food item(s) deleted successfully.")
            except Exception as e:
                messages.error(request, f"Error deleting selected items: {e}")
        else:
            messages.warning(request, "No food items selected for deletion.")
    return redirect('food_list')



def quick_add_discount(request):
    if 'admin_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('adminlogin')

    if request.method == "POST":
        food_id = request.POST.get('product')
        discount_percentage = request.POST.get('discount_percentage')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        from datetime import datetime
        from django.utils import timezone
        today = timezone.now().date()

        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Invalid date format.")
            return redirect('food_list')

        if start_date_obj < today:
            messages.error(request, "Start date cannot be in the past.")
            return redirect('food_list')

        if end_date_obj < start_date_obj:
            messages.error(request, "End date must be greater than or equal to start date.")
            return redirect('food_list')

        food_item = get_object_or_404(FoodItem, id=food_id)
        
        # Create or update discount
        discount, created = Discount.objects.get_or_create(
            product=food_item,
            defaults={
                'discount_percentage': int(discount_percentage),
                'start_date': start_date,
                'end_date': end_date,
                'active': True
            }
        )
        if not created:
            discount.discount_percentage = int(discount_percentage)
            discount.start_date = start_date
            discount.end_date = end_date
            discount.active = True
            discount.save()
            
        messages.success(request, f"Discount set to {discount_percentage}% for {food_item.food_name}!")
    return redirect('food_list')


def add_discount(request):
    if 'admin_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('adminlogin')

    admin_user = AdminOwner.objects.get(id=request.session['admin_id'])

    products = FoodItem.objects.filter(restaurant_name=admin_user.restaurant_name)

    if request.method == "POST":
        form = DiscountForm(request.POST)
        form.fields['product'].queryset = products  
        if form.is_valid():
            form.save()
            messages.success(request, "Discount added successfully!")
            return redirect('discount_list')
    else:
        form = DiscountForm()
        form.fields['product'].queryset = products

    return render(request, "admin_owner/discount.html", {
        "form": form,
        "products": products
    })


def discount_list(request):
    if 'admin_id' not in request.session:
        from django.contrib import messages
        messages.error(request, "You must log in first.")
        return redirect('adminlogin')

    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        from django.contrib import messages
        messages.error(request, "Invalid admin session. Please log in again.")
        return redirect('adminlogin')

    today_date = date.today()
    discounts = Discount.objects.filter(product__restaurant_name=admin_user.restaurant_name).select_related('product')

    for discount in discounts:
        if discount.end_date <= today_date and discount.active:
            discount.active = False
            discount.save()

    return render(request, 'admin_owner/discount_list.html', {
        'discounts': discounts,
        'today_date': today_date,
        'admin_user': admin_user
    })


def edit_discount(request, discount_id):
    discount = get_object_or_404(Discount, id=discount_id)

    if request.method == 'POST':
        form = DiscountForm(request.POST, instance=discount)
        if form.is_valid():
            form.save()
            return redirect('discount_list')  
    else:
        form = DiscountForm(instance=discount)

    return render(request, 'admin_owner/edit_discount.html', {'form': form, 'discount': discount})


def delete_discount(request, id):
    discount = get_object_or_404(Discount, id=id)
    if request.method == "POST":
        discount.delete()
        messages.success(request, "Discount deleted successfully!")
        referer = request.META.get('HTTP_REFERER')
        if referer and 'food_list' in referer:
            return redirect('food_list')
        return redirect("discount_list") 
    return redirect("discount_list")


def toggle_discount_status(request, discount_id):
    if 'admin_id' not in request.session:
        messages.error(request, "Please log in first.")
        return redirect('adminlogin')

    discount = get_object_or_404(Discount, id=discount_id)
    discount.active = not discount.active
    discount.save()
    messages.success(request, f"Discount status updated to {'Active' if discount.active else 'Inactive'}.")
    return redirect('discount_list')


def add_resto(request):
    if 'admin_id' not in request.session:
        messages.error(request, "You must log in first.")
        return redirect('adminlogin')

    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    except AdminOwner.DoesNotExist:
        messages.error(request, "Invalid admin session. Please log in again.")
        return redirect('adminlogin')

    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['name'] = admin_user.restaurant_name
        post_data['email'] = admin_user.email
        form = AddRestoForm(post_data, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('resto_list') 
    else:
        form = AddRestoForm(initial={
            'name': admin_user.restaurant_name,
            'email': admin_user.email,
        })

    form.fields['name'].widget.attrs['readonly'] = True
    form.fields['email'].widget.attrs['readonly'] = True
    form.fields['address'].widget.attrs['readonly'] = True

    return render(request, 'admin_owner/add_restaurant.html', {
        'form': form,
        'admin_user': admin_user,
    })


def resto_list(request):

    admin_id = request.session.get('admin_id')
    restaurant_name = request.session.get('restaurant_name')

    if not admin_id:
        return redirect('/adminlogin/')

    try:
        admin_owner = AdminOwner.objects.get(id=admin_id)
    except AdminOwner.DoesNotExist:
        return redirect('/adminlogin/')

    restos = AddResto.objects.filter(name__iexact=restaurant_name)

    return render(request, 'admin_owner/restaurant_list.html', {
        'restos': restos,
        'admin_owner': admin_owner,
        'admin_user': admin_owner
    })

def toggle_resto_status(request, id):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('/adminlogin/')

    next_url = request.META.get('HTTP_REFERER')
    if not next_url:
        next_url = 'resto_list'

    try:
        admin_owner = AdminOwner.objects.get(id=admin_id)
        if admin_owner.is_blocked:
            messages.error(request, "Your owner account is BLOCKED by the Super Admin.")
            return redirect(next_url)
    except AdminOwner.DoesNotExist:
        return redirect('/adminlogin/')

    if request.method == 'POST':
        restaurant = get_object_or_404(AddResto, id=id)
        restaurant.is_accepting_orders = not restaurant.is_accepting_orders
        restaurant.save()
        status = "Open" if restaurant.is_accepting_orders else "Closed"
        messages.success(request, f"{restaurant.name} is now {status}.")

    return redirect(next_url)
    
def edit_restaurant(request, id):
    resto = get_object_or_404(AddResto, id=id)

    if request.method == 'POST':
        form = AddRestoForm(request.POST, request.FILES, instance=resto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Restaurant updated successfully!')
            return redirect('resto_list')  
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddRestoForm(instance=resto)

    form.fields['name'].widget.attrs['readonly'] = True
    form.fields['email'].widget.attrs['readonly'] = True
    form.fields['address'].widget.attrs['readonly'] = True

    return render(request, 'admin_owner/edit_restaurant.html', {'form': form, 'resto': resto})

def delete_restaurant(request, id):
    restaurant = get_object_or_404(AddResto, id=id)
    restaurant.delete()
    messages.success(request, "Restaurant deleted successfully!")
    return redirect('resto_list') 

def delete_all_restaurants(request):
    if request.method == 'POST':
        AddResto.objects.all().delete()
        return JsonResponse({'status': 'success', 'message': 'All restaurants deleted successfully!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)    
   

def book_table(request, restaurant_id):
    restaurant = get_object_or_404(AddResto, id=restaurant_id)
    closing_time = normalize_restaurant_closing_time(restaurant.opening_time, restaurant.closing_time)

    if not restaurant.is_accepting_orders:
        messages.error(request, f"{restaurant.name} is currently closed for booking and orders.")
        return redirect('restaurant_list')

    today = timezone.localdate()
    booked_members = restaurant.bookings_resto.filter(
        booking_time__date=today
    ).exclude(status='Cancelled').aggregate(total=Sum('members'))['total'] or 0
    available_seats = restaurant.seating_capacity - booked_members

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        contact_number = request.POST.get('contact_number')
        members = request.POST.get('members')
        booking_time_value = request.POST.get('booking_time')

        if not (customer_name and contact_number and members and booking_time_value):
            messages.error(request, "All required fields must be filled.")
            return redirect('book_table', restaurant_id=restaurant.id)

        if not contact_number.isdigit() or len(contact_number) != 10:
            messages.error(request, "Mobile number must be 10 digits.")
            return redirect('book_table', restaurant_id=restaurant.id)

        try:
            members = int(members)
        except ValueError:
            messages.error(request, "Please enter a valid number of members.")
            return redirect('book_table', restaurant_id=restaurant.id)

        try:
            booking_time = datetime.strptime(booking_time_value, "%Y-%m-%dT%H:%M")
            if timezone.is_naive(booking_time):
                booking_time = timezone.make_aware(booking_time, timezone.get_default_timezone())
        except ValueError:
            messages.error(request, "Please select a valid booking date and time.")
            return redirect('book_table', restaurant_id=restaurant.id)

        selected_time = timezone.localtime(booking_time).time()
        if not is_booking_time_within_hours(selected_time, restaurant.opening_time, restaurant.closing_time):
            messages.error(
                request,
                f"Booking is allowed only between {format_restaurant_time(restaurant.opening_time)} "
                f"and {format_restaurant_time(closing_time)}."
            )
            return redirect('book_table', restaurant_id=restaurant.id)

        if booking_time < timezone.now():
            messages.error(request, "Please select a future booking time.")
            return redirect('book_table', restaurant_id=restaurant.id)

        booked_members = restaurant.bookings_resto.filter(
            booking_time__date=timezone.localtime(booking_time).date()
        ).exclude(status='Cancelled').aggregate(total=Sum('members'))['total'] or 0
        available_seats = restaurant.seating_capacity - booked_members

        if members > available_seats:
            messages.error(request, f"Only {available_seats} seats are available.")
            return redirect('book_table', restaurant_id=restaurant.id)

    
        Booking_resto.objects.create(
            restaurant=restaurant,
            customer_name=customer_name,
            contact_number=contact_number,
            address="N/A",
            members=members,
            booking_time=booking_time
        )

        messages.success(request, f"🎉 Table booked successfully at {restaurant.name}!")
        return redirect('restaurant_list')

    return render(request, 'book_table.html', {
        'restaurant': restaurant,
        'available_seats': available_seats,
        'closing_time': closing_time,
    })
    
        
def restaurant_list(request):
    restaurants = AddResto.objects.all()

    # Use IST today's date (timezone-aware)
    today = timezone.localdate()

    for restaurant in restaurants:
        # Exclude Cancelled bookings so freed seats are reflected
        bookings_today = restaurant.bookings_resto.filter(
            booking_time__date=today
        ).exclude(status='Cancelled')

        booked_members = 0
        for b in bookings_today:
            try:
                booked_members += int(b.members)
            except (ValueError, TypeError):
                continue

        # Never go below 0
        restaurant.available_seats = max(restaurant.seating_capacity - booked_members, 0)

    return render(request, 'restaurant_view.html', {'restaurants': restaurants})



def owner_bookings(request):
    owner_id = request.session.get('admin_id')
    restaurant_name = request.session.get('restaurant_name')

    if not owner_id:
        messages.error(request, "Please log in first")
        return redirect('adminlogin') 

    try:
        admin_owner = AdminOwner.objects.get(id=owner_id)
    except AdminOwner.DoesNotExist:
        messages.error(request, "Invalid session. Please log in again.")
        return redirect('adminlogin')

    restaurants = AddResto.objects.filter(name__iexact=restaurant_name)
    owner_restaurant = restaurants.first()

    # Auto-mark past Pending bookings as Completed
    Booking_resto.objects.filter(
        restaurant__in=restaurants,
        status='Pending',
        booking_time__lt=timezone.now()
    ).update(status='Completed')

    bookings = Booking_resto.objects.filter(restaurant__in=restaurants).order_by('-booking_time')

    context = {
        'bookings': bookings,
        'admin_owner': admin_owner,
        'admin_user': admin_owner,
        'restaurants': restaurants,
        'owner_restaurant': owner_restaurant,
    }

    return render(request, 'admin_owner/owner_bookings.html', context)


def toggle_restaurant_accepting_orders(request):
    owner_id = request.session.get('admin_id')
    restaurant_name = request.session.get('restaurant_name')

    if not owner_id:
        messages.error(request, "Please log in first")
        return redirect('adminlogin')

    next_url = request.META.get('HTTP_REFERER')
    if not next_url:
        next_url = 'owner_bookings'

    try:
        admin_owner = AdminOwner.objects.get(id=owner_id)
        if admin_owner.is_blocked:
            AddResto.objects.filter(name__iexact=restaurant_name).update(is_accepting_orders=False)
            admin_owner.is_accepting_orders = False
            admin_owner.save()
            messages.error(request, "Your restaurant owner account is BLOCKED by the Super Admin. You cannot turn bookings/orders ON.")
            return redirect(next_url)
    except AdminOwner.DoesNotExist:
        pass

    if request.method != 'POST':
        return redirect(next_url)

    restaurants = AddResto.objects.filter(name__iexact=restaurant_name)
    if not restaurants.exists():
        messages.error(request, "Restaurant not found.")
        return redirect(next_url)

    is_accepting = request.POST.get('is_accepting_orders') == 'on'
    
    admin_owner.is_accepting_orders = is_accepting
    admin_owner.save()
    
    restaurants.update(is_accepting_orders=is_accepting)

    status = "Open" if is_accepting else "Closed"
    messages.success(request, f"Restaurant booking and ordering is now {status}.")
    return redirect(next_url)


# ----------------------------------------Main Admin----------------------------------




def super_register(request):
    if request.method == 'POST':
        form = SuperRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.save() 
            messages.success(request, 'Registration successful! Please login.')
            return redirect('super_login')
        else:
            messages.error(request, 'Please correct the errors below.')
            print(form.errors) 
    else:
        form = SuperRegisterForm()

    return render(request, 'super_admin/super_register.html', {'form': form})


def super_login(request):
    super_user = None
    if 'super_id' in request.session:
        try:
            super_user = SuperRegister.objects.get(id=request.session['super_id'])
        except SuperRegister.DoesNotExist:
            request.session.flush()

    if request.method == 'POST':
        form = SuperLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                user = SuperRegister.objects.get(email=email)
                if user.check_password(password):
                    request.session['super_id'] = user.id
                    request.session['super_name'] = user.full_name
                    messages.success(request, f'Welcome {user.full_name}!')
                    return redirect('super_dashboard')
                else:
                    messages.error(request, 'Invalid password.')
            except SuperRegister.DoesNotExist:
                messages.error(request, 'No account found with this email.')
    else:
        form = SuperLoginForm()

    return render(request, 'super_admin/super_login.html', {
        'form': form,
        'super_user': super_user
    })


def super_forgot_password(request):
    if 'super_otp_sent' not in request.session:
        request.session['super_otp_sent'] = False
        request.session['super_otp_verified'] = False

    form = None
    if request.method == 'POST':
        if not request.session['super_otp_sent']:
            form = ForgotPasswordForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                try:
                    user = SuperRegister.objects.get(email=email)
                    otp = randint(100000, 999999)
                    request.session['super_reset_email'] = email
                    request.session['super_otp_code'] = str(otp)
                    request.session['super_otp_sent'] = True
                    request.session['super_otp_verified'] = False               
                    
                    subject = 'Your OTP for Super Admin Password Reset'
                    message_text = f'Your OTP is: {otp}'
                    html_message = f"""
                    <div style="font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; border-radius: 24px; background: #ffffff; border: 1px solid #e2e8f0; color: #1e293b; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
                        <div style="text-align: center; margin-bottom: 25px;">
                            <span style="font-size: 28px; font-weight: 800; color: #ff6f00; letter-spacing: -1px;">Foodeat</span>
                            <span style="display: block; font-size: 10px; font-weight: 700; text-transform: uppercase; color: #94a3b8; letter-spacing: 2px; margin-top: 5px;">Super Admin Security Verification</span>
                        </div>
                        <div style="border-top: 3px solid #ff6f00; padding-top: 25px;">
                            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">Hello {user.full_name},</p>
                            <p style="font-size: 14px; line-height: 1.6; margin: 0 0 25px 0; color: #475569;">We received a request to reset your Super Admin account password. Use the following security verification code to proceed. This code is active for 10 minutes.</p>
                            
                            <div style="text-align: center; margin: 30px 0; background: #f8fafc; border-radius: 16px; padding: 25px; border: 1px dashed #cbd5e1;">
                                <span style="display: block; font-size: 10px; font-weight: 800; text-transform: uppercase; color: #64748b; letter-spacing: 1.5px; margin-bottom: 8px;">Your Verification Code</span>
                                <span style="font-family: monospace; font-size: 36px; font-weight: 900; color: #0f172a; letter-spacing: 6px; padding-left: 6px;">{otp}</span>
                            </div>
                            
                            <p style="font-size: 12px; line-height: 1.6; color: #64748b; margin: 25px 0 0 0;">If you did not request a password reset, please ignore this email or contact support immediately.</p>
                        </div>
                        <div style="border-top: 1px solid #e2e8f0; margin-top: 35px; padding-top: 20px; text-align: center; font-size: 11px; color: #94a3b8;">
                            &copy; 2026 Foodeat. All rights reserved.
                        </div>
                    </div>
                    """
                    
                    try:
                        send_mail(
                            subject,
                            message_text,
                            settings.EMAIL_HOST_USER,
                            [email],
                            fail_silently=False,
                            html_message=html_message
                        )
                        messages.success(request, f"OTP sent to {email}")
                    except Exception:
                        messages.warning(request, f"For local testing, your verification OTP code is: {otp}")
                    
                    return redirect('super_forgot_password')
                except SuperRegister.DoesNotExist:
                    messages.error(request, "Email not registered as Super Admin")
        
        elif request.session.get('super_otp_sent') and not request.session.get('super_otp_verified'):
            form = OTPForm(request.POST)
            if form.is_valid():
                otp_input = form.cleaned_data['otp']
                if otp_input == request.session.get('super_otp_code'):
                    request.session['super_otp_verified'] = True
                    messages.success(request, "OTP verified. Please set your new password.")
                    return redirect('super_forgot_password')
                else:
                    messages.error(request, "Invalid OTP. Try again.")    
        
        elif request.session.get('super_otp_verified'):
            form = ResetPasswordForm(request.POST)
            if form.is_valid():
                password = form.cleaned_data['password']
                email = request.session.get('super_reset_email')
                try:
                    user = SuperRegister.objects.get(email=email)
                    user.password = make_password(password)
                    user.save()
                    messages.success(request, "Password reset successful!")               
                    
                    request.session.pop('super_otp_sent', None)
                    request.session.pop('super_otp_verified', None)
                    request.session.pop('super_otp_code', None)
                    request.session.pop('super_reset_email', None)
                    return redirect('super_login')
                except SuperRegister.DoesNotExist:
                    messages.error(request, "Something went wrong. Try again.")   
    else:
        if not request.session.get('super_otp_sent'):
            form = ForgotPasswordForm()
        elif request.session.get('super_otp_sent') and not request.session.get('super_otp_verified'):
            form = OTPForm()
        else:
            form = ResetPasswordForm()

    return render(request, 'super_admin/super_forgot_password.html', {'form': form})


def super_profile(request):
    if 'super_id' not in request.session:
        return redirect('/super_login/')

    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('/super_login/')

    context = {
        'super_user': super_user,
        'page_title': 'My Profile'
    }
    return render(request, 'super_admin/super_profile.html', context)


def super_profile_edit(request):
    if 'super_id' not in request.session:
        return redirect('/super_login/')

    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('/super_login/')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        profile_img = request.FILES.get('profile_img')

        # Server-side validation: phone must be exactly 10 digits
        clean_phone = ''.join(filter(str.isdigit, phone)) if phone else ''
        if not clean_phone or len(clean_phone) != 10:
            context = {
                'super_user': super_user,
                'page_title': 'Edit Profile',
                'error': 'Phone number must contain exactly 10 digits.'
            }
            return render(request, 'super_admin/super_profile_edit.html', context)

        if full_name:
            super_user.full_name = full_name
        if email:
            super_user.email = email
        if phone is not None:
            super_user.phone = clean_phone
        if profile_img:
            super_user.profile_img = profile_img  
        super_user.save()
        return redirect('/super_profile/')

    context = {
        'super_user': super_user,
        'page_title': 'Edit Profile'
    }
    return render(request, 'super_admin/super_profile_edit.html', context)

def super_dashboard(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    from django.db.models import Sum, F, Count
    super_user = SuperRegister.objects.get(id=request.session['super_id'])

    orders_by_day = (
        Order.objects.exclude(status='Cancelled').annotate(day=TruncDate('order_date'))
        .values('day')
        .annotate(
            total_profit=Sum('final_amount'),
            total_products=Sum(F('orderitem__quantity')),
            total_orders=Sum(1)
        )
        .order_by('day')
    )

    chart_labels = [o['day'].strftime("%d %b") for o in orders_by_day]
    chart_profit = [o['total_profit'] or 0 for o in orders_by_day]
    chart_products = [o['total_products'] or 0 for o in orders_by_day]
    chart_orders = [o['total_orders'] or 0 for o in orders_by_day]

    chart_restaurant_labels, chart_restaurant_orders, chart_restaurant_profit = [], [], []
    resto_items_grouped = (
        OrderItem.objects.exclude(order__status='Cancelled')
        .values('food__restaurant_name')
        .annotate(
            orders_count=Count('order', distinct=True),
            total_sales=Sum(F('price') * F('quantity'))
        )
    )
    for r in resto_items_grouped:
        name = r['food__restaurant_name']
        if not name:
            continue
        chart_restaurant_labels.append(name)
        chart_restaurant_orders.append(r['orders_count'])
        chart_restaurant_profit.append(float(r['total_sales'] or 0.0))

    foods = FoodItem.objects.all()
    chart_food_labels = [f.food_name for f in foods]
    chart_food_prices = [float(f.price) for f in foods]
    chart_food_is_spicy = [1 if f.is_spicy else 0 for f in foods]
    chart_food_is_veg = [1 if f.is_veg else 0 for f in foods]
    chart_food_is_available = [1 if f.is_available else 0 for f in foods]

    # Platform metrics & Settlements calculations
    from .models import PlatformSettings
    from datetime import datetime
    
    platform_settings, created = PlatformSettings.objects.get_or_create(id=1)
    commission_rate = float(platform_settings.restaurant_commission_percentage)

    # Calculate restaurant profits (Commissions)
    resto_names_from_resto = AddResto.objects.values_list('name', flat=True).distinct()
    resto_names_from_food = FoodItem.objects.values_list('restaurant_name', flat=True).distinct()
    resto_names = list(set(filter(None, list(resto_names_from_resto) + list(resto_names_from_food))))
    
    # Get mapping of restaurant name to owner name (AdminOwner)
    owners = AdminOwner.objects.all()
    resto_owner_map = {}
    for o in owners:
        resto_owner_map[o.restaurant_name.strip().lower()] = o.full_name.strip()
        
    all_resto_names = []
    for name in sorted(resto_names):
        owner_name = resto_owner_map.get(name.strip().lower())
        all_resto_names.append({
            'name': name,
            'owner_name': owner_name if owner_name else "Unknown Owner"
        })
    
    profit_restaurant = request.GET.get('profit_restaurant', '').strip()
    profit_date_str = request.GET.get('profit_date')
    
    profit_date = None
    if profit_date_str:
        try:
            profit_date = datetime.strptime(profit_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    today = timezone.localdate()
    restaurant_profits_list = []
    
    for name in resto_names:
        if not name:
            continue
        if profit_restaurant and name.lower() != profit_restaurant.lower():
            continue
            
        resto_items = OrderItem.objects.exclude(order__status='Cancelled').filter(food__restaurant_name__iexact=name)
        
        today_val = resto_items.filter(order__order_date__date=today).aggregate(total=Sum('restaurant_commission'))['total'] or 0.0
        
        all_time_val = resto_items.aggregate(total=Sum('restaurant_commission'))['total'] or 0.0
        
        filtered_val = None
        if profit_date:
            filtered_val = resto_items.filter(order__order_date__date=profit_date).aggregate(total=Sum('restaurant_commission'))['total'] or 0.0
            
        restaurant_profits_list.append({
            'name': name,
            'today_profit': float(today_val),
            'all_time_profit': float(all_time_val),
            'filtered_profit': float(filtered_val) if filtered_val is not None else None,
        })

    total_filtered_commission = 0.0
    if profit_date or profit_restaurant:
        if profit_date:
            total_filtered_commission = sum(float(r['filtered_profit'] or 0.0) for r in restaurant_profits_list)
        else:
            total_filtered_commission = sum(float(r['all_time_profit'] or 0.0) for r in restaurant_profits_list)

    modal_today_profit = sum(float(r['today_profit'] or 0.0) for r in restaurant_profits_list)
    modal_cumulative_profit = sum(float(r['all_time_profit'] or 0.0) for r in restaurant_profits_list)

    # Today's daily metrics (using timezone localdate)
    today_orders = Order.objects.filter(order_date__date=today).exclude(status='Cancelled')
    
    today_metrics = today_orders.aggregate(
        today_commission=Sum('restaurant_commission'),
        today_delivery=Sum('delivery_charge'),
        today_rider=Sum('rider_earning')
    )
    
    today_commission = float(today_metrics['today_commission']) if today_metrics['today_commission'] is not None else 0.0
    today_delivery = float(today_metrics['today_delivery']) if today_metrics['today_delivery'] is not None else 0.0
    today_rider = float(today_metrics['today_rider']) if today_metrics['today_rider'] is not None else 0.0
    
    today_net_profit = today_commission + (today_delivery - today_rider)
    today_delivery_profit = today_delivery - today_rider

    metrics_query = Order.objects.exclude(status='Cancelled').aggregate(
        total_commission=Sum('restaurant_commission'),
        total_delivery=Sum('delivery_charge'),
        total_rider=Sum('rider_earning')
    )
    
    total_commission = float(metrics_query['total_commission']) if metrics_query['total_commission'] is not None else 0.0
    total_delivery = float(metrics_query['total_delivery']) if metrics_query['total_delivery'] is not None else 0.0
    total_rider = float(metrics_query['total_rider']) if metrics_query['total_rider'] is not None else 0.0
    
    from .models import WalletTransaction
    total_admin_wallet_adds = float(WalletTransaction.objects.filter(transaction_type='Admin Add').aggregate(total=Sum('amount'))['total'] or 0.00)
    platform_net_profit = total_commission + (total_delivery - total_rider) - total_admin_wallet_adds
    total_delivery_profit = total_delivery - total_rider

    # Restaurant Settlements
    restaurant_settlements = list(
        OrderItem.objects.exclude(order__status='Cancelled')
        .values('food__restaurant_name')
        .annotate(
            total_sales=Sum(F('price') * F('quantity') - F('discount') * F('quantity')),
            order_count=Count('order', distinct=True)
        )
    )
    for r in restaurant_settlements:
        sales = float(r['total_sales']) if r['total_sales'] is not None else 0.0
        r['total_sales'] = sales
        r['commission'] = sales * (commission_rate / 100.0)
        r['net_resto_payout'] = sales - r['commission']

    # Rider Settlements
    rider_settlements = list(
        Order.objects.filter(delivery_boy__isnull=False, status='Delivered')
        .values('delivery_boy__name', 'delivery_boy__phone_number')
        .annotate(
            total_deliveries=Count('id'),
            total_charges=Sum('delivery_charge'),
            total_payout=Sum('rider_earning')
        )
    )

    # Wallet & Rider Milestone Calculations
    from .models import DeliveryBoyTaskProgress
    total_rider_bonuses = float(DeliveryBoyTaskProgress.objects.filter(is_completed=True).aggregate(total=Sum('task__bonus_amount'))['total'] or 0.00)

    context = {
        'super_user': super_user,
        'page_title': 'Dashboard',
        'chart_labels': json.dumps(chart_labels),
        'chart_profit': json.dumps(chart_profit),
        'chart_products': json.dumps(chart_products),
        'chart_orders': json.dumps(chart_orders),
        'chart_restaurant_labels': json.dumps(chart_restaurant_labels),
        'chart_restaurant_orders': json.dumps(chart_restaurant_orders),
        'chart_restaurant_profit': json.dumps(chart_restaurant_profit),
        'chart_food_labels': json.dumps(chart_food_labels),
        'chart_food_prices': json.dumps(chart_food_prices),
        'chart_food_is_spicy': json.dumps(chart_food_is_spicy),
        'chart_food_is_veg': json.dumps(chart_food_is_veg),
        'chart_food_is_available': json.dumps(chart_food_is_available),
        'total_commission': total_commission,
        'total_delivery': total_delivery,
        'total_rider': total_rider,
        'platform_net_profit': platform_net_profit,
        'today_commission': today_commission,
        'today_net_profit': today_net_profit,
        'today_delivery_profit': today_delivery_profit,
        'total_delivery_profit': total_delivery_profit,
        'restaurant_settlements': restaurant_settlements,
        'rider_settlements': rider_settlements,
        'commission_rate': commission_rate,
        'restaurant_profits_list': restaurant_profits_list,
        'profit_date_str': profit_date_str,
        'total_filtered_commission': total_filtered_commission,
        'all_resto_names': all_resto_names,
        'profit_restaurant': profit_restaurant,
        'modal_today_profit': modal_today_profit,
        'modal_cumulative_profit': modal_cumulative_profit,
        'total_rider_bonuses': total_rider_bonuses,
        'total_admin_wallet_adds': total_admin_wallet_adds,
    }

    return render(request, 'super_admin/super_dashboard.html', context)


def super_logout(request):
    if 'super_id' in request.session:
        del request.session['super_id']
    if 'super_name' in request.session:
        del request.session['super_name']

    messages.success(request, "Super Admin has been logged out successfully.")
    return redirect('super_login')


def contactus(request):
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save() 
            from django.contrib import messages
            messages.success(request, "Your message has been sent successfully! We will get back to you soon.")
            return redirect('contactus')  
    else:
        initial_data = {}
        if 'user_id' in request.session:
            try:
                from .models import Registration
                user = Registration.objects.get(id=request.session['user_id'])
                initial_data['full_name'] = f"{user.first_name} {user.last_name}"
                initial_data['email'] = user.email
            except Registration.DoesNotExist:
                pass
        form = ContactMessageForm(initial=initial_data)
    return render(request, 'contactus.html', {'form': form})



def admin_contact_list(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    super_user = None
    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('super_login')

    messages_list = ContactMessage.objects.all().order_by('-created_at')
    
    return render(request, 'super_admin/admin_contact_list.html', {
        'messages_list': messages_list,
        'super_user': super_user,   
        'page_title': 'Contact Messages', 
    })


def admin_contact_delete(request, message_id):
    try:
        msg = ContactMessage.objects.get(id=message_id)
        msg.delete()
        messages.success(request, "Message deleted successfully!")
    except ContactMessage.DoesNotExist:
        messages.error(request, "Message not found!")
    
    return redirect('admin_contact_list')


def admin_contact_reply(request, message_id):
    if 'super_id' not in request.session:
        return redirect('super_login')

    super_user = get_object_or_404(SuperRegister, id=request.session['super_id'])
    msg = get_object_or_404(ContactMessage, id=message_id)
    if request.method == 'POST':
        reply_text = request.POST.get('reply_text')
        
        # Send reply email to user using EmailMessage to support proper reply_to and super admin's identity
        from django.core.mail import EmailMessage
        from django.conf import settings
        
        subject = f"Reply to your Foodeat inquiry: {msg.subject}"
        body = f"Hello {msg.full_name},\n\nThank you for reaching out to Foodeat.\n\nRegarding your message:\n\"{msg.message}\"\n\nHere is our response:\n{reply_text}\n\nBest regards,\n{super_user.full_name}\nFoodeat Support Team"
        
        email_sent = False
        # Format sender address using authenticated host user so Gmail SMTP doesn't block the dispatch
        sender_address = f"{super_user.full_name} <{settings.EMAIL_HOST_USER}>"
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=sender_address,
            to=[msg.email],
            reply_to=[super_user.email]
        )
        
        try:
            email.send(fail_silently=False)
            email_sent = True
        except Exception as e:
            print("Failed to send email:", e)
            email_sent = False
        
        # Save the reply to the DB
        db_saved = False
        try:
            msg.reply_message = reply_text
            msg.save()
            db_saved = True
        except Exception as db_err:
            print("Failed to save reply to DB:", db_err)
            
        if db_saved:
            if email_sent:
                messages.success(request, f"Reply successfully sent directly to {msg.email}!")
            else:
                messages.success(request, f"Reply saved successfully! (Note: Email delivery failed, but response is recorded)")
        else:
            messages.error(request, "Failed to save reply in the database.")

    return redirect('admin_contact_list')


def show_owners(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    super_user = None
    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('super_login')

    owners = AdminOwner.objects.all().order_by('-id')
    restaurant_status = {
        restaurant.name.lower(): restaurant.is_accepting_orders
        for restaurant in AddResto.objects.all()
    }

    for owner in owners:
        owner.restaurant_is_online = restaurant_status.get(owner.restaurant_name.lower())

    return render(request, 'super_admin/show_owners.html', {
        'owners': owners,
        'super_user': super_user,
        'page_title': 'Restaurants', 
    })


def show_orders(request):
    if 'super_id' not in request.session:
        return redirect('/super_login/')  

    super_user = None
    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('/super_login/')

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        boy_id = request.POST.get('delivery_boy_id')
        if order_id and boy_id:
            order = get_object_or_404(Order, id=order_id)
            boy = get_object_or_404(DeliveryBoy, id=boy_id)
            order.delivery_boy = boy
            order.save()
            
            # Update delivery boy's status to Delivering
            if boy.status == 'Available':
                boy.status = 'Delivering'
                boy.save()
                
            from django.contrib import messages
            messages.success(request, f"Order #{order.id} has been manually assigned to {boy.name}.")
            return redirect('show_orders')

    orders = Order.objects.all().order_by('-id')  
    delivery_boys = DeliveryBoy.objects.filter(is_verified=True, is_blocked=False).exclude(status='Off-duty')

    context = {
        'super_user': super_user,
        'orders': orders,
        'delivery_boys': delivery_boys,
        'page_title': 'Orders Log',
    }
    return render(request, 'super_admin/show_orders.html', context)


def showsuper_users(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    super_user = None
    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('super_login')

    users = Registration.objects.all()

    return render(request, 'super_admin/show_users.html', {
        'owners': users,             
        'super_user': super_user,    
        'page_title': 'Users Directory',      
    })


def super_manage_user_wallet(request, user_id):
    if 'super_id' not in request.session:
        return redirect('super_login')

    from decimal import Decimal
    user = get_object_or_404(Registration, id=user_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        amount = request.POST.get('amount')
        try:
            val = float(amount)
            from .models import WalletTransaction
            if action == 'add':
                user.wallet_balance += Decimal(str(val))
                WalletTransaction.objects.create(
                    user=user,
                    amount=Decimal(str(val)),
                    transaction_type='Admin Add'
                )
                messages.success(request, f"Successfully added ₹{val:.2f} to {user.first_name}'s wallet!")
            elif action == 'subtract':
                user.wallet_balance = max(Decimal('0.00'), user.wallet_balance - Decimal(str(val)))
                WalletTransaction.objects.create(
                    user=user,
                    amount=Decimal(str(val)),
                    transaction_type='Admin Deduct'
                )
                messages.success(request, f"Successfully deducted ₹{val:.2f} from {user.first_name}'s wallet!")
            elif action == 'set':
                user.wallet_balance = Decimal(str(val))
                WalletTransaction.objects.create(
                    user=user,
                    amount=Decimal(str(val)),
                    transaction_type='Admin Set'
                )
                messages.success(request, f"Successfully set {user.first_name}'s wallet balance to ₹{val:.2f}!")
            user.save()
        except ValueError:
            messages.error(request, "Invalid amount value.")
            
    return redirect('showsuper_users')


def show_food(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    super_user = None
    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('super_login')

    food_items = FoodItem.objects.all().order_by('-id')

    return render(request, 'super_admin/show_food.html', {
        'owners': food_items,         
        'super_user': super_user,    
        'page_title': 'Food Catalog',  
    })


def show_booking(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    super_user = None
    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('super_login')

    restos = AddResto.objects.prefetch_related('bookings_resto').all()

    return render(request, 'super_admin/show_booking.html', {
        'restos': restos,
        'super_user': super_user,   
        'page_title': 'Table Bookings', 
    })


def get_admin_html_email(recipient_name, subject, message_body):
    import html
    safe_message = html.escape(message_body).replace('\n', '<br>')
    safe_name = html.escape(recipient_name)
    safe_subject = html.escape(subject)
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; padding: 40px 0;">
        <tr>
            <td align="center">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); border: 1px solid #e2e8f0;">
                    <!-- Branded Header -->
                    <tr>
                        <td align="center" style="background: linear-gradient(135deg, #ff6f00 0%, #ea580c 100%); padding: 32px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 800; letter-spacing: -0.5px; font-family: sans-serif;">Foodeat</h1>
                            <p style="margin: 4px 0 0 0; color: #ffedd5; font-size: 13px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;">Official Administration Message</p>
                        </td>
                    </tr>
                    <!-- Main Body Content -->
                    <tr>
                        <td style="padding: 40px 40px 30px 40px;">
                            <h2 style="margin: 0 0 20px 0; color: #0f172a; font-size: 18px; font-weight: 700;">Hello {safe_name},</h2>
                            <div style="color: #334155; font-size: 15px; line-height: 1.6; font-weight: 500;">
                                {safe_message}
                            </div>
                        </td>
                    </tr>
                    <!-- Separator -->
                    <tr>
                        <td style="padding: 0 40px;">
                            <div style="border-top: 1px dashed #e2e8f0;"></div>
                        </td>
                    </tr>
                    <!-- Support Info -->
                    <tr>
                        <td style="padding: 30px 40px 40px 40px;">
                            <p style="margin: 0 0 4px 0; color: #64748b; font-size: 13px; font-weight: 500;">If you have any questions or concerns regarding this message, please contact us directly by replying to this email.</p>
                            <p style="margin: 0; color: #ff6f00; font-size: 13px; font-weight: 700;">Foodeat Administrator Team</p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td align="center" style="background-color: #f1f5f9; padding: 24px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="margin: 0; color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">© 2026 Foodeat. All rights reserved.</p>
                            <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 11px; font-weight: 500;">Zamato Zomato_aryan Application Workspace</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def send_email_to_user(request, pk):
    user_to_email = get_object_or_404(Registration, pk=pk)

    if request.method == 'POST':
        form = EmailForm(request.POST, request.FILES)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message_body = form.cleaned_data['message']
            attachment = request.FILES.get('attachment')

            recipient_email = user_to_email.email
            sender_email = settings.EMAIL_HOST_USER

            recipient_name = f"{user_to_email.first_name} {user_to_email.last_name}"
            html_content = get_admin_html_email(recipient_name, subject, message_body)

            from django.core.mail import EmailMultiAlternatives
            email = EmailMultiAlternatives(
                subject,
                message_body,  # Plain text fallback
                sender_email,
                [recipient_email],
                reply_to=[sender_email]
            )
            email.attach_alternative(html_content, "text/html")

            if attachment:
                email.attach(attachment.name, attachment.read(), attachment.content_type)

            try:
                email.send()
                messages.success(request, f"✅ Email sent successfully to {user_to_email.email}!")
            except Exception as e:
                messages.error(request, f"❌ Failed to send email. Error: {e}")
        else:
            messages.error(request, "⚠️ Please correct the errors in the email form.")
    else:
        messages.warning(request, "Invalid access. Please use the 'Send Email' button.")
    return redirect('showsuper_users')


def toggle_user_block(request, pk):
    if 'super_id' not in request.session:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
            return JsonResponse({'status': 'error', 'message': 'Session expired'}, status=403)
        return redirect('super_login')

    user = get_object_or_404(Registration, pk=pk)
    user.is_blocked = not user.is_blocked
    user.save()
    
    status = "blocked" if user.is_blocked else "unblocked"
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true' or request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'is_blocked': user.is_blocked,
            'message': f"User {user.first_name} {user.last_name} has been {status} successfully."
        })

    messages.success(request, f"User {user.first_name} {user.last_name} has been {status} successfully.")
    return redirect('showsuper_users')


def toggle_owner_block(request, pk):
    if 'super_id' not in request.session:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
            return JsonResponse({'status': 'error', 'message': 'Session expired'}, status=403)
        return redirect('super_login')

    owner = get_object_or_404(AdminOwner, pk=pk)
    owner.is_blocked = not owner.is_blocked
    owner.save()
    
    if owner.is_blocked:
        # Automatically close their restaurant(s) if blocked
        AddResto.objects.filter(name__iexact=owner.restaurant_name).update(is_accepting_orders=False)
        owner.is_accepting_orders = False
        owner.save()
    
    status = "blocked" if owner.is_blocked else "unblocked"
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true' or request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'is_blocked': owner.is_blocked,
            'message': f"Restaurant Owner {owner.full_name} has been {status} successfully."
        })

    messages.success(request, f"Restaurant Owner {owner.full_name} has been {status} successfully.")
    return redirect('show_owners')


def toggle_owner_approval(request, pk):
    if 'super_id' not in request.session:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
            return JsonResponse({'status': 'error', 'message': 'Session expired'}, status=403)
        return redirect('super_login')

    owner = get_object_or_404(AdminOwner, pk=pk)
    
    if owner.is_approved:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
            return JsonResponse({'status': 'error', 'message': 'This owner is already approved.'}, status=400)
        messages.warning(request, "This owner is already approved.")
        return redirect('show_owners')

    owner.is_approved = True
    owner.save()

    # Send approval notification email
    login_url = request.build_absolute_uri('/adminlogin/')
    subject = 'Your Restaurant Owner Account is Approved!'
    message = f"Hello {owner.full_name},\n\nYour restaurant owner account for \"{owner.restaurant_name}\" has been approved by the Super Admin.\n\nYou can now log in to the Restaurant Owner console to manage your restaurant at:\n{login_url}\n\nBest regards,\nFoodeat Team"
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER, [owner.email], fail_silently=False)
    except Exception:
        pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true' or request.method == 'POST':
        return JsonResponse({
            'status': 'success',
            'is_approved': owner.is_approved,
            'message': f"Restaurant Owner {owner.full_name} has been approved successfully."
        })

    messages.success(request, f"Restaurant Owner {owner.full_name} has been approved successfully.")
    return redirect('show_owners')


def send_email_to_owner(request, pk):
    if 'super_id' not in request.session:
        return redirect('super_login')

    owner_to_email = get_object_or_404(AdminOwner, pk=pk)

    if request.method == 'POST':
        form = EmailForm(request.POST, request.FILES)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            message_body = form.cleaned_data['message']
            attachment = request.FILES.get('attachment')

            recipient_email = owner_to_email.email
            sender_email = settings.EMAIL_HOST_USER

            recipient_name = owner_to_email.full_name
            html_content = get_admin_html_email(recipient_name, subject, message_body)

            from django.core.mail import EmailMultiAlternatives
            email = EmailMultiAlternatives(
                subject,
                message_body,  # Plain text fallback
                sender_email,
                [recipient_email],
                reply_to=[sender_email]
            )
            email.attach_alternative(html_content, "text/html")

            if attachment:
                email.attach(attachment.name, attachment.read(), attachment.content_type)

            try:
                email.send()
                messages.success(request, f"✅ Email sent successfully to {owner_to_email.email}!")
            except Exception as e:
                messages.error(request, f"❌ Failed to send email. Error: {e}")
        else:
            messages.error(request, "⚠️ Please correct the errors in the email form.")
    else:
        messages.warning(request, "Invalid access. Please use the 'Send Email' button.")
    return redirect('show_owners')


def super_notifications(request):
    if 'super_id' not in request.session:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)

    from .models import AdminOwner, ContactMessage, SuperAdminNotification

    notifications = []

    from django.utils import timezone

    # 1. Pending Owner Registrations
    pending_owners = AdminOwner.objects.filter(is_approved=False).order_by('-id')
    for owner in pending_owners:
        notifications.append({
            'id': f"owner_{owner.id}",
            'timestamp': int(timezone.localtime(owner.created_at).timestamp()) if owner.created_at else 0,
            'type': 'owner',
            'title': 'New Restaurant Owner Registration',
            'message': f"{owner.full_name} registered '{owner.restaurant_name}'",
            'link': '/show_owners/',
            'created_at': timezone.localtime(owner.created_at).strftime('%I:%M %p') if owner.created_at else 'Just now'
        })

    # 2. Custom Alerts (like missing delivery boys)
    alerts = SuperAdminNotification.objects.filter(is_read=False).order_by('-id')
    for alert in alerts:
        notifications.append({
            'id': f"alert_{alert.id}",
            'timestamp': int(timezone.localtime(alert.created_at).timestamp()) if alert.created_at else 0,
            'type': 'alert',
            'title': alert.title,
            'message': alert.message,
            'link': alert.link,
            'created_at': timezone.localtime(alert.created_at).strftime('%I:%M %p') if alert.created_at else 'Just now'
        })

    # 3. Contact Messages
    messages = ContactMessage.objects.all().order_by('-id')
    for msg in messages:
        notifications.append({
            'id': f"msg_{msg.id}",
            'timestamp': int(timezone.localtime(msg.created_at).timestamp()) if msg.created_at else 0,
            'type': 'contact',
            'title': 'New Contact Message',
            'message': f"From {msg.full_name}: {msg.subject}",
            'link': '/admin_contact_list/',
            'created_at': timezone.localtime(msg.created_at).strftime('%I:%M %p') if msg.created_at else 'Recently'
        })

    # Sort notifications by timestamp descending so the newest are on top
    notifications.sort(key=lambda x: x['timestamp'], reverse=True)

    return JsonResponse({
        'status': 'success',
        'count': len(notifications),
        'notifications': notifications[:10]  # top 10 notifications
    })


def delivery_register(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        image = request.FILES.get('image')
        license_number = request.POST.get('license_number', '').strip()
        type_of_bike = request.POST.get('type_of_bike', '').strip()
        bike_number = request.POST.get('bike_number', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        aadhar_card_image = request.FILES.get('aadhar_card_image')
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not (name and image and license_number and type_of_bike and bike_number and email and phone_number and aadhar_card_image and password and confirm_password):
            messages.error(request, "All fields (including profile picture, driving license, vehicle plate, and Aadhaar card photo) are required.")
            return render(request, 'delivery/register.html')

        import re

        # 1. Password validation
        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, 'delivery/register.html')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'delivery/register.html')

        # 2. Email format validation
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            messages.error(request, "Please enter a valid email address.")
            return render(request, 'delivery/register.html')

        # 3. Mobile validation (exactly 10 digits)
        if not re.match(r'^\d{10}$', phone_number):
            messages.error(request, "Mobile number must be a valid 10-digit number.")
            return render(request, 'delivery/register.html')

        # 4. Vehicle/Bike Number validation (Standard RTO format)
        clean_bike_num = bike_number.replace(" ", "").replace("-", "").upper()
        if not re.match(r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$', clean_bike_num):
            messages.error(request, "Invalid Vehicle Number. It should match RTO format (e.g. GJ05AB1234 or GJ-05-AB-1234).")
            return render(request, 'delivery/register.html')

        # 5. Driving License Number validation (Standard DL format)
        clean_license = license_number.replace(" ", "").replace("-", "").upper()
        if not re.match(r'^[A-Z]{2}\d{2}\d{4}\d{7}$', clean_license):
            messages.error(request, "Invalid Driving License. It should match RTO format (e.g. GJ0520120123456 or GJ-05-2012-0123456).")
            return render(request, 'delivery/register.html')

        if DeliveryBoy.objects.filter(email=email).exists():
            messages.error(request, "A delivery boy with this email already exists.")
            return render(request, 'delivery/register.html')

        if DeliveryBoy.objects.filter(phone_number=phone_number).exists():
            messages.error(request, "A delivery boy with this phone number already exists.")
            return render(request, 'delivery/register.html')

        import random
        from django.contrib.auth.hashers import make_password
        otp = str(random.randint(100000, 999999))

        boy = DeliveryBoy.objects.create(
            name=name,
            image=image,
            license_number=license_number,
            type_of_bike=type_of_bike,
            bike_number=bike_number,
            email=email,
            phone_number=phone_number,
            aadhar_card_image=aadhar_card_image,
            password=make_password(password),
            otp=otp,
            is_verified=False
        )

        request.session['delivery_verify_email'] = email
        
        # Send actual verification email
        try:
            subject = 'Foodeat - Delivery Partner Verification Code'
            message = f'Hello {name},\n\nThank you for registering as a Delivery Partner with Foodeat.\n\nYour 6-digit OTP code is: {otp}\n\nPlease enter this code to verify your profile and open your dashboard.\n\nRegards,\nFoodeat Logistics Team'
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
            messages.success(request, "Registration details submitted! Verification OTP has been sent to your email address.")
        except Exception:
            messages.warning(request, f"Registration details submitted! For local testing, your verification OTP code is: {otp}")
            
        return redirect('delivery_verify_otp')

    return render(request, 'delivery/register.html')


def delivery_verify_otp(request):
    email = request.session.get('delivery_verify_email')
    if not email:
        boy_id = request.session.get('delivery_boy_id')
        if boy_id:
            boy = DeliveryBoy.objects.filter(id=boy_id).first()
            if boy:
                email = boy.email

    if not email:
        messages.error(request, "Session expired. Please register or login again.")
        return redirect('delivery_register')

    boy = get_object_or_404(DeliveryBoy, email=email)

    if request.method == 'POST':
        otp_input = request.POST.get('otp', '').strip()
        if otp_input == boy.otp:
            boy.is_email_verified = True
            boy.otp = None
            boy.save()
            request.session['delivery_boy_id'] = boy.id
            messages.success(request, f"Welcome, {boy.name}! Your email has been verified.")
            return redirect('delivery_dashboard')
        else:
            messages.error(request, "Invalid OTP code. Please check and try again.")

    return render(request, 'delivery/verify_otp.html', {'boy': boy})


def delivery_login(request):
    if request.method == 'POST':
        login_id = request.POST.get('login_id', '').strip()
        password = request.POST.get('password', '').strip()
        
        boy = DeliveryBoy.objects.filter(email=login_id).first() or DeliveryBoy.objects.filter(phone_number=login_id).first()
        
        if boy:
            from django.contrib.auth.hashers import check_password
            if check_password(password, boy.password):
                # Log in directly using credentials
                request.session['delivery_boy_id'] = boy.id
                messages.success(request, f"Welcome back, {boy.name}!")
                return redirect('delivery_dashboard')
            else:
                messages.error(request, "Incorrect password. Please try again.")
        else:
            messages.error(request, "No registered delivery partner found with these credentials.")

    return render(request, 'delivery/login.html')


def delivery_dashboard(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    if boy.is_blocked:
        if boy.status != 'Off-duty':
            boy.status = 'Off-duty'
            boy.save()

    if not boy.is_email_verified:
        return redirect('delivery_verify_otp')

    if not boy.is_verified:
        if boy.status != 'Off-duty':
            boy.status = 'Off-duty'
            boy.save()

    active_order = Order.objects.filter(delivery_boy=boy, status__in=['paid', 'Packed', 'Shipped']).first()
    active_order_items = []
    if active_order:
        active_order_items = OrderItem.objects.filter(order=active_order).select_related('food')

    available_orders = []
    if not active_order and boy.status != 'Off-duty':
        available_orders = Order.objects.filter(delivery_boy__isnull=True, status='Packed').order_by('-order_date')

    completed_deliveries = Order.objects.filter(delivery_boy=boy, status='Delivered').order_by('-order_date')
    from django.db.models import Sum
    from django.utils import timezone
    today = timezone.now().date()

    total_earnings_query = completed_deliveries.aggregate(total=Sum('rider_earning'))
    total_earnings = float(total_earnings_query['total']) if total_earnings_query['total'] is not None else 0.0

    today_completed = completed_deliveries.filter(order_date__date=today)
    today_earnings_query = today_completed.aggregate(total=Sum('rider_earning'))
    today_earnings = float(today_earnings_query['total']) if today_earnings_query['total'] is not None else 0.0

    today_completed_count = today_completed.count()

    from django.db.models import Avg
    ratings_query = Order.objects.filter(delivery_boy=boy, delivery_rating__isnull=False, delivery_rating__gt=0).aggregate(avg_rating=Avg('delivery_rating'))
    avg_rating = round(ratings_query['avg_rating'], 1) if ratings_query['avg_rating'] is not None else None

    performance_status = "New Partner"
    if avg_rating is not None:
        if avg_rating >= 4.5:
            performance_status = "Excellent Rider"
        elif avg_rating >= 3.5:
            performance_status = "Good Rider"
        else:
            performance_status = "Standard Rider"

    # Calculate custom active milestone task progresses
    from .models import DeliveryTask, DeliveryBoyTaskProgress
    active_tasks = DeliveryTask.objects.filter(is_active=True, end_date__gte=today)
    
    for task in active_tasks:
        progress, created_progress = DeliveryBoyTaskProgress.objects.get_or_create(
            delivery_boy=boy,
            task=task
        )
        if not progress.is_completed:
            completed_count = completed_deliveries.filter(
                order_date__gte=task.created_at,
                order_date__date__lte=task.end_date
            ).count()
            progress.orders_completed = completed_count
            if completed_count >= task.required_orders:
                progress.is_completed = True
                progress.completed_at = timezone.now()
            progress.save()

    completed_tasks_payout = DeliveryBoyTaskProgress.objects.filter(
        delivery_boy=boy, is_completed=True
    ).aggregate(total=Sum('task__bonus_amount'))['total'] or 0.00
    
    total_earnings += float(completed_tasks_payout)
    
    rider_tasks = DeliveryBoyTaskProgress.objects.filter(
        delivery_boy=boy,
        task__is_active=True
    ).select_related('task').order_by('-task__end_date')

    context = {
        'boy': boy,
        'active_order': active_order,
        'active_order_items': active_order_items,
        'available_orders': available_orders,
        'completed_deliveries': completed_deliveries,
        'total_earnings': total_earnings,
        'today_earnings': today_earnings,
        'today_completed_count': today_completed_count,
        'avg_rating': avg_rating,
        'performance_status': performance_status,
        'rider_tasks': rider_tasks,
    }
    return render(request, 'delivery/dashboard.html', context)


def delivery_check_orders(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    
    from .models import Order
    # Check if there is an active order assigned to this delivery boy
    active_order = Order.objects.filter(delivery_boy_id=boy_id, status__in=['paid', 'Packed', 'Shipped']).first()
    
    active_id = active_order.id if active_order else 0
    return JsonResponse({'status': 'success', 'active_order_id': active_id})


def delivery_accept_order(request, order_id):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    order = get_object_or_404(Order, id=order_id)

    if boy.status == 'Off-duty':
        messages.error(request, "You are currently Offline. Please go Online first to accept orders.")
        return redirect('delivery_dashboard')

    has_active = Order.objects.filter(delivery_boy=boy, status__in=['Shipped', 'Packed']).exists()
    if has_active:
        messages.error(request, "You already have an active delivery task.")
        return redirect('delivery_dashboard')

    if order.delivery_boy:
        messages.error(request, "This order has already been accepted by another driver.")
        return redirect('delivery_dashboard')

    order.delivery_boy = boy
    order.save()

    messages.success(request, f"Order #{order.id} accepted. Proceed to pickup at the restaurant(s).")
    return redirect('delivery_dashboard')


def delivery_update_order_status(request, order_id):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    order = get_object_or_404(Order, id=order_id, delivery_boy=boy)

    new_status = request.POST.get('status')
    if new_status in ['Shipped', 'Delivered']:
        if new_status == 'Shipped' and order.status != 'Packed':
            messages.error(request, "You cannot start the ride until the restaurant marks it as Packed.")
        else:
            order.status = new_status
            if new_status == 'Shipped':
                est_time = request.POST.get('estimated_time')
                if est_time:
                    try:
                        order.estimated_delivery_time = int(est_time)
                    except ValueError:
                        pass
                order.ride_started_at = timezone.now()
                order.delivery_otp = None  # Reset OTP at start of ride
            order.save()
            messages.success(request, f"Order status updated to {new_status}.")
    else:
        messages.error(request, "Invalid status choice.")

    return redirect('delivery_dashboard')


def delivery_logout(request):
    if 'delivery_boy_id' in request.session:
        del request.session['delivery_boy_id']
    if 'delivery_verify_email' in request.session:
        del request.session['delivery_verify_email']
    messages.success(request, "Delivery partner logged out successfully.")
    return redirect('delivery_login')


def owner_pack_order(request, order_id):
    if 'admin_id' not in request.session:
        return redirect('adminlogin')
        
    try:
        admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
        order = get_object_or_404(Order, id=order_id)
        
        restaurant_items = OrderItem.objects.filter(
            order=order,
            food__restaurant_name=admin_user.restaurant_name
        )
        
        if not restaurant_items.exists():
            messages.error(request, "Unauthorized action.")
            return redirect('dashboard')
            
        for item in restaurant_items:
            item.status = 'Packed'
            item.save()
            
        all_order_items = OrderItem.objects.filter(order=order)
        all_packed = all_order_items.filter(status='Packed').count() == all_order_items.count()
        
        if all_packed:
            order.status = 'Packed'
            order.save()
            messages.success(request, f"Order #{order.id} marked as Packed & ready for delivery!")
        else:
            messages.success(request, f"Your items for Order #{order.id} are marked as Packed! Waiting for other restaurants to pack.")
            
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        
    return redirect('dashboard')


def delivery_request_otp(request, order_id):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    order = get_object_or_404(Order, id=order_id, delivery_boy=boy)

    import random
    otp = str(random.randint(100000, 999999))
    order.delivery_otp = otp
    order.save()

    try:
        customer_email = order.user.email if order.user else None
        if customer_email:
            subject = 'Foodeat - Delivery Verification OTP'
            message = f'Hello {order.delivery_name},\n\nYour Foodeat delivery partner is at your location.\n\nPlease share this 6-digit OTP code with the driver to receive your food:\n\nDelivery Code: {otp}\n\nRegards,\nFoodeat Logistics Team'
            send_mail(subject, message, settings.EMAIL_HOST_USER, [customer_email], fail_silently=False)
            messages.success(request, f"Delivery OTP sent successfully to customer's email ({customer_email})!")
        else:
            messages.warning(request, f"Customer has no email. Your test delivery OTP code is: {otp}")
    except Exception:
        messages.warning(request, f"Could not send email. For testing, your delivery verification OTP code is: {otp}")

    return redirect('delivery_dashboard')


def delivery_verify_order(request, order_id):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    order = get_object_or_404(Order, id=order_id, delivery_boy=boy)

    if request.method == 'POST':
        otp_input = request.POST.get('otp', '').strip()
        if order.delivery_otp and otp_input == order.delivery_otp:
            order.status = 'Delivered'
            order.delivery_otp = None
            order.save()

            # Update Rider Task Progress
            from django.utils import timezone
            from .models import DeliveryTask, DeliveryBoyTaskProgress
            order_datetime = order.order_date
            order_date = order_datetime.date()
            active_tasks = DeliveryTask.objects.filter(
                is_active=True,
                start_date__lte=order_date,
                end_date__gte=order_date,
                created_at__lte=order_datetime
            )
            for t in active_tasks:
                progress, created = DeliveryBoyTaskProgress.objects.get_or_create(
                    delivery_boy=boy,
                    task=t
                )
                if not progress.is_completed:
                    progress.orders_completed += 1
                    if progress.orders_completed >= t.required_orders:
                        progress.is_completed = True
                        progress.completed_at = timezone.now()
                    progress.save()

            messages.success(request, f"Order #{order.id} verified and marked as Delivered successfully! Good job!")
        else:
            messages.error(request, "Invalid delivery verification code. Please check and try again.")

    return redirect('delivery_dashboard')


def delivery_toggle_duty(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    if boy.is_blocked:
        messages.error(request, "Your account is blocked by the Administrator. You cannot go online.")
        return redirect('delivery_dashboard')

    if not boy.is_verified:
        messages.error(request, "Your profile is pending verification by the Super Admin. You cannot go online.")
        return redirect('delivery_dashboard')

    if boy.status == 'Off-duty':
        boy.status = 'Available'
        boy.save()
        messages.success(request, "You are now Online! You will receive new orders.")
        
        # Auto-assign the oldest unassigned order if one is waiting
        unassigned_order = Order.objects.filter(delivery_boy__isnull=True, status__in=['paid', 'Pending', 'Packed']).order_by('id').first()
        if unassigned_order:
            unassigned_order.delivery_boy = boy
            unassigned_order.save()
            boy.status = 'Delivering'
            boy.save()
            messages.info(request, f"Order #{unassigned_order.id} has been automatically assigned to you since you just went online.")
    else:
        has_active = Order.objects.filter(delivery_boy=boy, status__in=['Shipped', 'Pending', 'Packed']).exists()
        if has_active:
            messages.error(request, "You cannot go offline while you have an active delivery task.")
        else:
            boy.status = 'Off-duty'
            messages.success(request, "You are now Offline. Enjoy your rest!")
    boy.save()
    return redirect('delivery_dashboard')


def delivery_profile_edit(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        license_number = request.POST.get('license_number', '').strip()
        type_of_bike = request.POST.get('type_of_bike', '').strip()
        bike_number = request.POST.get('bike_number', '').strip()
        
        image = request.FILES.get('image')
        aadhar_card_image = request.FILES.get('aadhar_card_image')
        password = request.POST.get('password', '').strip()

        if not (name and email and phone_number and license_number and type_of_bike and bike_number):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        import re
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            messages.error(request, "Please enter a valid email address.")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        if not re.match(r'^\d{10}$', phone_number):
            messages.error(request, "Mobile number must be a valid 10-digit number.")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        clean_bike_num = bike_number.replace(" ", "").replace("-", "").upper()
        if not re.match(r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$', clean_bike_num):
            messages.error(request, "Invalid Vehicle Number. It should match RTO format (e.g. GJ05AB1234).")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        clean_license = license_number.replace(" ", "").replace("-", "").upper()
        if not re.match(r'^[A-Z]{2}\d{2}\d{4}\d{7}$', clean_license):
            messages.error(request, "Invalid Driving License. It should match RTO format (e.g. GJ0520120123456).")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        if DeliveryBoy.objects.filter(email=email).exclude(id=boy.id).exists():
            messages.error(request, "A delivery partner with this email already exists.")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        if DeliveryBoy.objects.filter(phone_number=phone_number).exclude(id=boy.id).exists():
            messages.error(request, "A delivery partner with this phone number already exists.")
            return render(request, 'delivery/edit_profile.html', {'boy': boy})

        boy.name = name
        boy.email = email
        boy.phone_number = phone_number
        boy.license_number = license_number
        boy.type_of_bike = type_of_bike
        boy.bike_number = bike_number

        if image:
            boy.image = image
        if aadhar_card_image:
            boy.aadhar_card_image = aadhar_card_image
        
        if password:
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return render(request, 'delivery/edit_profile.html', {'boy': boy})
            from django.contrib.auth.hashers import make_password
            boy.password = make_password(password)

        boy.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('delivery_dashboard')

    return render(request, 'delivery/edit_profile.html', {'boy': boy})


def delivery_vehicle_info(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')
    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    return render(request, 'delivery/vehicle_info.html', {'boy': boy})


def delivery_bank_details(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')
    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    
    if request.method == 'POST':
        request.session['bank_name'] = request.POST.get('bank_name')
        request.session['acc_holder'] = request.POST.get('acc_holder')
        request.session['acc_number'] = request.POST.get('acc_number')
        request.session['ifsc_code'] = request.POST.get('ifsc_code')
        messages.success(request, "Bank details updated successfully!")
        return redirect('delivery_bank_details')
        
    bank_details = {
        'bank_name': request.session.get('bank_name', 'HDFC Bank Ltd'),
        'acc_holder': request.session.get('acc_holder', boy.name),
        'acc_number': request.session.get('acc_number', 'XXXX XXXX 8849'),
        'ifsc_code': request.session.get('ifsc_code', 'HDFC0000123'),
    }
    return render(request, 'delivery/bank_details.html', {'boy': boy, 'bank': bank_details})


def delivery_help_support(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')
    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    return render(request, 'delivery/help_support.html', {'boy': boy})


def super_delivery_boys(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    try:
        super_user = SuperRegister.objects.get(id=request.session['super_id'])
    except SuperRegister.DoesNotExist:
        request.session.flush()
        return redirect('super_login')

    delivery_boys = DeliveryBoy.objects.all().order_by('-id')

    return render(request, 'super_admin/show_delivery_boys.html', {
        'super_user': super_user,
        'delivery_boys': delivery_boys,
        'page_title': 'Delivery Partners',
    })


def super_toggle_verify_boy(request, boy_id):
    if 'super_id' not in request.session:
        return redirect('super_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    boy.is_verified = True
    boy.save()
    
    messages.success(request, f"Delivery partner {boy.name} has been Verified successfully.")
    return redirect('super_delivery_boys')


def super_delete_boy(request, boy_id):
    if 'super_id' not in request.session:
        return redirect('super_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    name = boy.name
    boy.delete()
    
    messages.success(request, f"Delivery partner {name} deleted successfully.")
    return redirect('super_delivery_boys')


def super_toggle_block_boy(request, boy_id):
    if 'super_id' not in request.session:
        return redirect('super_login')

    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    boy.is_blocked = not boy.is_blocked
    boy.save()
    
    status_str = "Blocked" if boy.is_blocked else "Unblocked"
    messages.success(request, f"Delivery partner {boy.name} has been {status_str} successfully.")
    return redirect('super_delivery_boys')


def super_platform_settings(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    from .models import SuperRegister, PlatformSettings
    super_user = get_object_or_404(SuperRegister, id=request.session['super_id'])
    
    settings_obj, created = PlatformSettings.objects.get_or_create(id=1)

    if request.method == 'POST':
        base_delivery = request.POST.get('base_delivery_charge')
        rider_share = request.POST.get('rider_share_percentage')
        resto_commission = request.POST.get('restaurant_commission_percentage')
        bonus_threshold = request.POST.get('delivery_bonus_orders_threshold')
        bonus_amount = request.POST.get('delivery_bonus_amount')
        
        try:
            from decimal import Decimal
            new_base_delivery = Decimal(str(base_delivery))
            new_rider_share = Decimal(str(rider_share))
            new_resto_commission = Decimal(str(resto_commission))
            new_bonus_threshold = int(bonus_threshold) if bonus_threshold else 0
            new_bonus_amount = Decimal(str(bonus_amount)) if bonus_amount else Decimal('0.00')

            # Change Detection & Notifications
            if settings_obj.rider_share_percentage != new_rider_share:
                from .models import DeliveryBoy, DeliveryBoyNotification
                boys = DeliveryBoy.objects.filter(is_verified=True, is_blocked=False)
                for boy in boys:
                    DeliveryBoyNotification.objects.create(
                        delivery_boy=boy,
                        title="Rider Payout Share Updated",
                        message=f"Rider Payout Share has been updated to {new_rider_share}% by the Super Admin."
                    )
            
            if settings_obj.restaurant_commission_percentage != new_resto_commission:
                from .models import AdminOwner, RestaurantNotification
                owners = AdminOwner.objects.filter(is_approved=True, is_blocked=False)
                for owner in owners:
                    RestaurantNotification.objects.create(
                        restaurant_name=owner.restaurant_name,
                        message=f"Restaurant Commission Fee has been updated to {new_resto_commission}% by the Super Admin."
                    )

            settings_obj.base_delivery_charge = new_base_delivery
            settings_obj.rider_share_percentage = new_rider_share
            settings_obj.restaurant_commission_percentage = new_resto_commission
            settings_obj.delivery_bonus_orders_threshold = new_bonus_threshold
            settings_obj.delivery_bonus_amount = new_bonus_amount
            settings_obj.save()
            messages.success(request, "Platform charges, commission, and delivery bonus settings updated successfully!")
        except Exception as e:
            messages.error(request, f"Error saving settings: {str(e)}")
            
        return redirect('super_platform_settings')

    context = {
        'super_user': super_user,
        'settings': settings_obj,
        'page_title': 'Platform Charges Configuration'
    }
    return render(request, 'super_admin/platform_settings.html', context)


def super_delivery_tasks(request):
    if 'super_id' not in request.session:
        return redirect('super_login')

    from .models import SuperRegister, DeliveryTask, DeliveryBoyTaskProgress
    super_user = get_object_or_404(SuperRegister, id=request.session['super_id'])
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            title = request.POST.get('title')
            description = request.POST.get('description')
            required_orders = request.POST.get('required_orders')
            bonus_amount = request.POST.get('bonus_amount')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            try:
                DeliveryTask.objects.create(
                    title=title,
                    description=description,
                    required_orders=int(required_orders),
                    bonus_amount=float(bonus_amount),
                    start_date=start_date,
                    end_date=end_date
                )
                messages.success(request, f"Task '{title}' created successfully!")
            except Exception as e:
                messages.error(request, f"Failed to create task: {str(e)}")
                
        elif action == 'update':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(DeliveryTask, id=task_id)
            title = request.POST.get('title')
            description = request.POST.get('description')
            required_orders = request.POST.get('required_orders')
            bonus_amount = request.POST.get('bonus_amount')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            try:
                task.title = title
                task.description = description
                task.required_orders = int(required_orders)
                task.bonus_amount = float(bonus_amount)
                task.start_date = start_date
                task.end_date = end_date
                task.save()
                messages.success(request, f"Task '{title}' updated successfully!")
            except Exception as e:
                messages.error(request, f"Failed to update task: {str(e)}")
                
        elif action == 'toggle':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(DeliveryTask, id=task_id)
            task.is_active = not task.is_active
            task.save()
            messages.success(request, f"Task status updated successfully!")
            
        elif action == 'delete':
            task_id = request.POST.get('task_id')
            task = get_object_or_404(DeliveryTask, id=task_id)
            task.delete()
            messages.success(request, f"Task deleted successfully!")
            
        return redirect('super_delivery_tasks')

    tasks = DeliveryTask.objects.all().order_by('-start_date')
    
    # Enrich tasks with participant count and completion count
    for t in tasks:
        progresses = DeliveryBoyTaskProgress.objects.filter(task=t)
        t.total_participants = progresses.count()
        t.total_completions = progresses.filter(is_completed=True).count()

    from .models import DeliveryBoy
    total_delivery_boys = DeliveryBoy.objects.count()

    context = {
        'super_user': super_user,
        'page_title': 'Rider Milestone Tasks',
        'tasks': tasks,
        'total_delivery_boys': total_delivery_boys,
    }
    return render(request, 'super_admin/delivery_tasks.html', context)


def delivery_notifications(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    from .models import DeliveryBoy, DeliveryBoyNotification
    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    notifications = DeliveryBoyNotification.objects.filter(delivery_boy=boy).order_by('-created_at')

    context = {
        'boy': boy,
        'notifications': notifications,
    }
    return render(request, 'delivery/notifications.html', context)


def delivery_mark_notification_read(request, notif_id):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    from .models import DeliveryBoy, DeliveryBoyNotification
    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    notification = get_object_or_404(DeliveryBoyNotification, id=notif_id, delivery_boy=boy)
    notification.is_read = True
    notification.save()
    
    messages.success(request, "Notification marked as read.")
    return redirect('delivery_notifications')


def delivery_mark_all_notifications_read(request):
    boy_id = request.session.get('delivery_boy_id')
    if not boy_id:
        return redirect('delivery_login')

    from .models import DeliveryBoy, DeliveryBoyNotification
    boy = get_object_or_404(DeliveryBoy, id=boy_id)
    DeliveryBoyNotification.objects.filter(delivery_boy=boy, is_read=False).update(is_read=True)
    
    messages.success(request, "All notifications marked as read.")
    return redirect('delivery_notifications')



# Restaurant Owner Notifications
def owner_notifications(request):
    if 'admin_id' not in request.session:
        return redirect('adminlogin')
    from .models import AdminOwner, RestaurantNotification
    admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    notifications = RestaurantNotification.objects.filter(
        restaurant_name__iexact=admin_user.restaurant_name
    ).order_by('-created_at')
    
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'admin_user': admin_user,
        'notifications': notifications,
        'unread_count': unread_count,
        'page_title': 'Notifications'
    }
    return render(request, 'admin_owner/notifications.html', context)


def owner_mark_notification_read(request, notif_id):
    if 'admin_id' not in request.session:
        return redirect('adminlogin')
    from .models import RestaurantNotification
    notif = get_object_or_404(RestaurantNotification, id=notif_id)
    notif.is_read = True
    notif.save()
    messages.success(request, "Notification marked as read.")
    return redirect('owner_notifications')


def owner_mark_all_notifications_read(request):
    if 'admin_id' not in request.session:
        return redirect('adminlogin')
    from .models import AdminOwner, RestaurantNotification
    admin_user = AdminOwner.objects.get(id=request.session['admin_id'])
    RestaurantNotification.objects.filter(
        restaurant_name__iexact=admin_user.restaurant_name,
        is_read=False
    ).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('owner_notifications')


# Super Admin Notifications
def super_notifications_page(request):
    if 'super_id' not in request.session:
        return redirect('super_login')
    from .models import SuperRegister, SuperAdminNotification
    super_user = SuperRegister.objects.get(id=request.session['super_id'])
    notifications = SuperAdminNotification.objects.all().order_by('-created_at')
    
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'super_user': super_user,
        'notifications': notifications,
        'unread_count': unread_count,
        'page_title': 'Notifications'
    }
    return render(request, 'super_admin/notifications.html', context)


def super_mark_notification_read(request, notif_id):
    if 'super_id' not in request.session:
        return redirect('super_login')
    from .models import SuperAdminNotification
    notif = get_object_or_404(SuperAdminNotification, id=notif_id)
    notif.is_read = True
    notif.save()
    messages.success(request, "Notification marked as read.")
    return redirect('super_notifications_page')


def super_mark_all_notifications_read(request):
    if 'super_id' not in request.session:
        return redirect('super_login')
    from .models import SuperAdminNotification
    SuperAdminNotification.objects.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('super_notifications_page')
