from django.urls import reverse
from django.utils import timezone


def _period(start_date, end_date):
    if start_date == end_date:
        return f'{start_date:%d/%m/%Y}'
    return f'{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}'


def _leave_response(leave):
    return {
        'kind': 'leave',
        'title': 'Đơn nghỉ phép',
        'subtitle': _period(leave.start_date, leave.end_date),
        'state': leave.state,
        'state_label': leave.get_state_display(),
        'icon': 'bi-calendar2-check',
        'tone': 'purple',
        'url': reverse('leave:detail', args=[leave.pk]),
        'at': leave.decided_at or leave.cancelled_at or leave.updated_at,
    }


def _correction_response(correction):
    return {
        'kind': 'correction',
        'title': 'Yêu cầu sửa chấm công',
        'subtitle': f'{correction.date:%d/%m/%Y}',
        'state': correction.state,
        'state_label': correction.get_state_display(),
        'icon': 'bi-pencil-square',
        'tone': 'orange',
        'url': reverse('attendance:my'),
        'at': correction.decided_at or correction.updated_at,
    }


def _leave_submission(leave):
    return {
        'kind': 'leave',
        'title': f'{leave.employee.full_name} gửi đơn nghỉ phép',
        'subtitle': _period(leave.start_date, leave.end_date),
        'state': leave.state,
        'state_label': leave.get_state_display(),
        'icon': 'bi-calendar2-check',
        'tone': 'purple',
        'url': reverse('leave:detail', args=[leave.pk]),
        'at': leave.created_at,
    }


def _correction_submission(correction):
    return {
        'kind': 'correction',
        'title': f'{correction.employee.full_name} gửi yêu cầu sửa chấm công',
        'subtitle': f'{correction.date:%d/%m/%Y}',
        'state': correction.state,
        'state_label': correction.get_state_display(),
        'icon': 'bi-pencil-square',
        'tone': 'orange',
        'url': reverse('attendance:correction_detail', args=[correction.pk]),
        'at': correction.created_at,
    }


def _mark_unread(items, seen_at):
    for item in items:
        item['is_new'] = seen_at is None or item['at'] > seen_at
    return sum(1 for item in items if item['is_new'])


def notifications(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'notifications': None}

    from attendance.models import Attendance, CorrectionRequest
    from leave.models import LeaveRequest

    today = timezone.localdate()
    seen_at = user.notifications_seen_at

    if user.is_hr:
        submissions = []
        for leave in LeaveRequest.objects.select_related('employee').order_by('-created_at')[:10]:
            submissions.append(_leave_submission(leave))
        for correction in CorrectionRequest.objects.select_related('employee').order_by('-created_at')[:10]:
            submissions.append(_correction_submission(correction))
        submissions.sort(key=lambda item: item['at'], reverse=True)
        count = _mark_unread(submissions, seen_at)

        return {'notifications': {
            'is_hr': True,
            'count': count,
            'recent': submissions[:5],
            'pending_corrections': CorrectionRequest.objects.filter(
                state=CorrectionRequest.STATE_PENDING
            ).count(),
            'pending_leave': LeaveRequest.objects.filter(
                state=LeaveRequest.STATE_PENDING
            ).count(),
            'present_today': Attendance.objects.filter(date=today).count(),
        }}

    employee = getattr(user, 'employee', None)
    if not employee:
        return {'notifications': {
            'is_hr': False,
            'count': 0,
            'recent': [],
        }}

    responses = []
    for leave in LeaveRequest.objects.filter(employee=employee).exclude(
        state=LeaveRequest.STATE_PENDING
    ):
        responses.append(_leave_response(leave))
    for correction in CorrectionRequest.objects.filter(employee=employee).exclude(
        state=CorrectionRequest.STATE_PENDING
    ):
        responses.append(_correction_response(correction))
    responses.sort(key=lambda item: item['at'], reverse=True)
    count = _mark_unread(responses, seen_at)

    return {'notifications': {
        'is_hr': False,
        'count': count,
        'recent': responses[:5],
    }}
