from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from oauth2_provider.decorators import protected_resource
import logging
from rest_framework.permissions import BasePermission
from .api import get_all_users_api

from loginModule.api import Router

logger = logging.getLogger(__name__)

router= Router()


class IsOAuth2Authenticated(BasePermission):
    """
    Allow access if OAuth2 token is valid.
    Works with client_credentials grant where request.user may be None.
    """
    def has_permission(self, request, view):
        # Allow if request.auth exists (OAuth2 token is valid)
        return request.auth is not None


@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])  # ← Use custom permission
def protected_view(request):
    return Response({
        'message': 'OAuth2 authenticated!',
        'auth_token': str(request.auth)[:20] + '...',
        'status': 'authenticated'
    })

@api_view(['GET'])
@permission_classes([IsOAuth2Authenticated])
def get_all_users(request):
    return Response(get_all_users_api())



