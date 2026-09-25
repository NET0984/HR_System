from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditLog
from employees.models import Department, Employee

from .models import Attendance, CorrectionRequest


User = get_user_model()


class AttendanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='emp-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.employee = Employee.objects.create(
            full_name='Nguyễn Minh Anh',
            joining_date=date(2024, 1, 15),
            user=self.user,
        )
        self.hr = User.objects.create_user(
            username='hr-user',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )

    def test_requires_login(self):
        response = self.client.get(reverse('attendance:my'))

        self.assertRedirects(response, '/login/?next=/attendance/')

    def test_check_in_creates_record_for_today(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.post(reverse('attendance:check_in'))

        self.assertRedirects(response, reverse('attendance:my'))
        record = Attendance.objects.get(employee=self.employee)
        self.assertEqual(record.date, date.today())
        self.assertIsNotNone(record.original_check_in)
        self.assertEqual(record.original_check_in, record.effective_check_in)
        self.assertIsNone(record.effective_check_out)

    def test_check_in_uses_local_business_date(self):
        self.client.login(username='emp-user', password='test-password-123')
        utc_moment = datetime(2024, 1, 1, 20, 0, tzinfo=dt_timezone.utc)

        with patch('django.utils.timezone.now', return_value=utc_moment):
            self.client.post(reverse('attendance:check_in'))

        record = Attendance.objects.get(employee=self.employee)
        self.assertEqual(record.date, date(2024, 1, 2))

    def test_check_in_twice_creates_single_record(self):
        self.client.login(username='emp-user', password='test-password-123')

        self.client.post(reverse('attendance:check_in'))
        self.client.post(reverse('attendance:check_in'))

        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 1)

    def test_check_out_without_check_in_is_rejected(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.post(reverse('attendance:check_out'))

        self.assertRedirects(response, reverse('attendance:my'))
        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 0)

    def test_check_out_closes_today_session(self):
        self.client.login(username='emp-user', password='test-password-123')
        self.client.post(reverse('attendance:check_in'))

        self.client.post(reverse('attendance:check_out'))

        record = Attendance.objects.get(employee=self.employee)
        self.assertIsNotNone(record.original_check_out)
        self.assertEqual(record.original_check_out, record.effective_check_out)
        self.assertIsNotNone(record.duration)
        self.assertFalse(record.is_incomplete)

    def test_hr_without_employee_cannot_check_in(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('attendance:check_in'))

        self.assertRedirects(response, reverse('attendance:my'))
        self.assertEqual(Attendance.objects.count(), 0)

    def test_history_only_shows_own_records(self):
        other_user = User.objects.create_user(
            username='other-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        other_employee = Employee.objects.create(
            full_name='Trần Quốc Bảo',
            joining_date=date(2024, 1, 15),
            user=other_user,
        )
        Attendance.objects.create(
            employee=other_employee,
            date=date.today(),
            original_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
            effective_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
        )
        self.client.login(username='emp-user', password='test-password-123')
        self.client.post(reverse('attendance:check_in'))

        response = self.client.get(reverse('attendance:my'))

        records = list(response.context['page_obj'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].employee, self.employee)

    def test_yesterday_incomplete_does_not_block_today_check_in(self):
        yesterday = date.today() - timedelta(days=1)
        Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            original_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
            effective_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
        )
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.post(reverse('attendance:check_in'))

        self.assertRedirects(response, reverse('attendance:my'))
        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 2)
        today_record = Attendance.objects.get(employee=self.employee, date=date.today())
        self.assertIsNotNone(today_record.effective_check_in)
        yesterday_record = Attendance.objects.get(employee=self.employee, date=yesterday)
        self.assertIsNone(yesterday_record.effective_check_out)
        self.assertIsNone(yesterday_record.duration)

    def test_check_out_only_closes_today_not_yesterday(self):
        yesterday = date.today() - timedelta(days=1)
        yesterday_record = Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            original_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
            effective_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
        )
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.post(reverse('attendance:check_out'))

        self.assertRedirects(response, reverse('attendance:my'))
        yesterday_record.refresh_from_db()
        self.assertIsNone(yesterday_record.effective_check_out)
        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 1)

    def test_incomplete_session_duration_is_none(self):
        record = Attendance.objects.create(
            employee=self.employee,
            date=date.today() - timedelta(days=2),
            original_check_in=datetime(2024, 1, 14, 8, 0, tzinfo=dt_timezone.utc),
            effective_check_in=datetime(2024, 1, 14, 8, 0, tzinfo=dt_timezone.utc),
        )

        self.assertTrue(record.is_incomplete)
        self.assertIsNone(record.duration)
        self.assertIsNone(record.duration_display)

    def test_attendance_page_lists_incomplete_past_sessions(self):
        yesterday = date.today() - timedelta(days=1)
        Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            original_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
            effective_check_in=datetime(2024, 1, 15, 8, 0, tzinfo=dt_timezone.utc),
        )
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.get(reverse('attendance:my'))

        incomplete = list(response.context['incomplete_records'])
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0].date, yesterday)

    def test_check_out_twice_does_not_change_first_checkout(self):
        self.client.login(username='emp-user', password='test-password-123')
        self.client.post(reverse('attendance:check_in'))
        self.client.post(reverse('attendance:check_out'))
        first_checkout = Attendance.objects.get(employee=self.employee).effective_check_out

        self.client.post(reverse('attendance:check_out'))

        record = Attendance.objects.get(employee=self.employee)
        self.assertEqual(record.effective_check_out, first_checkout)

    def test_session_does_not_span_local_midnight(self):
        self.client.login(username='emp-user', password='test-password-123')
        late_utc = datetime(2024, 1, 1, 16, 59, tzinfo=dt_timezone.utc)
        with patch('django.utils.timezone.now', return_value=late_utc):
            self.client.post(reverse('attendance:check_in'))

        after_midnight_utc = datetime(2024, 1, 1, 17, 1, tzinfo=dt_timezone.utc)
        with patch('django.utils.timezone.now', return_value=after_midnight_utc):
            response = self.client.post(reverse('attendance:check_out'))

        self.assertRedirects(response, reverse('attendance:my'))
        first_record = Attendance.objects.get(employee=self.employee, date=date(2024, 1, 1))
        self.assertEqual(first_record.effective_check_in.date(), date(2024, 1, 1))
        self.assertIsNone(first_record.effective_check_out)
        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 1)


class ConcurrentAttendanceTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='concurrent-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.employee = Employee.objects.create(
            full_name='Nguyễn Minh Anh',
            joining_date=date(2024, 1, 15),
            user=self.user,
        )

    def _submit_check_in(self):
        try:
            client = Client()
            client.login(username='concurrent-user', password='test-password-123')
            return client.post(reverse('attendance:check_in')).status_code
        finally:
            connections.close_all()

    def test_concurrent_check_in_creates_single_record(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: self._submit_check_in(), range(2)))

        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 1)
        self.assertTrue(all(status == 302 for status in statuses))


class CorrectionWorkflowTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='emp-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.employee = Employee.objects.create(
            full_name='Nguyễn Minh Anh',
            joining_date=date(2024, 1, 15),
            user=self.employee_user,
        )
        self.hr = User.objects.create_user(
            username='hr-user',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )
        self.yesterday = date.today() - timedelta(days=1)
        self.attendance = Attendance.objects.create(
            employee=self.employee,
            date=self.yesterday,
            original_check_in=timezone.now() - timedelta(days=1),
            effective_check_in=timezone.now() - timedelta(days=1),
            revision=1,
        )

    def _submit_correction(self, target_date=None, proposed_in='08:00', proposed_out='17:00'):
        return self.client.post(reverse('attendance:correction_create'), {
            'date': (target_date or self.yesterday).strftime('%Y-%m-%d'),
            'proposed_check_in': proposed_in,
            'proposed_check_out': proposed_out,
            'reason': 'Quên chấm công ra',
        })

    def test_employee_can_submit_correction(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self._submit_correction()

        self.assertRedirects(response, reverse('attendance:my'))
        correction = CorrectionRequest.objects.get(employee=self.employee)
        self.assertEqual(correction.state, CorrectionRequest.STATE_PENDING)
        self.assertEqual(correction.base_revision, 1)
        self.assertEqual(correction.attendance, self.attendance)
        self.assertEqual(correction.requester, self.employee_user)

    def test_cannot_submit_for_future_date(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self._submit_correction(target_date=date.today() + timedelta(days=1))

        self.assertRedirects(response, reverse('attendance:my'))
        self.assertEqual(CorrectionRequest.objects.count(), 0)

    def test_only_one_pending_request_per_day(self):
        self.client.login(username='emp-user', password='test-password-123')

        self._submit_correction()
        self._submit_correction()

        self.assertEqual(
            CorrectionRequest.objects.filter(
                employee=self.employee,
                date=self.yesterday,
                state=CorrectionRequest.STATE_PENDING,
            ).count(),
            1,
        )

    def test_hr_approve_updates_effective_and_keeps_original(self):
        self.client.login(username='emp-user', password='test-password-123')
        self._submit_correction()
        correction = CorrectionRequest.objects.get()
        original_in = self.attendance.original_check_in
        original_out = self.attendance.original_check_out
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('attendance:correction_approve', args=[correction.pk]))

        self.assertRedirects(response, reverse('attendance:correction_detail', args=[correction.pk]))
        correction.refresh_from_db()
        self.attendance.refresh_from_db()
        self.assertEqual(correction.state, CorrectionRequest.STATE_APPROVED)
        self.assertEqual(correction.reviewer, self.hr)
        self.assertEqual(self.attendance.original_check_in, original_in)
        self.assertEqual(self.attendance.original_check_out, original_out)
        self.assertEqual(self.attendance.effective_check_in, correction.proposed_check_in)
        self.assertEqual(self.attendance.effective_check_out, correction.proposed_check_out)
        self.assertEqual(self.attendance.revision, 2)
        self.assertEqual(self.attendance.source, Attendance.SOURCE_CORRECTION)

    def test_hr_reject_keeps_attendance_unchanged(self):
        self.client.login(username='emp-user', password='test-password-123')
        self._submit_correction()
        correction = CorrectionRequest.objects.get()
        effective_in = self.attendance.effective_check_in
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('attendance:correction_reject', args=[correction.pk]))

        self.assertRedirects(response, reverse('attendance:correction_detail', args=[correction.pk]))
        correction.refresh_from_db()
        self.attendance.refresh_from_db()
        self.assertEqual(correction.state, CorrectionRequest.STATE_REJECTED)
        self.assertIsNone(self.attendance.effective_check_out)
        self.assertEqual(self.attendance.effective_check_in, effective_in)
        self.assertEqual(self.attendance.revision, 1)

    def test_stale_request_is_superseded(self):
        self.client.login(username='emp-user', password='test-password-123')
        self._submit_correction()
        correction = CorrectionRequest.objects.get()
        self.attendance.revision = 2
        self.attendance.save(update_fields=['revision'])
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(reverse('attendance:correction_approve', args=[correction.pk]))

        self.assertRedirects(response, reverse('attendance:correction_detail', args=[correction.pk]))
        correction.refresh_from_db()
        self.attendance.refresh_from_db()
        self.assertEqual(correction.state, CorrectionRequest.STATE_SUPERSEDED)
        self.assertIsNone(self.attendance.effective_check_out)

    def test_hr_cannot_decide_own_request(self):
        hr_employee = Employee.objects.create(
            full_name='Phạm Văn Dũng',
            joining_date=date(2024, 1, 15),
            user=self.hr,
        )
        correction = CorrectionRequest.objects.create(
            employee=hr_employee,
            date=self.yesterday,
            base_revision=0,
            proposed_check_in=timezone.now() - timedelta(days=1),
            proposed_check_out=timezone.now() - timedelta(days=1) + timedelta(hours=8),
            reason='Tự gửi',
            requester=self.hr,
        )
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('attendance:correction_approve', args=[correction.pk]))

        correction.refresh_from_db()
        self.assertEqual(correction.state, CorrectionRequest.STATE_PENDING)

    def test_approve_creates_record_for_missed_day(self):
        missed_date = date.today() - timedelta(days=3)
        self.client.login(username='emp-user', password='test-password-123')
        self._submit_correction(target_date=missed_date)
        correction = CorrectionRequest.objects.get()
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('attendance:correction_approve', args=[correction.pk]))

        record = Attendance.objects.get(employee=self.employee, date=missed_date)
        self.assertIsNone(record.original_check_in)
        self.assertIsNone(record.original_check_out)
        self.assertEqual(record.effective_check_in, correction.proposed_check_in)
        self.assertEqual(record.effective_check_out, correction.proposed_check_out)
        self.assertEqual(record.source, Attendance.SOURCE_CORRECTION)

    def test_employee_cannot_access_correction_queue(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.get(reverse('attendance:correction_queue'))

        self.assertRedirects(response, '/login/?next=/attendance/corrections/')


class HRAttendanceManageTests(TestCase):
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
        self.department = Department.objects.create(name='Kỹ thuật')
        self.employee = Employee.objects.create(
            employee_code='NV0001',
            full_name='Nguyễn Minh Anh',
            joining_date=date(2024, 1, 15),
            department=self.department,
            user=self.employee_user,
        )
        self.other_department = Department.objects.create(name='Kinh doanh')
        self.other_employee = Employee.objects.create(
            employee_code='NV0002',
            full_name='Trần Quốc Bảo',
            joining_date=date(2024, 1, 15),
            department=self.other_department,
        )
        self.target_date = date.today() - timedelta(days=1)

    def _edit_url(self):
        return reverse('attendance:manage_edit', args=[self.employee.pk])

    def test_employee_cannot_access_manage(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.get(reverse('attendance:manage'))

        self.assertRedirects(response, '/login/?next=/attendance/manage/')

    def test_hr_sees_all_employees(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('attendance:manage'), {'date': self.target_date.strftime('%Y-%m-%d')})

        self.assertEqual(response.status_code, 200)
        codes = [row['employee'].employee_code for row in response.context['rows']]
        self.assertIn('NV0001', codes)
        self.assertIn('NV0002', codes)

    def test_filter_by_department(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('attendance:manage'), {
            'date': self.target_date.strftime('%Y-%m-%d'),
            'department': self.other_department.pk,
        })

        codes = [row['employee'].employee_code for row in response.context['rows']]
        self.assertEqual(codes, ['NV0002'])

    def test_filter_by_status_none(self):
        Attendance.objects.create(
            employee=self.employee,
            date=self.target_date,
            original_check_in=timezone.now(),
            effective_check_in=timezone.now(),
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('attendance:manage'), {
            'date': self.target_date.strftime('%Y-%m-%d'),
            'status': 'none',
        })

        codes = [row['employee'].employee_code for row in response.context['rows']]
        self.assertEqual(codes, ['NV0002'])

    def test_quick_edit_creates_record_for_missed_day(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(self._edit_url(), {
            'date': self.target_date.strftime('%Y-%m-%d'),
            'check_in': '08:00',
            'check_out': '17:00',
            'reason': 'HR ghi bổ sung theo xác nhận',
        })

        self.assertEqual(response.status_code, 302)
        record = Attendance.objects.get(employee=self.employee, date=self.target_date)
        self.assertIsNone(record.original_check_in)
        self.assertIsNone(record.original_check_out)
        self.assertEqual(timezone.localtime(record.effective_check_in).strftime('%H:%M'), '08:00')
        self.assertEqual(timezone.localtime(record.effective_check_out).strftime('%H:%M'), '17:00')
        self.assertEqual(record.source, Attendance.SOURCE_HR_HISTORICAL)
        self.assertTrue(AuditLog.objects.filter(action='attendance.hr_edit', entity_id=record.pk).exists())

    def test_quick_edit_updates_effective_and_keeps_original(self):
        record = Attendance.objects.create(
            employee=self.employee,
            date=self.target_date,
            original_check_in=timezone.now() - timedelta(hours=9),
            effective_check_in=timezone.now() - timedelta(hours=9),
            revision=1,
        )
        original_in = record.original_check_in
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(self._edit_url(), {
            'date': self.target_date.strftime('%Y-%m-%d'),
            'check_in': '09:00',
            'check_out': '18:00',
            'reason': 'Điều chỉnh theo thực tế',
        })

        record.refresh_from_db()
        self.assertEqual(record.original_check_in, original_in)
        self.assertEqual(timezone.localtime(record.effective_check_in).strftime('%H:%M'), '09:00')
        self.assertEqual(record.revision, 2)
        self.assertEqual(record.source, Attendance.SOURCE_HR_HISTORICAL)

    def test_quick_edit_requires_reason(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(self._edit_url(), {
            'date': self.target_date.strftime('%Y-%m-%d'),
            'check_in': '08:00',
            'check_out': '17:00',
            'reason': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Attendance.objects.filter(employee=self.employee, date=self.target_date).exists())

    def test_quick_edit_rejects_future_time(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.post(self._edit_url(), {
            'date': date.today().strftime('%Y-%m-%d'),
            'check_in': '08:00',
            'check_out': '23:59',
            'reason': 'Thử tương lai',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Attendance.objects.filter(employee=self.employee, date=date.today()).exists())

    def test_manage_rows_link_to_edit(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('attendance:manage'), {
            'date': self.target_date.strftime('%Y-%m-%d'),
        })

        expected = 'data-href="%s?date=%s"' % (
            reverse('attendance:manage_edit', args=[self.employee.pk]),
            self.target_date.strftime('%Y-%m-%d'),
        )
        self.assertContains(response, expected)
        self.assertNotContains(response, '<th class="text-end">Thao tác</th>')
