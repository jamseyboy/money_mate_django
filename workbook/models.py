from django.db import models
from django.conf import settings
from django.db.models import ForeignKey


# Create your models here.
#Categories (Typeable fields)

# Amount(integer)
#
# Remarks (Typable fields)
#
# Nature (credit/debit)
#
# Date (calendar)


class Workbook(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        to_field='username',
        db_column='user_username',
        related_name='workbooks'
    )

    # Adding a title helps distinguish between a user's multiple workbooks
    title = models.CharField(max_length=255, default="My Workbook")
    opening_balance = models.DecimalField(decimal_places=4, max_digits=20, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class Transaction(models.Model):
    NATURE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]

    # Links the transaction to a specific workbook
    workbook = models.ForeignKey(
        Workbook,
        on_delete=models.CASCADE,
        related_name='transactions'
    )

    category = models.CharField(max_length=255)
    amount = models.IntegerField()
    remarks = models.TextField(blank=True, null=True)
    nature = models.CharField(max_length=6, choices=NATURE_CHOICES)
    date = models.DateField()

    def __str__(self):
        return f"{self.date} | {self.category} - {self.nature.capitalize()} {self.amount}"
