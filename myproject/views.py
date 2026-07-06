from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.db import models



def login_page(request):
    return render(request, 'login.html')

def register_page(request):
    return render(request, 'register.html')


def homepage(request):
    data={'title' : 'Wel-Come Zomato'}

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
    

# Admin


def admin_deshboard(request):
    data={'title' : 'Dashborad'}

    return render(request,"admin/dashboard.html",data)

def food_add(request):
    data={'title' : 'Food Add'}

    return render(request,"admin/food_add.html",data)

# def testing(request):
#     templates = loader.get_template('template.html')
#     context = {
#         'greeting' : 2
#     }
#     return HttpResponse(templates.render(context,request))

