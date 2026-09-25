from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.monthly_report, name='monthly'),
    path('export/pdf/', views.monthly_report_pdf, name='export_pdf'),
    path('export/excel/', views.monthly_report_excel, name='export_excel'),
]
