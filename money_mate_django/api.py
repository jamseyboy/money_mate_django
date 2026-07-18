from django.shortcuts import render
from ninja import NinjaAPI, Schema
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_jwt.authentication import JWTAuth
from ninja_extra import  NinjaExtraAPI

from loginModule.models import UserModel

api = NinjaExtraAPI(auth=None)

api.register_controllers(NinjaJWTDefaultController)
api.add_router("/user/", "loginModule.api.router")
api.add_router("/workbook/", "workbook.api.router")


@api.get("/hello")
def hello(request):
    print(request)
    return render(request, "hello.html")


@api.get('/users-page')
def users_page(request):
    # 1. Fetch the users directly from the database
    users = UserModel.objects.all()

    # 2. Pass them to the HTML template in a dictionary
    return render(request, "alluser.html", {"users": users})