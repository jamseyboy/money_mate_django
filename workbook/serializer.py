from rest_framework import serializers

from workbook.models import Workbook, Transaction


class WorkbookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workbook
        exclude = ['user']
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'