"""
URL configuration for money_mate_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.views import TokenView
from loginModule import views as drf_views
from django.http import HttpResponse
from .api import api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', csrf_exempt(TokenView.as_view()), name='token'),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('api/ninja/', api.urls),
    path('api/oauth2/protected/', drf_views.protected_view, name='drf-protected'),
    path('api/oauth2/get_all_users/', drf_views.get_all_users, name='drf-get_all_users'),
    path('healthz/', lambda r: HttpResponse('ok')),

]
