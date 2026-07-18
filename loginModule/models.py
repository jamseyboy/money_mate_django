from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.
# data fields in DB
#               "id"
#             "password"
#             "last_login"
#             "is_superuser"
#             "username"
#             "first_name"
#             "last_name"
#             "is_staff"
#             "is_active"
#             "date_joined"
#             "email"
#             "phone"
#             "groups"
#             "user_permissions"



class UserModel(AbstractUser) :
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=120, blank=True, null=True)
    def __str__(self):
        return self.username
    class Meta:
        db_table = 'user_model'


