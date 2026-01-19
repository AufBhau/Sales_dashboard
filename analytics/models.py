from django.db import models
from django.contrib.auth.models import User

class SalesData(models.Model):
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    product = models.CharField(max_length=200)
    region = models.CharField(max_length=100)
    revenue = models.DecimalField(max_digits=10, decimal_places=2)
    leads = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.product} - {self.date}"

class CSVUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    rows_imported = models.IntegerField(default=0)

    def __str__(self):
        return f"Upload by {self.user.username} at {self.uploaded_at}"