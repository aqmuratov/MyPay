from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('100000'))

    def __str__(self):
        return f'{self.user.username}: {self.balance}'


class Transaction(models.Model):
    KINDS = [('transfer', "O'tkazma"), ('payment', "To'lov")]
    sender = models.ForeignKey(Wallet, null=True, on_delete=models.SET_NULL, related_name='sent')
    receiver = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.SET_NULL, related_name='received')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    kind = models.CharField(max_length=20, choices=KINDS, default='transfer')
    title = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']