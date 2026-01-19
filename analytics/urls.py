from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_csv, name='upload_csv'),
    path('export/', views.export_report, name='export_report'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('delete/', views.delete_data, name='delete_data'),
]