"""URL configuration for config project."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('employees/', include('employees.urls')),
    path('attendance/', include('attendance.urls')),
    path('audit/', include('audit.urls')),
    path('leave/', include('leave.urls')),
    path('reports/', include('reports.urls')),
]