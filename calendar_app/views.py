from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q  # Add this import
from .models import Event, CalendarGroup
from .forms import EventForm, UserRegistrationForm, GroupForm
from datetime import datetime, timedelta
import json
from django.http import JsonResponse

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
    # Get events created by the user
    user_events = Event.objects.filter(user=request.user)
    
    # Get events where user is specifically selected
    specific_events = Event.objects.filter(specific_members=request.user)
    
    # Get group-wide events for groups the user is a member of
    group_events = Event.objects.filter(
        group__members=request.user,
        is_group_wide=True
    )
    
    # For superusers, get all events they created
    if request.user.is_superuser:
        admin_events = Event.objects.filter(user=request.user)
    else:
        admin_events = Event.objects.none()
    
    # Combine all events
    events = user_events | group_events | specific_events | admin_events
    
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
            'group': event.group.name if event.group else 'Personal',
            'isGroupWide': event.is_group_wide if event.group else None
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
        kwargs['is_superuser'] = self.request.user.is_superuser
        return kwargs

    def form_valid(self, form):
        event = form.save(commit=False)
        event.user = self.request.user
        
        if not self.request.user.is_superuser:
            event.group = None
            event.is_group_wide = False
            event.save()
            return super().form_valid(form)
            
        # Handle superuser events
        event.save()
        
        if form.cleaned_data['group']:
            if form.cleaned_data['is_group_wide']:
                event.specific_members.clear()
            else:
                selected_members = form.cleaned_data['specific_members']
                if selected_members:
                    event.specific_members.set(selected_members)
                else:
                    event.specific_members.clear()
        
        return super().form_valid(form)

    def form_invalid(self, form):
        # Add debugging for form errors
        print(f"Form errors: {form.errors}")
        return super().form_invalid(form)

class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar_app/event_form.html'
    success_url = reverse_lazy('calendar')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['is_superuser'] = self.request.user.is_superuser
        # Add read_only flag if user is not the creator and not superuser
        kwargs['read_only'] = not self.request.user.is_superuser and self.get_object().user != self.request.user
        return kwargs

    def get_queryset(self):
        # Allow viewing for assigned users, editing for creators and superusers
        base_query = Q(user=self.request.user)  # Own events
        if not self.request.user.is_superuser:
            base_query |= (
                Q(specific_members=self.request.user) |  # Specifically assigned
                Q(group__members=self.request.user, is_group_wide=True)  # Group-wide events
            )
        else:
            base_query |= Q(user=self.request.user)  # Admin events
        return Event.objects.filter(base_query).distinct()

    def test_func(self):
        event = self.get_object()
        # Allow view access for assigned users
        can_view = (
            self.request.user.is_superuser or
            event.user == self.request.user or
            self.request.user in event.specific_members.all() or
            (event.is_group_wide and event.group and self.request.user in event.group.members.all())
        )
        return can_view

class EventDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Event
    success_url = reverse_lazy('calendar')
    template_name = 'calendar_app/event_confirm_delete.html'

    def get_queryset(self):
        # Only allow deletion if user is the creator
        return Event.objects.filter(user=self.request.user)  # changed from creator to user

    def test_func(self):
        event = self.get_object()
        return self.request.user == event.user or (
            event.group and 
            self.request.user.is_superuser and 
            event.group.admin == self.request.user
        )

@login_required
def get_group_members(request, group_id):
    """API endpoint to get members of a specific group"""
    try:
        group = CalendarGroup.objects.get(id=group_id)
        members = group.members.all()
        members_data = [{'id': member.id, 'username': member.username} for member in members]
        return JsonResponse(members_data, safe=False)
    except CalendarGroup.DoesNotExist:
        return JsonResponse([], safe=False)

class GroupDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = CalendarGroup
    success_url = reverse_lazy('group-list')
    template_name = 'calendar_app/group_confirm_delete.html'

    def test_func(self):
        group = self.get_object()
        return self.request.user.is_superuser and group.admin == self.request.user