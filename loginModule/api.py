#This api ahandles users

from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.contrib.auth import authenticate, login, logout
from django.db.models import QuerySet
from django.http import JsonResponse
from ninja import Router
from typing import List
from django.shortcuts import get_object_or_404
from datetime import date
from django.utils import timezone
from collections import defaultdict

from .serializers import UserSerializer
from .models import UserModel
from .schemas import LoginUserSchema, RegisterUserSchema, GetAllUserSchema, DeleteUserSchema, DeactivateUserSchema, \
    ActivateUserSchema, GetUserSchema

router = Router()

@router.get('/session')
def check_session(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email}, status=200)
    else:
        return JsonResponse({'status': 'failed'}, status=401)

@csrf_protect
@router.post('/login')
def login_view(request, payload : LoginUserSchema):
    user = authenticate(request,
                        username=payload.username,
                        password=payload.password)
    if user is None:
        return JsonResponse({"success": False, "message": "Invalid credentials"}, status=401)
    if not user.is_active:
        return JsonResponse({"success": False, "message": "Inactive user"}, status=401)
    login(request, user)
    return JsonResponse({"success": True, "message": "Login successful"}, status=200)

@csrf_protect
@router.post('/logout')
def logout_view(request):
    logout(request)
    return JsonResponse({"success": True, "message": "Logout successful"}, status=200)


@router.post('/create_user')
def create_user(request, payload : RegisterUserSchema) -> JsonResponse | None:

    if UserModel.objects.filter(username=payload.username).exists():
        return JsonResponse({'error': 'User already exists'}, status=409)
    user = UserModel.objects.create_user(username=payload.username,
                                  email=payload.email,
                                  password=payload.password,
                                  phone=payload.phone)
    return JsonResponse({'message': f'User created successfully id= {user.id}'}, status=201)



@router.delete('/remove_user/{username}')
def remove_user(request, username : str):
    deleted_count, _ = UserModel.objects.filter(username=username).delete()
    if deleted_count == 0:
        return JsonResponse({'message': 'User does not exist'}, status=404)

    return JsonResponse({'message': f'User {username} permanently deleted'}, status=200)

@router.post('/deactivate_user')
def deactivate_user(request, payload : DeactivateUserSchema):
    print(payload)
    active_user = get_object_or_404(UserModel, username = payload.username)
    print(active_user)
    active_user.is_active = False
    active_user.save()
    return JsonResponse({'message': f'User {active_user} has been deactivated'}, status=200)

@router.post('/activate_user')
def activate_user(request, payload : ActivateUserSchema):
    inactive_user = get_object_or_404(UserModel, username = payload.username)
    inactive_user.is_active = True
    inactive_user.save()
    return JsonResponse({'message': f'User {inactive_user} has been activated'}, status=200)

@router.get('/user_detail')
def get_user_details(request, payload : GetUserSchema):
    if request.user.is_authenticated:
        user_details = UserModel.objects.get(username = payload.username)
        serializer = UserSerializer(user_details)
        return JsonResponse({
            "status" : "success",
            "data" : serializer.data
        })
    return JsonResponse({"status" : "failed"}, status=401)


def get_all_users_api():

    users = UserModel.objects.all()

    serializer = UserSerializer(users, many=True)

    # 3. Return the serialized data as JSON
    return {
        "status": "success",
        "data": serializer.data
    }