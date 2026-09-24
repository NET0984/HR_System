from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_EMPLOYEE = 'employee'
    ROLE_HR_ADMIN = 'hr_admin'
    ROLE_CHOICES = [
        (ROLE_EMPLOYEE, 'Nhân viên'),
        (ROLE_HR_ADMIN, 'Quản trị nhân sự'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_EMPLOYEE)
    notifications_seen_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_hr(self):
        return self.role == self.ROLE_HR_ADMIN

    def __str__(self):
        return self.username