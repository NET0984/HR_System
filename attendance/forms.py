from datetime import datetime

from django import forms
from django.utils import timezone


class CorrectionRequestForm(forms.Form):
    proposed_check_in = forms.TimeField(
        label='Giờ vào đề xuất',
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
    )
    proposed_check_out = forms.TimeField(
        label='Giờ ra đề xuất',
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
    )
    reason = forms.CharField(
        label='Lý do',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ví dụ: Quên chấm công ra do họp đột xuất',
        }),
    )

    def __init__(self, *args, date=None, joining_date=None, end_date=None, **kwargs):
        self.date = date
        self.joining_date = joining_date
        self.end_date = end_date
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('proposed_check_in')
        end = cleaned.get('proposed_check_out')
        if not (start and end) or not self.date:
            return cleaned

        if end <= start:
            self.add_error('proposed_check_out', 'Giờ ra phải sau giờ vào.')
            return cleaned

        timezone_ = timezone.get_current_timezone()
        end_dt = timezone.make_aware(datetime.combine(self.date, end), timezone_)
        if end_dt > timezone.now():
            self.add_error('proposed_check_out', 'Không thể đề xuất mốc thời gian trong tương lai.')

        if self.joining_date and self.date < self.joining_date:
            self.add_error(None, 'Ngày này trước ngày vào làm của nhân viên.')
        if self.end_date and self.date > self.end_date:
            self.add_error(None, 'Ngày này sau ngày kết thúc làm việc của nhân viên.')
        return cleaned

    def proposed_datetimes(self):
        timezone_ = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(self.date, self.cleaned_data['proposed_check_in']), timezone_)
        end = timezone.make_aware(datetime.combine(self.date, self.cleaned_data['proposed_check_out']), timezone_)
        return start, end


class CorrectionDecisionForm(forms.Form):
    decision_reason = forms.CharField(
        label='Ghi chú',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Lý do duyệt hoặc từ chối (tùy chọn)',
        }),
    )


class HRAttendanceEditForm(forms.Form):
    check_in = forms.TimeField(
        label='Giờ vào',
        required=False,
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
    )
    check_out = forms.TimeField(
        label='Giờ ra',
        required=False,
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'class': 'form-control'}),
    )
    reason = forms.CharField(
        label='Lý do chỉnh sửa',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ví dụ: Nhân viên quên chấm công, HR ghi bổ sung theo xác nhận của trưởng phòng',
        }),
    )

    def __init__(self, *args, date=None, **kwargs):
        self.date = date
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('check_in')
        end = cleaned.get('check_out')
        if not start and not end:
            raise forms.ValidationError('Cần nhập ít nhất giờ vào hoặc giờ ra.')
        if start and end and end <= start:
            self.add_error('check_out', 'Giờ ra phải sau giờ vào.')
        if end and self.date:
            timezone_ = timezone.get_current_timezone()
            end_dt = timezone.make_aware(datetime.combine(self.date, end), timezone_)
            if end_dt > timezone.now():
                self.add_error('check_out', 'Không thể đặt mốc thời gian trong tương lai.')
        return cleaned

    def datetimes(self):
        timezone_ = timezone.get_current_timezone()
        start = None
        end = None
        if self.cleaned_data.get('check_in'):
            start = timezone.make_aware(datetime.combine(self.date, self.cleaned_data['check_in']), timezone_)
        if self.cleaned_data.get('check_out'):
            end = timezone.make_aware(datetime.combine(self.date, self.cleaned_data['check_out']), timezone_)
        return start, end
