from django.conf import settings
from django.db import models


class LeaveRequest(models.Model):
    TYPE_ANNUAL = 'annual'
    TYPE_SICK = 'sick'
    TYPE_PERSONAL = 'personal'
    TYPE_UNPAID = 'unpaid'
    TYPE_CHOICES = [
        (TYPE_ANNUAL, 'Phép năm'),
        (TYPE_SICK, 'Nghỉ ốm'),
        (TYPE_PERSONAL, 'Việc riêng'),
        (TYPE_UNPAID, 'Không lương'),
    ]

    STATE_PENDING = 'pending'
    STATE_APPROVED = 'approved'
    STATE_REJECTED = 'rejected'
    STATE_CANCELLED = 'cancelled'
    STATE_CHOICES = [
        (STATE_PENDING, 'Chờ duyệt'),
        (STATE_APPROVED, 'Đã duyệt'),
        (STATE_REJECTED, 'Từ chối'),
        (STATE_CANCELLED, 'Đã hủy'),
    ]

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='leave_requests',
    )
    leave_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_ANNUAL)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_PENDING)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='leave_requests',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_leave_requests',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_leave_requests',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee.employee_code} {self.start_date:%d/%m/%Y}-{self.end_date:%d/%m/%Y}'

    @property
    def is_pending(self):
        return self.state == self.STATE_PENDING

    @property
    def is_approved(self):
        return self.state == self.STATE_APPROVED

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1
