from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import EventDeleteView

urlpatterns = [
    path('', views.home_view, name='home'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='calendar_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('groups/', views.group_list, name='group-list'),
    path('groups/create/', views.group_create, name='group-create'),
    path('event/new/', views.EventCreateView.as_view(), name='event-create'),
    path('event/<int:pk>/update/', views.EventUpdateView.as_view(), name='event_update'),
    path('event/<int:pk>/delete/', EventDeleteView.as_view(), name='event_delete'),
    path('api/group-members/<int:group_id>/', views.get_group_members, name='group-members'),
    path('group/<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group-delete'),
    path('api/generate-store-schedule/', views.generate_store_schedule, name='generate_store_schedule'),
]