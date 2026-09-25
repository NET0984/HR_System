from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import AccountProvisionForm
from .models import Department, Employee


User = get_user_model()


class EmployeeModuleTests(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username='hr-user',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )
        self.employee_user = User.objects.create_user(
            username='plain-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.department = Department.objects.create(name='Kỹ thuật')

    def test_employee_role_cannot_access_employee_module(self):
        self.client.login(username='plain-user', password='test-password-123')

        response = self.client.get(reverse('employees:list'))

        self.assertRedirects(response, '/login/?next=/employees/')

    def test_hr_can_create_department(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('employees:department_list'), {'name': 'Kinh doanh'})

        self.assertRedirects(response, reverse('employees:department_list'))
        self.assertTrue(Department.objects.filter(name='Kinh doanh').exists())

    def test_employee_code_is_generated_and_unique(self):
        first = Employee.objects.create(full_name='Nguyễn Minh Anh', joining_date=date(2024, 1, 15))
        second = Employee.objects.create(full_name='Trần Quốc Bảo', joining_date=date(2024, 1, 15))

        self.assertEqual(first.employee_code, 'NV0001')
        self.assertEqual(second.employee_code, 'NV0002')

    def test_hr_can_create_employee_via_view(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('employees:create'), {
            'full_name': 'Lê Thị Chi',
            'work_email': 'chi@example.com',
            'phone': '0900000000',
            'department': self.department.pk,
            'joining_date': '2024-02-01',
            'end_date': '',
            'is_active': 'on',
        })

        employee = Employee.objects.get(full_name='Lê Thị Chi')
        self.assertRedirects(response, reverse('employees:detail', args=[employee.pk]))
        self.assertEqual(employee.employee_code, 'NV0001')

    def test_hr_can_deactivate_employee_and_block_login(self):
        employee = Employee.objects.create(
            full_name='Phạm Văn Dũng',
            joining_date=date(2024, 1, 15),
            user=self.employee_user,
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('employees:deactivate', args=[employee.pk]))

        self.assertRedirects(response, reverse('employees:detail', args=[employee.pk]))
        employee.refresh_from_db()
        self.employee_user.refresh_from_db()
        self.assertFalse(employee.is_active)
        self.assertFalse(self.employee_user.is_active)
        self.assertIsNotNone(employee.end_date)

    def test_hr_can_provision_account_for_employee(self):
        employee = Employee.objects.create(
            full_name='Hoàng Thị Em',
            joining_date=date(2024, 1, 15),
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('employees:provision_account', args=[employee.pk]), {
            'username': 'hoang-em',
            'password': 'new-password-123',
            'confirm_password': 'new-password-123',
        })

        self.assertRedirects(response, reverse('employees:detail', args=[employee.pk]))
        employee.refresh_from_db()
        self.assertIsNotNone(employee.user)
        self.assertEqual(employee.user.username, 'hoang-em')
        self.assertEqual(employee.user.role, User.ROLE_EMPLOYEE)
        self.assertTrue(self.client.login(username='hoang-em', password='new-password-123'))

    def test_provision_account_rejects_duplicate_username(self):
        employee = Employee.objects.create(
            full_name='Võ Thanh Phong',
            joining_date=date(2024, 1, 15),
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('employees:provision_account', args=[employee.pk]), {
            'username': 'plain-user',
            'password': 'new-password-123',
            'confirm_password': 'new-password-123',
        })

        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertIsNone(employee.user)

    def test_account_form_default_username_removes_diacritics(self):
        employee = Employee.objects.create(
            full_name='Trần Quốc Bảo',
            work_email='bảo@example.com',
            joining_date=date(2024, 1, 15),
        )

        form = AccountProvisionForm(employee=employee)

        self.assertEqual(form.fields['username'].initial, 'bao')

    def test_employee_list_rows_link_to_detail(self):
        employee = Employee.objects.create(
            full_name='Lê Thị Chi',
            joining_date=date(2024, 1, 15),
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('employees:list'))

        expected = f'data-href="{reverse("employees:detail", args=[employee.pk])}"'
        self.assertContains(response, expected)
        self.assertNotContains(response, '<th class="text-end">Thao tác</th>')
