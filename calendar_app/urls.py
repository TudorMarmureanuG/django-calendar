from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),  # This should be first in the list
    path('calendar/', views.calendar_view, name='calendar'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='calendar_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),  # Add next_page parameter
    path('event/new/', views.EventCreateView.as_view(), name='event-create'),
    path('event/<int:pk>/update/', views.EventUpdateView.as_view(), name='event-update'),
    path('event/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event-delete'),
]