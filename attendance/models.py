from django.conf import settings
from django.db import models


class Attendance(models.Model):
    SOURCE_BROWSER = 'browser'
    SOURCE_CORRECTION = 'correction'
    SOURCE_HR_HISTORICAL = 'hr_historical'
    SOURCE_CHOICES = [
        (SOURCE_BROWSER, 'Chấm công trên web'),
        (SOURCE_CORRECTION, 'Sửa chấm công'),
        (SOURCE_HR_HISTORICAL, 'HR ghi bổ sung'),
    ]

    STATUS_WORKING = 'working'
    STATUS_DONE = 'done'

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    date = models.DateField()
    original_check_in = models.DateTimeField(null=True, blank=True)
    original_check_out = models.DateTimeField(null=True, blank=True)
    effective_check_in = models.DateTimeField(null=True, blank=True)
    effective_check_out = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_BROWSER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_attendance_per_day'),
        ]

    def __str__(self):
        return f'{self.employee.employee_code} {self.date:%d/%m/%Y}'

    @property
    def is_incomplete(self):
        return self.effective_check_in is not None and self.effective_check_out is None

    @property
    def duration(self):
        if self.effective_check_in and self.effective_check_out:
            return self.effective_check_out - self.effective_check_in
        return None

    @property
    def duration_display(self):
        duration = self.duration
        if not duration:
            return None
        total_minutes = int(duration.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f'{hours}h{minutes:02d}'

    @property
    def status(self):
        if self.effective_check_in is None:
            return self.STATUS_DONE
        if self.effective_check_out is None:
            return self.STATUS_WORKING
        return self.STATUS_DONE


class CorrectionRequest(models.Model):
    STATE_PENDING = 'pending'
    STATE_APPROVED = 'approved'
    STATE_REJECTED = 'rejected'
    STATE_SUPERSEDED = 'superseded'
    STATE_CHOICES = [
        (STATE_PENDING, 'Chờ duyệt'),
        (STATE_APPROVED, 'Đã duyệt'),
        (STATE_REJECTED, 'Từ chối'),
        (STATE_SUPERSEDED, 'Đã thay thế'),
    ]

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='correction_requests',
    )
    date = models.DateField()
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correction_requests',
    )
    base_revision = models.PositiveIntegerField(default=0)
    proposed_check_in = models.DateTimeField()
    proposed_check_out = models.DateTimeField()
    reason = models.TextField()
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_PENDING)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='correction_requests',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_corrections',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee.employee_code} {self.date:%d/%m/%Y} ({self.get_state_display()})'

    @property
    def is_pending(self):
        return self.state == self.STATE_PENDING
