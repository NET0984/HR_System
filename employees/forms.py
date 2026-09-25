import unicodedata

from django import forms
from django.contrib.auth import get_user_model

from .models import Department, Employee


User = get_user_model()


def _ascii_username(value):
    normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    return normalized.lower().strip()


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên phòng ban'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['full_name', 'work_email', 'phone', 'department', 'joining_date', 'end_date', 'is_active']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'work_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'joining_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control date-picker'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control date-picker'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        joining_date = cleaned.get('joining_date')
        end_date = cleaned.get('end_date')
        if joining_date and end_date and end_date < joining_date:
            self.add_error('end_date', 'Ngày kết thúc phải sau ngày vào làm.')
        return cleaned


class AccountProvisionForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        if self.employee and not self.initial.get('username'):
            local_part = self.employee.work_email.split('@')[0] if self.employee.work_email else ''
            self.fields['username'].initial = _ascii_username(local_part) or self.employee.employee_code.lower()

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Tên đăng nhập đã tồn tại.')
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'Mật khẩu xác nhận không khớp.')
        return cleaned
