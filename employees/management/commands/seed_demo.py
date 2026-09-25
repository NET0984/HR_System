from datetime import date
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from employees.models import Department, Employee


User = get_user_model()

DEPARTMENTS = ['Kinh doanh', 'Kỹ thuật', 'Nhân sự']

EMPLOYEES = [
    ('Nguyễn Minh Anh', 'Kinh doanh', 'anh'),
    ('Trần Quốc Bảo', 'Kỹ thuật', None),
    ('Lê Thị Chi', 'Kỹ thuật', None),
    ('Phạm Văn Dũng', 'Nhân sự', None),
    ('Hoàng Thị Em', 'Kinh doanh', None),
    ('Võ Thanh Phong', 'Kỹ thuật', None),
]


class Command(BaseCommand):
    help = 'Tạo dữ liệu demo cho phòng ban và nhân viên.'

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        departments = {}
        for name in DEPARTMENTS:
            department, _ = Department.objects.get_or_create(name=name)
            departments[name] = department
        self.stdout.write(f'Phòng ban: {len(departments)}')

        created = 0
        for full_name, department_name, username in EMPLOYEES:
            email_slug = full_name.split()[-1].lower()
            employee, is_new = Employee.objects.get_or_create(
                full_name=full_name,
                defaults={
                    'work_email': f'{email_slug}@example.com',
                    'department': departments[department_name],
                    'joining_date': date(2024, 1, 15),
                    'is_active': True,
                },
            )
            if is_new:
                created += 1
            if username:
                user = User.objects.filter(username=username).first()
                if user and employee.user_id is None:
                    employee.user = user
                    employee.save(update_fields=['user'])

        self.stdout.write(self.style.SUCCESS(f'Đã tạo {created} nhân viên mới. Tổng: {Employee.objects.count()}'))
