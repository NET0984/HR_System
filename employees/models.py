from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return str(self.name)


class Employee(models.Model):
    employee_code = models.CharField(max_length=20, unique=True, blank=True)
    full_name = models.CharField(max_length=120)
    work_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
    )
    joining_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_code']

    def __str__(self):
        return f'{self.employee_code} - {self.full_name}'

    def save(self, *args, **kwargs):
        if not self.employee_code:
            self.employee_code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        numbers = []
        for code in Employee.objects.filter(employee_code__startswith='NV').values_list('employee_code', flat=True):
            try:
                numbers.append(int(code[2:]))
            except (TypeError, ValueError):
                continue
        next_number = max(numbers, default=0) + 1
        return f'NV{next_number:04d}'
