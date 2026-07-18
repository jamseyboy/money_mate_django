from django.urls import path
from . import views, api

urlpatterns = [
    path('protected/', views.protected_view, name='protected'),
    path('get_all_users/', views.get_all_users, name='get_all_users'),
]