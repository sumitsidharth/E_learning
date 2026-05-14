from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout

class RoleRequiredMixin(UserPassesTestMixin):
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        if not self.request.user.is_active:
            logout(self.request)
            messages.error(self.request, "Your account is inactive. Please contact support.")
            return redirect('Eduverse:home')
            
        is_privileged = getattr(self.request.user, 'is_admin', False) or getattr(self.request.user, 'is_superuser', False)

        if not self.request.user.is_email_verified and not is_privileged:
            messages.warning(self.request, "Please verify your email to access this page.")
            return redirect('Eduverse:home')
            
        if is_privileged:
            return redirect('Eduverse:admin_dashboard')
        elif getattr(self.request.user, 'is_teacher', False):
            return redirect('Eduverse:teacher_dashboard')
        elif getattr(self.request.user, 'is_student', False):
            return redirect('Eduverse:student_dashboard')
            
        return redirect('Eduverse:home')

class TeacherRequiredMixin(RoleRequiredMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_active and user.is_teacher and user.is_email_verified

class OwnershipRequiredMixin:
    """
    Filters the queryset to only include objects owned by the requesting user.
    Assumes the model has a 'teacher' foreign key to the user.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(teacher=self.request.user)

class StudentRequiredMixin(RoleRequiredMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_active and user.is_student and user.is_email_verified

class AdminRequiredMixin(RoleRequiredMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_active and (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False))
