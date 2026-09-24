from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance, CorrectionRequest
from employees.models import Employee
from leave.models import LeaveRequest


User = get_user_model()


class AuthenticationAndRoleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='test-admin',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )
        self.employee = User.objects.create_user(
            username='test-employee',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('accounts:home'))

        self.assertRedirects(response, '/login/?next=/')

    def test_employee_can_login_and_view_home(self):
        logged_in = self.client.login(username='test-employee', password='test-password-123')

        self.assertTrue(logged_in)
        response = self.client.get(reverse('accounts:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nhân viên')
        self.assertContains(response, 'Trang chủ')

    def test_invalid_credentials_are_rejected(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'test-employee', 'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tên đăng nhập hoặc mật khẩu không đúng.')

    def test_employee_cannot_access_hr_pages(self):
        self.client.login(username='test-employee', password='test-password-123')

        response = self.client.get(reverse('employees:list'))

        self.assertRedirects(response, '/login/?next=/employees/')

    def test_hr_admin_can_access_hr_pages(self):
        self.client.login(username='test-admin', password='test-password-123')

        response = self.client.get(reverse('employees:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quản lý nhân sự')

    def test_logout_ends_the_session(self):
        self.client.login(username='test-admin', password='test-password-123')

        response = self.client.post(reverse('accounts:logout'))

        self.assertRedirects(response, reverse('accounts:login'))
        self.assertRedirects(self.client.get(reverse('accounts:home')), '/login/?next=/')


class NotificationTests(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            username='hr-user',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )
        self.employee_user = User.objects.create_user(
            username='emp-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.employee = Employee.objects.create(
            employee_code='NV0001',
            full_name='Nguyễn Minh Anh',
            joining_date=date(2024, 1, 15),
            user=self.employee_user,
        )
        self.other = Employee.objects.create(
            employee_code='NV0002',
            full_name='Trần Quốc Bảo',
            joining_date=date(2024, 1, 15),
        )

    def _home(self):
        return self.client.get(reverse('accounts:home'))

    def test_hr_notifications_count_pending_work(self):
        target = date.today() + timedelta(days=10)
        LeaveRequest.objects.create(
            employee=self.other,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=target,
            end_date=target,
            reason='Nghỉ phép',
            state=LeaveRequest.STATE_PENDING,
        )
        CorrectionRequest.objects.create(
            employee=self.other,
            date=date.today(),
            base_revision=1,
            proposed_check_in=timezone.now(),
            proposed_check_out=timezone.now(),
            reason='Sửa',
            state=CorrectionRequest.STATE_PENDING,
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self._home()

        notifications = response.context['notifications']
        self.assertEqual(notifications['count'], 2)
        self.assertEqual(notifications['pending_corrections'], 1)
        self.assertEqual(notifications['pending_leave'], 1)
        self.assertContains(response, reverse('leave:queue'))
        self.assertContains(response, reverse('attendance:correction_queue'))

    def test_hr_sees_new_submission_notification(self):
        target = date.today() + timedelta(days=10)
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=target,
            end_date=target,
            reason='Nghỉ phép',
            state=LeaveRequest.STATE_PENDING,
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self._home()

        notifications = response.context['notifications']
        self.assertEqual(notifications['count'], 1)
        self.assertEqual(len(notifications['recent']), 1)
        self.assertTrue(notifications['recent'][0]['is_new'])
        self.assertIn('Nguyễn Minh Anh', notifications['recent'][0]['title'])
        self.assertContains(response, 'Mới gửi')

    def test_hr_submission_notification_clears_after_seen(self):
        target = date.today() + timedelta(days=10)
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=target,
            end_date=target,
            reason='Nghỉ phép',
            state=LeaveRequest.STATE_PENDING,
        )
        self.client.login(username='hr-user', password='test-password-123')
        self.assertEqual(self._home().context['notifications']['count'], 1)

        self.client.post(reverse('accounts:notifications_seen'))

        notifications = self._home().context['notifications']
        self.assertEqual(notifications['count'], 0)
        self.assertEqual(len(notifications['recent']), 1)
        self.assertFalse(notifications['recent'][0]['is_new'])

    def test_employee_pending_request_does_not_notify(self):
        target = date.today() + timedelta(days=10)
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=target,
            end_date=target,
            reason='Nghỉ phép',
            state=LeaveRequest.STATE_PENDING,
        )
        self.client.login(username='emp-user', password='test-password-123')

        response = self._home()

        notifications = response.context['notifications']
        self.assertEqual(notifications['count'], 0)
        self.assertEqual(notifications['recent'], [])
        self.assertNotContains(response, 'đang chờ duyệt')

    def test_employee_sees_unread_response(self):
        target = date.today() + timedelta(days=10)
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_SICK,
            start_date=target,
            end_date=target,
            reason='Nghỉ ốm',
            state=LeaveRequest.STATE_APPROVED,
            decided_at=timezone.now(),
        )
        self.client.login(username='emp-user', password='test-password-123')

        response = self._home()

        notifications = response.context['notifications']
        self.assertEqual(notifications['count'], 1)
        self.assertEqual(len(notifications['recent']), 1)
        self.assertTrue(notifications['recent'][0]['is_new'])
        self.assertContains(response, 'Kết quả gần đây')
        self.assertContains(response, 'Mới')

    def test_marking_seen_clears_unread(self):
        target = date.today() + timedelta(days=10)
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_SICK,
            start_date=target,
            end_date=target,
            reason='Nghỉ ốm',
            state=LeaveRequest.STATE_APPROVED,
            decided_at=timezone.now(),
        )
        self.client.login(username='emp-user', password='test-password-123')
        self.assertEqual(self._home().context['notifications']['count'], 1)

        response = self.client.post(reverse('accounts:notifications_seen'))

        self.assertEqual(response.status_code, 200)
        self.employee_user.refresh_from_db()
        self.assertIsNotNone(self.employee_user.notifications_seen_at)
        after = self._home().context['notifications']
        self.assertEqual(after['count'], 0)
        self.assertFalse(after['recent'][0]['is_new'])

    def test_notifications_seen_requires_post(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.get(reverse('accounts:notifications_seen'))

        self.assertEqual(response.status_code, 405)

    def test_employee_without_activity_sees_empty_state(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self._home()

        notifications = response.context['notifications']
        self.assertEqual(notifications['count'], 0)
        self.assertEqual(notifications['recent'], [])
        self.assertContains(response, 'Không có thông báo')

    def test_hr_without_work_has_no_badge(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self._home()

        notifications = response.context['notifications']
        self.assertEqual(notifications['count'], 0)
        self.assertNotContains(response, 'class="notification-count"')

    def test_notifications_include_attendance_today_for_hr(self):
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            original_check_in=timezone.now(),
            effective_check_in=timezone.now(),
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self._home()

        self.assertEqual(response.context['notifications']['present_today'], 1)
        self.assertContains(response, 'Chấm công hôm nay')
