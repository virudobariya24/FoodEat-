from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password


class Registration(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=False)
    phone = models.CharField(max_length=15)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Other')
    city = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    password = models.CharField(max_length=100)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class AdminOwner(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    restaurant_name = models.CharField(max_length=255)
    restaurant_address = models.TextField()
    profile_image = models.ImageField(upload_to='owner_images/', null=True, blank=True)
    aadhar_card_img = models.ImageField(upload_to='aadhar_images/', null=True, blank=True)
    is_blocked = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepting_orders = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name


class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()

    def __str__(self):
        return self.name


class FoodItem(models.Model):
    restaurant_name = models.CharField(max_length=100)
    food_name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)
    is_veg = models.BooleanField(default=False)
    is_spicy = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    food_image = models.ImageField(upload_to='food_images/')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.restaurant_name} - {self.food_name}"

    @property
    def average_rating(self):
        ratings = self.orderitem_set.filter(order__food_rating__gt=0).values_list('order__food_rating', flat=True)
        if ratings.exists():
            return round(sum(ratings) / len(ratings), 1)
        return None


class Product(models.Model):
    food_name = models.CharField(max_length=200)
    food_image = models.ImageField(upload_to='products/')

    def __str__(self):
        return self.food_name


class Discount(models.Model):
    product = models.ForeignKey(
        'FoodItem',
        on_delete=models.CASCADE,
        related_name='discounts'
    )
    discount_percentage = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.food_name} - {self.discount_percentage}%"


class Food(models.Model):
    food_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    food_image = models.ImageField(upload_to="food_images/", blank=True, null=True)

    def __str__(self):
        return self.food_name


class Cart(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.first_name} - {self.food.food_name} ({self.quantity})"


class Order_pay(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    wallet_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=100, default="created")
    created_at = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE, null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    total_amount = models.FloatField()
    total_discount = models.FloatField(default=0)
    final_amount = models.FloatField()
    delivery_name = models.CharField(max_length=255)
    delivery_phone = models.CharField(max_length=15)
    delivery_address = models.TextField()
    delivery_charge = models.FloatField(default=0.0)
    rider_earning = models.FloatField(default=0.0)
    restaurant_commission = models.FloatField(default=0.0)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='Pending')
    delivery_boy = models.ForeignKey('DeliveryBoy', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    delivery_otp = models.CharField(max_length=6, null=True, blank=True)
    estimated_delivery_time = models.IntegerField(null=True, blank=True)
    ride_started_at = models.DateTimeField(null=True, blank=True)
    food_rating = models.IntegerField(null=True, blank=True)
    delivery_rating = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Order {self.id} - {self.user.first_name if self.user else 'Guest'}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.FloatField()
    discount = models.FloatField(default=0)
    restaurant_commission = models.FloatField(default=0.0)
    status = models.CharField(max_length=50, default='Pending')

    def __str__(self):
        return f"{self.food.food_name} x {self.quantity}"

    @property
    def subtotal(self):
        return (self.price - self.discount) * self.quantity

    @property
    def discounted_unit_price(self):
        return self.price - self.discount


class AddResto(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    address = models.TextField()
    seating_capacity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='restaurant_images/')
    menu = models.FileField(upload_to='restaurant_menus/', null=True, blank=True)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    is_accepting_orders = models.BooleanField(default=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return self.name


class Booking(models.Model):
    restaurant = models.ForeignKey(AddResto, on_delete=models.CASCADE, related_name="bookings")
    customer_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    members = models.PositiveIntegerField()
    booking_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - {self.restaurant.name}"


class SuperRegister(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_img = models.ImageField(upload_to='super_images/', blank=True, null=True)
    role = models.CharField(max_length=50, default='Super Admin')
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'super_register'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.full_name


class ContactMessage(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    reply_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.subject}"


class Booking_resto(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
    ]
    restaurant = models.ForeignKey(AddResto, on_delete=models.CASCADE, related_name="bookings_resto")
    customer_name = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    address = models.TextField()
    members = models.PositiveIntegerField()
    booking_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"{self.customer_name} - {self.restaurant.name}"


class UserAddress(models.Model):
    ADDRESS_TYPES = [
        ('Home', 'Home'),
        ('Work', 'Work'),
        ('Other', 'Other'),
    ]
    user = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='saved_addresses')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='Home')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    house_no = models.CharField(max_length=100, blank=True, null=True)
    building_name = models.CharField(max_length=255, blank=True, null=True)
    floor = models.CharField(max_length=100, blank=True, null=True)
    landmark = models.CharField(max_length=255, blank=True, null=True)
    complete_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.first_name} - {self.address_type} ({self.complete_address[:30]})"

    @property
    def full_address(self):
        details = []
        if self.address_type == 'Home':
            if self.house_no: details.append(f"House/Flat: {self.house_no}")
            if self.building_name: details.append(f"Building: {self.building_name}")
        elif self.address_type == 'Work':
            if self.building_name: details.append(f"Office: {self.building_name}")
            if self.floor: details.append(f"Floor: {self.floor}")
        else: # Other
            if self.building_name: details.append(f"Label: {self.building_name}")
            if self.house_no: details.append(f"Details: {self.house_no}")
        
        if self.landmark:
            details.append(f"Landmark: {self.landmark}")
            
        formatted_details = ", ".join(details)
        if formatted_details:
            return f"{formatted_details}, {self.complete_address}"
        return self.complete_address


class DeliveryBoy(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='delivery_boys/', null=True, blank=True)
    license_number = models.CharField(max_length=50, null=True, blank=True)
    type_of_bike = models.CharField(max_length=50)
    bike_number = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    address = models.TextField(null=True, blank=True)
    aadhar_card_image = models.ImageField(upload_to='aadhar_cards/', null=True, blank=True)
    password = models.CharField(max_length=255, default='')
    otp = models.CharField(max_length=6, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='Available') # Available, Delivering, Off-duty

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class RestaurantNotification(models.Model):
    restaurant_name = models.CharField(max_length=255)
    message = models.TextField()
    order = models.ForeignKey('Order', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.restaurant_name} - {self.message[:30]}"


class SuperAdminNotification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, default='/show_orders/')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Super Admin: {self.title}"


class PlatformSettings(models.Model):
    base_delivery_charge = models.DecimalField(max_digits=6, decimal_places=2, default=50.00)
    rider_share_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=80.00)
    restaurant_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    delivery_bonus_orders_threshold = models.IntegerField(default=10)
    delivery_bonus_amount = models.DecimalField(max_digits=8, decimal_places=2, default=100.00)

    def __str__(self):
        return f"Platform Settings Config (Delivery: ₹{self.base_delivery_charge}, Rider: {self.rider_share_percentage}%, Resto: {self.restaurant_commission_percentage}%)"


class DeliveryTask(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    required_orders = models.IntegerField(default=10)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    import django.utils.timezone
    created_at = models.DateTimeField(default=django.utils.timezone.now)

    def __str__(self):
        return f"{self.title} (Target: {self.required_orders} orders, Bonus: ₹{self.bonus_amount})"


class DeliveryBoyTaskProgress(models.Model):
    delivery_boy = models.ForeignKey(DeliveryBoy, on_delete=models.CASCADE, related_name='task_progress')
    task = models.ForeignKey(DeliveryTask, on_delete=models.CASCADE, related_name='rider_progress')
    orders_completed = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    is_claimed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('delivery_boy', 'task')

    def __str__(self):
        return f"{self.delivery_boy.name} - {self.task.title} ({self.orders_completed}/{self.task.required_orders})"


class WalletTransaction(models.Model):
    user = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20) # 'Admin Add', 'Admin Deduct', 'Deposit', 'Order Payment'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.first_name} - {self.transaction_type} of ₹{self.amount}"


class DeliveryBoyNotification(models.Model):
    delivery_boy = models.ForeignKey(DeliveryBoy, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.delivery_boy.name} - {self.title} - Read: {self.is_read}"
