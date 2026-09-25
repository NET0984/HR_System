from django.urls import path

from . import views

app_name = 'leave'

urlpatterns = [
    path('', views.leave_list, name='list'),
    path('new/', views.leave_create, name='create'),
    path('queue/', views.leave_queue, name='queue'),
    path('<int:pk>/', views.leave_detail, name='detail'),
    path('<int:pk>/cancel/', views.leave_cancel, name='cancel'),
    path('<int:pk>/approve/', views.leave_approve, name='approve'),
    path('<int:pk>/reject/', views.leave_reject, name='reject'),
    path('<int:pk>/hr-cancel/', views.leave_hr_cancel, name='hr_cancel'),
]
