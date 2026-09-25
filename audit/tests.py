from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance, CorrectionRequest
from employees.models import Employee

from .models import AuditLog


User = get_user_model()


class AuditLogTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='emp-user',
            password='test-password-123',
            role=User.ROLE_EMPLOYEE,
        )
        self.employee = Employee.objects.create(
            full_name='Nguyễn Minh Anh',
            work_email='anh@example.com',
            joining_date=date(2024, 1, 15),
            user=self.employee_user,
        )
        self.hr = User.objects.create_user(
            username='hr-user',
            password='test-password-123',
            role=User.ROLE_HR_ADMIN,
        )

    def test_check_in_creates_audit_entry(self):
        self.client.login(username='emp-user', password='test-password-123')

        self.client.post(reverse('attendance:check_in'))

        log = AuditLog.objects.get(action='attendance.check_in')
        self.assertEqual(log.actor, self.employee_user)
        self.assertEqual(log.entity_type, 'Attendance')
        self.assertIn('effective_check_in', log.after)

    def test_correction_approval_records_before_and_after(self):
        yesterday = date.today() - timedelta(days=1)
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            original_check_in=timezone.now() - timedelta(days=1),
            effective_check_in=timezone.now() - timedelta(days=1),
            revision=1,
        )
        self.client.login(username='emp-user', password='test-password-123')
        self.client.post(reverse('attendance:correction_create'), {
            'date': yesterday.strftime('%Y-%m-%d'),
            'proposed_check_in': '08:00',
            'proposed_check_out': '17:00',
            'reason': 'Quên chấm công ra',
        })
        correction = CorrectionRequest.objects.get()
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('attendance:correction_approve', args=[correction.pk]))

        create_log = AuditLog.objects.get(action='correction.create')
        approve_log = AuditLog.objects.get(action='correction.approve')
        self.assertEqual(create_log.actor, self.employee_user)
        self.assertEqual(approve_log.actor, self.hr)
        self.assertEqual(approve_log.before['revision'], 1)
        self.assertEqual(approve_log.after['revision'], 2)
        self.assertEqual(approve_log.reason, '')

        attendance.refresh_from_db()
        self.assertEqual(attendance.revision, 2)
        self.assertIsNone(attendance.original_check_out)

    def test_rejection_creates_audit_entry(self):
        yesterday = date.today() - timedelta(days=1)
        Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            original_check_in=timezone.now() - timedelta(days=1),
            effective_check_in=timezone.now() - timedelta(days=1),
            revision=1,
        )
        self.client.login(username='emp-user', password='test-password-123')
        self.client.post(reverse('attendance:correction_create'), {
            'date': yesterday.strftime('%Y-%m-%d'),
            'proposed_check_in': '08:00',
            'proposed_check_out': '17:00',
            'reason': 'Quên chấm công ra',
        })
        correction = CorrectionRequest.objects.get()
        self.client.login(username='hr-user', password='test-password-123')

        self.client.post(reverse('attendance:correction_reject', args=[correction.pk]))

        log = AuditLog.objects.get(action='correction.reject')
        self.assertEqual(log.actor, self.hr)

    def test_hr_can_view_audit_list(self):
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('audit:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nhật ký hoạt động')

    def test_employee_cannot_view_audit_list(self):
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.get(reverse('audit:list'))

        self.assertRedirects(response, '/login/?next=/audit/')

    def test_changes_are_shown_in_vietnamese(self):
        log = AuditLog.objects.create(
            actor=self.hr,
            action='attendance.hr_edit',
            entity_type='Attendance',
            entity_id=1,
            before={'effective_check_in': '2026-09-14T01:30:00+00:00', 'revision': 1},
            after={'effective_check_in': '2026-09-14T02:00:00+00:00', 'revision': 2},
        )

        self.assertEqual(log.action_label, 'HR chỉnh sửa chấm công')
        self.assertEqual(log.entity_label, 'Chấm công')
        changes = {row['label']: row for row in log.changes}
        self.assertEqual(changes['Giờ vào']['before'], '14/09/2026 08:30')
        self.assertEqual(changes['Giờ vào']['after'], '14/09/2026 09:00')
        self.assertEqual(changes['Lần sửa']['before'], '1')
        self.assertEqual(changes['Lần sửa']['after'], '2')

    def test_source_value_is_translated(self):
        log = AuditLog.objects.create(
            actor=self.hr,
            action='attendance.hr_edit',
            entity_type='Attendance',
            entity_id=1,
            before={'source': 'browser'},
            after={'source': 'hr_historical'},
        )

        row = log.changes[0]
        self.assertEqual(row['label'], 'Nguồn')
        self.assertEqual(row['before'], 'Chấm công trên web')
        self.assertEqual(row['after'], 'HR ghi bổ sung')

    def test_audit_list_filter_shows_vietnamese_labels(self):
        AuditLog.objects.create(
            actor=self.employee_user,
            action='attendance.check_in',
            entity_type='Attendance',
            entity_id=1,
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('audit:list'))

        self.assertContains(response, 'Chấm công vào')
        self.assertNotContains(response, '>attendance.check_in<')

    def test_audit_list_rows_link_to_detail(self):
        log = AuditLog.objects.create(
            actor=self.hr,
            action='attendance.check_in',
            entity_type='Attendance',
            entity_id=1,
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('audit:list'))

        self.assertContains(response, 'data-href="%s"' % reverse('audit:detail', args=[log.pk]))
        self.assertNotContains(response, '<th>Thay đổi</th>')
        self.assertNotContains(response, '<th>Lý do</th>')

    def test_audit_detail_shows_changes_and_reason(self):
        log = AuditLog.objects.create(
            actor=self.hr,
            action='attendance.hr_edit',
            entity_type='Attendance',
            entity_id=1,
            before={'effective_check_in': '2026-09-14T01:30:00+00:00', 'revision': 1},
            after={'effective_check_in': '2026-09-14T02:00:00+00:00', 'revision': 2},
            reason='HR ghi bổ sung theo xác nhận',
        )
        self.client.login(username='hr-user', password='test-password-123')

        response = self.client.get(reverse('audit:detail', args=[log.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Giá trị trước và sau')
        self.assertContains(response, '14/09/2026 08:30')
        self.assertContains(response, '14/09/2026 09:00')
        self.assertContains(response, 'HR ghi bổ sung theo xác nhận')

    def test_employee_cannot_view_audit_detail(self):
        log = AuditLog.objects.create(
            actor=self.hr,
            action='attendance.check_in',
            entity_type='Attendance',
            entity_id=1,
        )
        self.client.login(username='emp-user', password='test-password-123')

        response = self.client.get(reverse('audit:detail', args=[log.pk]))

        self.assertRedirects(response, '/login/?next=/audit/%d/' % log.pk)
