from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Event
from .forms import EventForm, UserRegistrationForm
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

@login_required
def calendar_view(request):
    events = Event.objects.filter(user=request.user)
    events_list = []
    for event in events:
        events_list.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            'end': event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            'color': event.color
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

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar_app/event_form.html'
    success_url = reverse_lazy('calendar')

class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    success_url = reverse_lazy('calendar')
    template_name = 'calendar_app/event_confirm_delete.html'