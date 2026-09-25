from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance
from audit.models import AuditLog
from employees.models import Employee

from .models import LeaveRequest


User = get_user_model()


class LeaveWorkflowTests(TestCase):
    def setUp(self):
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
        self.hr = User.objects.create_user(
            username='hr-user',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )
        self.other_user = User.objects.create_user(
            username='other-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.other_employee = Employee.objects.create(
            employee_code='NV0002',
            full_name='Trần Quốc Bảo',
            joining_date=date(2024, 1, 15),
            user=self.other_user,
        )

    def _day(self, offset):
        return date.today() + timedelta(days=offset)

    def _submit(self, start, end, leave_type='annual'):
        return self.client.post(reverse('leave:create'), {
            'leave_type': leave_type,
            'start_date': start.strftime('%Y-%m-%d'),
            'end_date': end.strftime('%Y-%m-%d'),
            'reason': 'Lý do nghỉ phép',
        })

    def _make_leave(self, state, start_offset, end_offset, employee=None, requester=None):
        return LeaveRequest.objects.create(
            employee=employee or self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=self._day(start_offset),
            end_date=self._day(end_offset),
            reason='Đơn có sẵn',
            state=state,
            requester=requester or self.employee_user,
        )

    def test_01_employee_can_submit_leave(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self._submit(self._day(10), self._day(12))

        self.assertRedirects(response, reverse('leave:list'))
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.state, LeaveRequest.STATE_PENDING)
        self.assertEqual(leave.requester, self.employee_user)
        self.assertEqual(leave.days, 3)
        self.assertTrue(AuditLog.objects.filter(action='leave.create', entity_id=leave.pk).exists())

    def test_02_end_before_start_is_rejected(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self._submit(self._day(12), self._day(10))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_03_overlap_with_pending_is_blocked(self):
        self._make_leave(LeaveRequest.STATE_PENDING, 10, 12)
        self.client.login(username='emp-user', password='test-password-123')

        self._submit(self._day(11), self._day(13))

        self.assertEqual(LeaveRequest.objects.count(), 1)

    def test_04_overlap_with_approved_is_blocked(self):
        self._make_leave(LeaveRequest.STATE_APPROVED, 10, 12)
        self.client.login(username='emp-user', password='test-password-123')

        self._submit(self._day(11), self._day(13))

        self.assertEqual(LeaveRequest.objects.count(), 1)

    def test_05_adjacent_range_is_allowed(self):
        self._make_leave(LeaveRequest.STATE_APPROVED, 10, 12)
        self.client.login(username='emp-user', password='test-password-123')

        self._submit(self._day(13), self._day(15))

        self.assertEqual(LeaveRequest.objects.count(), 2)

    def test_06_hr_can_approve(self):
        leave = self._make_leave(LeaveRequest.STATE_PENDING, 10, 12)
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('leave:approve', args=[leave.pk]), {'decision_reason': 'Đồng ý'})

        self.assertRedirects(response, reverse('leave:detail', args=[leave.pk]))
        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_APPROVED)
        self.assertEqual(leave.reviewer, self.hr)
        self.assertIsNotNone(leave.decided_at)
        self.assertTrue(AuditLog.objects.filter(action='leave.approve', entity_id=leave.pk).exists())

    def test_07_hr_can_reject(self):
        leave = self._make_leave(LeaveRequest.STATE_PENDING, 10, 12)
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('leave:reject', args=[leave.pk]), {'decision_reason': 'Không hợp lệ'})

        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_REJECTED)
        self.assertEqual(leave.reviewer, self.hr)
        self.assertTrue(AuditLog.objects.filter(action='leave.reject', entity_id=leave.pk).exists())

    def test_08_hr_cannot_decide_own_request(self):
        hr_employee = Employee.objects.create(
            employee_code='NV0003',
            full_name='Phạm Văn Dũng',
            joining_date=date(2024, 1, 15),
            user=self.hr,
        )
        leave = self._make_leave(
            LeaveRequest.STATE_PENDING, 10, 12,
            employee=hr_employee, requester=self.hr,
        )
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('leave:approve', args=[leave.pk]))

        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_PENDING)

    def test_09_employee_can_cancel_pending(self):
        leave = self._make_leave(LeaveRequest.STATE_PENDING, 10, 12)
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.post(reverse('leave:cancel', args=[leave.pk]), {'cancellation_reason': 'Đổi kế hoạch'})

        self.assertRedirects(response, reverse('leave:list'))
        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_CANCELLED)
        self.assertEqual(leave.cancelled_by, self.employee_user)
        self.assertTrue(AuditLog.objects.filter(action='leave.cancel', entity_id=leave.pk).exists())

    def test_10_employee_cannot_cancel_approved(self):
        leave = self._make_leave(LeaveRequest.STATE_APPROVED, 10, 12)
        self.client.login(username='emp-user', password='test-password-123')

        self.client.post(reverse('leave:cancel', args=[leave.pk]))

        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_APPROVED)

    def test_11_hr_can_cancel_approved_with_reason(self):
        leave = self._make_leave(LeaveRequest.STATE_APPROVED, 10, 12)
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('leave:hr_cancel', args=[leave.pk]), {'cancellation_reason': ''})
        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_APPROVED)

        self.client.post(reverse('leave:hr_cancel', args=[leave.pk]), {'cancellation_reason': 'Công ty cần người'})
        leave.refresh_from_db()
        self.assertEqual(leave.state, LeaveRequest.STATE_CANCELLED)
        self.assertEqual(leave.cancelled_by, self.hr)
        self.assertEqual(leave.cancellation_reason, 'Công ty cần người')
        self.assertTrue(AuditLog.objects.filter(action='leave.hr_cancel', entity_id=leave.pk).exists())

    def test_12_leave_does_not_change_attendance(self):
        target = self._day(0)
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=target,
            original_check_in=timezone.now(),
            effective_check_in=timezone.now(),
        )
        self.client.login(username='emp-user', password='test-password-123')
        self._submit(target, target)
        leave = LeaveRequest.objects.get()
        self.client.login(username='hr-user', password='test-password-123')
        self.client.post(reverse('leave:approve', args=[leave.pk]))

        self.assertEqual(Attendance.objects.count(), 1)
        attendance.refresh_from_db()
        self.assertEqual(attendance.employee, self.employee)
        self.assertIsNotNone(attendance.original_check_in)

    def test_13_employee_cannot_access_queue_or_other_detail(self):
        other_leave = self._make_leave(
            LeaveRequest.STATE_PENDING, 10, 12,
            employee=self.other_employee, requester=self.other_user,
        )
        self.client.login(username='emp-user', password='test-password-123')

        queue_response = self.client.get(reverse('leave:queue'))
        self.assertRedirects(queue_response, '/login/?next=/leave/queue/')

        detail_response = self.client.get(reverse('leave:detail', args=[other_leave.pk]))
        self.assertRedirects(detail_response, reverse('leave:list'))

    def test_queue_rows_link_to_detail(self):
        leave = self._make_leave(LeaveRequest.STATE_PENDING, 10, 12)
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('leave:queue'))

        expected = f'data-href="{reverse("leave:detail", args=[leave.pk])}"'
        self.assertContains(response, expected)
        self.assertNotContains(response, '<th class="text-end">Thao tác</th>')
