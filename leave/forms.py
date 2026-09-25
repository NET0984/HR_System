from django import forms

from .models import LeaveRequest


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control date-picker'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control date-picker'}),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ví dụ: Nghỉ phép năm đi du lịch cùng gia đình',
            }),
        }

    def __init__(self, *args, employee=None, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if not (start and end):
            return cleaned

        if end < start:
            self.add_error('end_date', 'Ngày kết thúc phải sau hoặc bằng ngày bắt đầu.')
            return cleaned

        if self.employee:
            if start < self.employee.joining_date:
                self.add_error('start_date', 'Ngày bắt đầu trước ngày vào làm của nhân viên.')
            if self.employee.end_date and end > self.employee.end_date:
                self.add_error('end_date', 'Ngày kết thúc sau ngày kết thúc làm việc của nhân viên.')
            if self._has_overlap(start, end):
                self.add_error(None, 'Khoảng nghỉ trùng với một đơn đang chờ duyệt hoặc đã duyệt.')
        return cleaned

    def _has_overlap(self, start, end):
        return LeaveRequest.objects.filter(
            employee=self.employee,
            state__in=[LeaveRequest.STATE_PENDING, LeaveRequest.STATE_APPROVED],
            start_date__lte=end,
            end_date__gte=start,
        ).exists()


class LeaveDecisionForm(forms.Form):
    decision_reason = forms.CharField(
        label='Ghi chú',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Lý do duyệt hoặc từ chối (tùy chọn)',
        }),
    )


class LeaveCancelForm(forms.Form):
    cancellation_reason = forms.CharField(
        label='Lý do hủy',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Lý do hủy (tùy chọn)',
        }),
    )

    def __init__(self, *args, require_reason=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cancellation_reason'].required = require_reason
