from django.urls import path

from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.my_attendance, name='my'),
    path('check-in/', views.check_in, name='check_in'),
    path('check-out/', views.check_out, name='check_out'),
    path('manage/', views.attendance_manage, name='manage'),
    path('manage/<int:pk>/edit/', views.manage_edit, name='manage_edit'),
    path('corrections/', views.correction_queue, name='correction_queue'),
    path('corrections/new/', views.correction_create, name='correction_create'),
    path('corrections/<int:pk>/', views.correction_detail, name='correction_detail'),
    path('corrections/<int:pk>/approve/', views.correction_approve, name='correction_approve'),
    path('corrections/<int:pk>/reject/', views.correction_reject, name='correction_reject'),
]
