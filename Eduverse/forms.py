from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=[(User.Role.STUDENT, 'Student'), (User.Role.TEACHER, 'Teacher')])
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=15, required=True, help_text="e.g. +1234567890")
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'phone_number', 'username', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = False

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with that email already exists.')
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if User.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError('A user with that phone number already exists.')
        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone_number = self.cleaned_data.get('phone_number')
        user.role = self.cleaned_data['role']
        if not user.username:
            user.username = user.email
        if commit:
            user.save()
        return user
