from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail
from django.conf import settings
from .models import User, StudentProfile, TeacherProfile, Subject, Notes, Question, Purchase

@admin.action(description="Approve selected teachers")
def approve_teachers(modeladmin, request, queryset):
    for user in queryset.filter(role=User.Role.TEACHER):
        # Update profile
        profile = user.teacher_profile
        if not profile.is_approved:
            profile.is_approved = True
            profile.save()
            
            # Send notification email
            send_mail(
                subject='Welcome to Eduverse — Teacher Account Approved!',
                message=f'Hello {user.username},\n\nYour teacher profile on Eduverse has been approved! You can now upload and publish notes and questions.\n\nHappy teaching!',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

class EduverseUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'date_joined', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff')
    actions = [approve_teachers]
    
    # Ensure role is editable in the admin
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role',)}),
    )

# Unregister original User registration if exists
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, EduverseUserAdmin)
admin.site.register(StudentProfile)
admin.site.register(TeacherProfile)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)

@admin.register(Notes)
class NotesAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'subject', 'price', 'is_published', 'created_at')
    list_filter = ('is_published', 'subject', 'teacher')
    search_fields = ('title', 'description')
    actions = ['make_published', 'make_unpublished']

    @admin.action(description="Mark selected notes as published")
    def make_published(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="Mark selected notes as unpublished")
    def make_unpublished(self, request, queryset):
        queryset.update(is_published=False)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'subject', 'is_published', 'created_at')
    list_filter = ('is_published', 'subject', 'teacher')
    search_fields = ('title', 'content')

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('student', 'note', 'amount_paid', 'purchased_at')
    list_filter = ('purchased_at',)
    search_fields = ('student__email', 'note__title')
