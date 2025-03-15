from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Event, CalendarGroup
from .forms import EventForm, UserRegistrationForm, GroupForm
from datetime import datetime, timedelta
import json

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'calendar_app/register.html', {'form': form})

def is_superuser(user):
    return user.is_superuser

@user_passes_test(is_superuser)
def group_list(request):
    groups = CalendarGroup.objects.filter(admin=request.user)
    return render(request, 'calendar_app/group_list.html', {'groups': groups})

@user_passes_test(is_superuser)
def group_create(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.admin = request.user
            group.save()
            form.save_m2m()  # Save many-to-many relationships
            return redirect('group-list')
    else:
        form = GroupForm()
    return render(request, 'calendar_app/group_form.html', {'form': form})

@login_required
def calendar_view(request):
    # Get personal events
    user_events = Event.objects.filter(user=request.user)
    
    # Get group events where user is a member
    group_events = Event.objects.filter(group__members=request.user)
    
    # Get events where user is the group admin
    admin_events = Event.objects.filter(group__admin=request.user) if request.user.is_superuser else Event.objects.none()
    
    # Combine all events
    events = user_events | group_events | admin_events
    
    events_list = []
    for event in events.distinct():
        events_list.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            'end': event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            'color': event.color,
            'description': event.description,
            'editable': request.user.is_superuser or event.user == request.user,
            'group': event.group.name if event.group else 'Personal'
        })
    
    return render(request, 'calendar_app/calendar.html', {
        'events': json.dumps(events_list),
    })

def home_view(request):
    if request.user.is_authenticated:
        return redirect('calendar')
    return render(request, 'calendar_app/home.html')

class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar_app/event_form.html'
    success_url = reverse_lazy('calendar')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar_app/event_form.html'
    success_url = reverse_lazy('calendar')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        event = self.get_object()
        return self.request.user == event.user or (
            event.group and 
            self.request.user.is_superuser and 
            event.group.admin == self.request.user
        )

class EventDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Event
    success_url = reverse_lazy('calendar')
    template_name = 'calendar_app/event_confirm_delete.html'

    def test_func(self):
        event = self.get_object()
        return self.request.user == event.user or (
            event.group and 
            self.request.user.is_superuser and 
            event.group.admin == self.request.user
        )