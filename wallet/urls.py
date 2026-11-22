from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.home, name='home'),
    path('transfer/', views.transfer, name='transfer'),
    path('history/', views.history, name='history'),
    path('register/', views.register, name='register'),
    path('payments/', views.payments, name='payments'),
    path('pay/<str:code>/', views.pay, name='pay'),
    path('manifest.json', views.manifest),
    path('sw.js', views.service_worker),
    path('miniapps/', login_required(TemplateView.as_view(template_name='miniapps.html')), name='miniapps'),
    path('send/', views.send, name='send'),
    path('history/export/', views.history_export, name='history_export'),
]