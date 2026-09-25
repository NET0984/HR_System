from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


def _format_datetime(value):
    try:
        moment = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return value
    if timezone.is_aware(moment):
        moment = timezone.localtime(moment)
    return moment.strftime('%d/%m/%Y %H:%M')


def _format_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return value


class AuditLog(models.Model):
    ACTION_LABELS = {
        'attendance.check_in': 'Chấm công vào',
        'attendance.check_out': 'Chấm công ra',
        'attendance.hr_edit': 'HR chỉnh sửa chấm công',
        'correction.create': 'Gửi yêu cầu sửa',
        'correction.approve': 'Duyệt yêu cầu sửa',
        'correction.reject': 'Từ chối yêu cầu sửa',
        'correction.supersede': 'Yêu cầu sửa bị thay thế',
        'leave.create': 'Gửi đơn nghỉ phép',
        'leave.approve': 'Duyệt đơn nghỉ phép',
        'leave.reject': 'Từ chối đơn nghỉ phép',
        'leave.cancel': 'Hủy đơn nghỉ phép',
        'leave.hr_cancel': 'HR hủy đơn nghỉ phép',
    }
    ENTITY_LABELS = {
        'Attendance': 'Chấm công',
        'CorrectionRequest': 'Yêu cầu sửa',
        'LeaveRequest': 'Đơn nghỉ phép',
    }
    FIELD_LABELS = {
        'effective_check_in': 'Giờ vào',
        'effective_check_out': 'Giờ ra',
        'original_check_in': 'Giờ vào gốc',
        'original_check_out': 'Giờ ra gốc',
        'proposed_check_in': 'Giờ vào đề xuất',
        'proposed_check_out': 'Giờ ra đề xuất',
        'revision': 'Lần sửa',
        'base_revision': 'Bản sửa gốc',
        'source': 'Nguồn',
        'date': 'Ngày',
        'leave_type': 'Loại nghỉ',
        'start_date': 'Từ ngày',
        'end_date': 'Đến ngày',
        'state': 'Trạng thái',
    }
    VALUE_LABELS = {
        'browser': 'Chấm công trên web',
        'correction': 'Sửa chấm công',
        'hr_historical': 'HR ghi bổ sung',
        'annual': 'Phép năm',
        'sick': 'Nghỉ ốm',
        'personal': 'Việc riêng',
        'unpaid': 'Không lương',
        'pending': 'Chờ duyệt',
        'approved': 'Đã duyệt',
        'rejected': 'Từ chối',
        'cancelled': 'Đã hủy',
    }
    DATETIME_FIELDS = {
        'effective_check_in',
        'effective_check_out',
        'original_check_in',
        'original_check_out',
        'proposed_check_in',
        'proposed_check_out',
    }
    DATE_FIELDS = {
        'date',
        'start_date',
        'end_date',
    }

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=60)
    entity_id = models.PositiveIntegerField()
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f'{self.created_at:%d/%m/%Y %H:%M} {self.actor} {self.action}'

    @property
    def action_label(self):
        return self.ACTION_LABELS.get(self.action, self.action)

    @property
    def entity_label(self):
        return self.ENTITY_LABELS.get(self.entity_type, self.entity_type)

    def _display_value(self, key, value):
        if value is None:
            return '—'
        if key in self.DATETIME_FIELDS:
            return _format_datetime(value)
        if key in self.DATE_FIELDS:
            return _format_date(value)
        if isinstance(value, str):
            return self.VALUE_LABELS.get(value, value)
        return str(value)

    @property
    def changes(self):
        keys = []
        for source in (self.before or {}, self.after or {}):
            for key in source:
                if key not in keys:
                    keys.append(key)

        rows = []
        for key in keys:
            before_raw = (self.before or {}).get(key)
            after_raw = (self.after or {}).get(key)
            if before_raw == after_raw:
                continue
            rows.append({
                'label': self.FIELD_LABELS.get(key, key),
                'before': self._display_value(key, before_raw),
                'after': self._display_value(key, after_raw),
            })
        return rows
