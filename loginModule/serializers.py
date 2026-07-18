# loginModule/serializers.py
from rest_framework import serializers
from loginModule.models import UserModel

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        # Use '__all__' to return every column, or list them explicitly: ['id', 'username', 'email']
        #fields = '__all__'
        exclude = ['password', 'is_superuser']