import sys

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import Attendance
from audit.models import AuditLog

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class Command(BaseCommand):
    help = 'Xoá các bản ghi chấm công của hôm nay và nhật ký liên quan.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        records = Attendance.objects.filter(date=today)
        attendance_ids = list(records.values_list('pk', flat=True))

        if not attendance_ids:
            self.stdout.write(f'Ngày {today:%d/%m/%Y}: không có bản ghi chấm công nào.')
            return

        records.delete()
        deleted_logs = AuditLog.objects.filter(
            entity_type='Attendance',
            entity_id__in=attendance_ids,
        ).delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f'Ngày {today:%d/%m/%Y}: đã xoá {len(attendance_ids)} bản ghi chấm công '
            f'và {deleted_logs} dòng nhật ký.'
        ))
