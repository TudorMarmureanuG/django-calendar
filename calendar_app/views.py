from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.models import User, Group  # Add Group to the import
from .models import Event, CalendarGroup
from .forms import EventForm, UserRegistrationForm, GroupForm
from datetime import datetime, timedelta
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from icalendar import Calendar, Event as CalendarEvent
from django.http import HttpResponse

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
        # Get specific members for this event if it's not group-wide
        specific_members = []
        if event.group and not event.is_group_wide:
            specific_members = [
                {
                    'id': member.id,
                    'username': member.username
                } 
                for member in event.specific_members.all()
            ]

        events_list.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            'end': event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            'color': event.color,
            'description': event.description,
            'editable': request.user.is_superuser or event.user == request.user,
            'group': event.group.name if event.group else 'Personal',
            'isGroupWide': event.is_group_wide if event.group else None,
            'specificMembers': specific_members if not event.is_group_wide else []
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
        
        event = self.get_object()
        # Add read_only flag if user is not the creator and not superuser
        kwargs['read_only'] = not self.request.user.is_superuser and event.user != self.request.user
        
        # Filter specific_members queryset to only show group members
        if event.group:
            kwargs['group_members'] = event.group.members.all()
        
        return kwargs

    def get_queryset(self):
        # Allow viewing for assigned users, editing for creators and superusers
        base_query = Q(user=self.request.user)  # Own events
        # Include events where user is specifically assigned or part of group-wide events
        base_query |= (
            Q(specific_members=self.request.user) |  # Specifically assigned
            Q(group__members=self.request.user, is_group_wide=True)  # Group-wide events
        )
        return Event.objects.filter(base_query).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object:
            if not self.object.is_group_wide and self.object.group:
                # Filter specific members to only show those from the event's group
                context['specific_members'] = self.object.specific_members.filter(
                    calendar_groups=self.object.group
                ).distinct()
                context['group_members'] = self.object.group.members.all()
            elif self.object.group:
                context['group_members'] = self.object.group.members.all()
        return context

    def test_func(self):
        event = self.get_object()
        # Allow access if user is:
        # 1. The creator
        # 2. A superuser
        # 3. Specifically assigned to the event
        # 4. Part of the group for group-wide events
        return (
            self.request.user == event.user or
            self.request.user.is_superuser or
            (event.specific_members.filter(id=self.request.user.id).exists()) or
            (event.is_group_wide and event.group and event.group.members.filter(id=self.request.user.id).exists())
        )

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

def is_weekday(date):
    return date.weekday() < 5

def calculate_start_date(launch_date, workday_gap):
    days_counted = 0
    current_date = launch_date
    
    while days_counted < workday_gap:
        current_date -= timedelta(days=1)
        if is_weekday(current_date):
            days_counted += 1
    
    return current_date

def adjust_for_weekend(current_date):
    if current_date.weekday() == 5:  # Saturday
        return current_date + timedelta(days=2)
    elif current_date.weekday() == 6:  # Sunday
        return current_date + timedelta(days=1)
    return current_date

@require_http_methods(["POST"])
@user_passes_test(lambda u: u.is_superuser)
def generate_store_schedule(request):
    try:
        data = json.loads(request.body)
        store_name = data['store_name']
        opening_date_str = data['opening_date']
        if 'T' in opening_date_str:
            opening_date_str = opening_date_str.split('T')[0]
        opening_date = datetime.strptime(opening_date_str, '%Y-%m-%d')
        group_id = data['group_id']
        include_all_members = data['include_all_members']
        selected_members = data.get('selected_members', [])
        
        # Remove the default color and use the one from the form
        color = data.get('color')  # This will get the color selected in the form

        # Get group members
        if include_all_members:
            group_members = User.objects.filter(groups=group_id)
        else:
            group_members = User.objects.filter(id__in=selected_members)

        # Generate events
        events = []
        task_schedule = [
            ("Instalare (fizica)calculatoare + pos retur", ["Katrein sau Omega"], 9, 2),
            ("Configurare initiala", ["Suport IT"], 8, 2),
            ("Configurare LSCentral POS", ["Lavinia Avram"], 7, 3),
            ("Teste utilizator aplicatie POS", ["Magazin"], 4, 2),
            ("Instalare ECR", ["Parteneri SIBS (Ropeco)"], 3, 1),
            ("Deschidere magazin", ["Dedeman"], 0, 1)
        ]

        for task_name, default_assignees, workday_gap, duration_days in task_schedule:
            start_date = calculate_start_date(opening_date, workday_gap)
            current_date = start_date
            
            for _ in range(duration_days):
                current_date = adjust_for_weekend(current_date)
                assignees = group_members if not include_all_members else default_assignees
                
                for assignee in assignees:
                    event = Event.objects.create(
                        title=f"{store_name} - {task_name}",
                        start_time=current_date,
                        end_time=current_date + timedelta(days=1),
                        group_id=group_id,
                        is_group_wide=include_all_members,
                        user=request.user,
                        color=color  # Use the color from the form
                    )
                    if not include_all_members:
                        event.specific_members.add(assignee)
                    events.append(event)
                
                current_date += timedelta(days=1)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def search_users(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    query = request.GET.get('q', '').strip()
    print(f"Searching for users with query: {query}")  # Debug line
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    try:
        users = User.objects.filter(
            username__icontains=query
        ).exclude(
            id=request.user.id
        ).values('id', 'username')[:10]
        
        users_data = list(users)
        print(f"Found users: {users_data}")  # Debug line
        
        return JsonResponse({'users': users_data})
    except Exception as e:
        print(f"Error in search_users: {str(e)}")  # Debug line
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def store_opening_create(request):
    if not request.user.is_superuser:
        return redirect('calendar')
    
    # Filter groups to show only those where the current user is admin
    groups = CalendarGroup.objects.filter(admin=request.user)
    return render(request, 'calendar_app/store_opening_form.html', {
        'groups': groups
    })

@login_required
def export_calendar(request):
    # Create calendar
    cal = Calendar()
    cal.add('prodid', '-//Your Calendar Application//example.com//')
    cal.add('version', '2.0')

    # Get events based on user type and permissions (similar to calendar_view)
    user_events = Event.objects.filter(user=request.user)
    specific_events = Event.objects.filter(specific_members=request.user)
    group_events = Event.objects.filter(
        group__members=request.user,
        is_group_wide=True
    )
    
    if request.user.is_superuser:
        admin_events = Event.objects.filter(user=request.user)
    else:
        admin_events = Event.objects.none()
    
    # Combine all events
    events = user_events | specific_events | group_events | admin_events
    events = events.distinct()

    # Add events to calendar
    for event in events:
        cal_event = CalendarEvent()
        cal_event.add('summary', event.title)
        cal_event.add('dtstart', event.start_time)
        cal_event.add('dtend', event.end_time)
        cal_event.add('description', event.description or '')
        cal_event.add('uid', str(event.id) + "@yourcalendar.com")
        
        if event.group:
            cal_event.add('categories', event.group.name)
        
        cal.add_component(cal_event)

    # Create response
    response = HttpResponse(cal.to_ical(), content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename="calendar.ics"'
    return response
