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
    class Meta:
        model = Event
        fields = ['title', 'description', 'start_time', 'end_time', 'color', 'group', 'is_group_wide', 'specific_members']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'group': forms.Select(attrs={'class': 'form-control', 'id': 'group-select'}),
            'is_group_wide': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'specific_members': forms.SelectMultiple(attrs={'class': 'form-control', 'id': 'specific-members-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        is_superuser = kwargs.pop('is_superuser', False)
        read_only = kwargs.pop('read_only', False)
        group_members = kwargs.pop('group_members', None)
        
        super().__init__(*args, **kwargs)
        
        # Disable group selection when editing an existing group event
        if self.instance.pk and self.instance.group:
            self.fields['group'].disabled = True
            self.fields['group'].widget.attrs['class'] = 'form-control disabled'
            # Only show members of the current group
            self.fields['specific_members'].queryset = self.instance.group.members.all()
        
        if read_only:
            for field in self.fields.values():
                field.disabled = True
                if isinstance(field.widget, forms.Select) or isinstance(field.widget, forms.SelectMultiple):
                    field.widget.attrs['class'] = 'form-control'
                else:
                    field.widget.attrs['readonly'] = True
            return

        if not is_superuser:
            # Hide group-related fields for regular users
            self.fields['group'].disabled = True
            self.fields['group'].widget.attrs['class'] = 'form-control d-none'
            self.fields['is_group_wide'].disabled = True
            self.fields['is_group_wide'].widget.attrs['class'] = 'form-check-input d-none'
            self.fields['specific_members'].disabled = True
            self.fields['specific_members'].widget.attrs['class'] = 'form-control d-none'
        else:
            # For new events, superusers can see groups they admin
            if not self.instance.pk:
                self.fields['group'].queryset = CalendarGroup.objects.filter(admin=user)
            
            # Get the group from either the instance or POST data
            group_id = None
            if self.instance and self.instance.group:
                group_id = self.instance.group.id
            elif self.data.get('group'):
                group_id = self.data.get('group')

            # Set specific_members queryset based on group
            if group_id:
                try:
                    group = CalendarGroup.objects.get(id=group_id)
                    self.fields['specific_members'].queryset = group.members.all()
                except CalendarGroup.DoesNotExist:
                    self.fields['specific_members'].queryset = User.objects.none()
            else:
                self.fields['specific_members'].queryset = User.objects.none()
                
    def clean(self):
        cleaned_data = super().clean()
        group = cleaned_data.get('group')
        is_group_wide = cleaned_data.get('is_group_wide')
        specific_members = cleaned_data.get('specific_members')

        if group and not is_group_wide:
            if not specific_members:
                raise forms.ValidationError("Please select specific members or mark as group-wide")
            
            # Validate that selected members belong to the group
            valid_members = group.members.all()
            invalid_members = [member for member in specific_members if member not in valid_members]
            if invalid_members:
                raise forms.ValidationError(f"Invalid member selection: {', '.join(str(m) for m in invalid_members)}")

        return cleaned_data

class GroupForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = CalendarGroup
        fields = ['name', 'description', 'members']