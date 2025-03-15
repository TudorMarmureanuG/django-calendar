from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Event, CalendarGroup

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class EventForm(forms.ModelForm):
    is_group_wide = forms.BooleanField(
        required=False, 
        initial=True, 
        label="For all group members",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Event
        fields = ['title', 'description', 'start_time', 'end_time', 'color', 'group', 'is_group_wide', 'specific_members']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-control', 'id': 'group-select'}),
            'specific_members': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'id': 'specific-members-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.is_superuser:
            self.fields['group'].queryset = CalendarGroup.objects.filter(admin=user)
            
            # Initialize with all possible users, will be filtered by JavaScript
            all_users = User.objects.exclude(id=user.id)
            self.fields['specific_members'].queryset = all_users

            # If we have initial group data, filter members
            if self.data.get('group'):
                try:
                    group = CalendarGroup.objects.get(id=self.data['group'])
                    self.fields['specific_members'].queryset = group.members.all()
                except (CalendarGroup.DoesNotExist, ValueError):
                    pass
        else:
            self.fields['group'].widget = forms.HiddenInput()
            self.fields['is_group_wide'].widget = forms.HiddenInput()
            self.fields['specific_members'].widget = forms.HiddenInput()

class GroupForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = CalendarGroup
        fields = ['name', 'description', 'members']