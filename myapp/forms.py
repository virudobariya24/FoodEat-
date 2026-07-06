from django import forms
from django.db import models
from django.contrib.auth.models import User
from .models import (
    Registration, AdminOwner, FoodItem, Discount, AddResto, 
    ContactMessage, SuperRegister
)

class RegistrationForm(forms.ModelForm):
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = Registration
        fields = [
            'first_name', 'last_name', 'phone', 'email',
            'city', 'gender', 'profile_image', 'password'
        ]
        widgets = {
            'password': forms.PasswordInput(),
            'gender': forms.Select(choices=Registration.GENDER_CHOICES),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.isdigit() or len(phone) != 10:
                raise forms.ValidationError("Mobile number must be exactly 10 digits.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class LoginForm(forms.Form):
    email = forms.CharField(label="Email or Mobile Number", widget=forms.TextInput(attrs={
        'placeholder': 'Email or Mobile Number',
        'class': 'form-control'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Password',
        'class': 'form-control'
    }))

class AdminOwnerRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = AdminOwner
        fields = ['full_name', 'email', 'password', 'restaurant_name', 'profile_image', 'aadhar_card_img']

class AdminLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'placeholder': "Business Email Address",
        'class': 'form-control'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': "Password",
        'class': 'form-control'
    }))

class FoodItemForm(forms.ModelForm):
    class Meta:
        model = FoodItem
        fields = ['restaurant_name', 'food_name', 'description', 'price', 'category', 'is_veg', 'is_spicy', 'is_available', 'food_image']

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Enter your email'}))
    
class OTPForm(forms.Form):
    otp = forms.CharField(max_length=6, widget=forms.TextInput(attrs={'placeholder': 'Enter OTP'}))
    
class ResetPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password'}))
    
    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get("password")
        cpw = cleaned_data.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error('confirm_password', "Passwords do not match")
        return cleaned_data

class DiscountForm(forms.ModelForm):
    class Meta:
        model = Discount
        fields = ['product', 'discount_percentage', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'date-picker-input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'date-picker-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        from django.utils import timezone
        today = timezone.now().date()

        if start_date:
            if start_date < today:
                self.add_error('start_date', "Start date cannot be in the past.")

        if start_date and end_date:
            if end_date < start_date:
                self.add_error('end_date', "End date must be greater than or equal to start date.")
        
        return cleaned_data

class CartForm(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.food.food_name} ({self.quantity})"

class AddRestoForm(forms.ModelForm):
    class Meta:
        model = AddResto
        fields = ['name', 'email', 'address', 'seating_capacity', 'image', 'menu', 'opening_time', 'closing_time', 'latitude', 'longitude']
        labels = {
            'name': 'Restaurant Name',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Restaurant Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Address'}),
            'seating_capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'opening_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'placeholder': 'Select on Map'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'placeholder': 'Select on Map'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'menu': forms.FileInput(attrs={'class': 'form-control'}),
        }

class SuperRegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = SuperRegister
        fields = ['full_name', 'email', 'phone', 'profile_img', 'role', 'password']
        widgets = {
            'role': forms.TextInput(attrs={'value': 'Super Admin', 'readonly': 'readonly', 'class': 'bg-slate-100 cursor-not-allowed pointer-events-none'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if not phone.isdigit() or len(phone) != 10:
                raise forms.ValidationError("Mobile number must be exactly 10 digits.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class SuperLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['full_name', 'email', 'subject', 'message']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'block w-full text-base',
                'placeholder': 'John Doe'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'block w-full text-base',
                'placeholder': 'you@example.com'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'block w-full text-base',
                'placeholder': 'e.g., Question about my order'
            }),
            'message': forms.Textarea(attrs={
                'class': 'block w-full text-base resize-none',
                'rows': 5,
                'placeholder': 'Write your message here...'
            }),
        }

class EmailForm(forms.Form):
    subject = forms.CharField(max_length=255, widget=forms.TextInput(attrs={'placeholder': 'Subject of the email'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 8, 'placeholder': 'Your message here...'}))
    attachment = forms.FileField(required=False, help_text='Optional: Attach a file (e.g., a menu)')
