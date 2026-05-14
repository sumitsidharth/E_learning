from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.views import View
from django.views.generic import CreateView, TemplateView, ListView, UpdateView, DeleteView
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.db.models import Sum
from .forms import UserRegistrationForm
from .models import Notes, Question, Purchase
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from datetime import timedelta
from .models import User, Notes, Question, Purchase, Subject
from .mixins import TeacherRequiredMixin, OwnershipRequiredMixin, StudentRequiredMixin, AdminRequiredMixin
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.contrib.auth.mixins import LoginRequiredMixin
from .utils import send_verification_sms
from .models import PhoneVerificationToken

@method_decorator(ratelimit(key='ip', rate='3/m', method='POST', block=True), name='post')
class RegisterView(CreateView):
    template_name = 'accounts/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('Eduverse:verify_email_sent')

    def form_valid(self, form):
        user = form.save()
        # Send verification SMS
        send_verification_sms(user, self.request)
        
        messages.info(self.request, "A verification SMS has been sent to your phone.")
        return redirect('Eduverse:verify_phone_sent')

class VerifyPhoneView(View):
    def get(self, request, token, *args, **kwargs):
        try:
            token_obj = PhoneVerificationToken.objects.get(token=token)
            if token_obj.is_valid():
                token_obj.is_used = True
                token_obj.save()
                
                user = token_obj.user
                user.is_email_verified = True
                user.save()
                
                login(request, user)
                messages.success(request, "Phone verified successfully! Welcome to Eduverse.")
                if getattr(user, 'is_student', False):
                    return redirect('/')
                elif getattr(user, 'is_teacher', False):
                    return redirect('Eduverse:teacher_dashboard')
                elif getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
                    return redirect('Eduverse:admin_dashboard')
                return redirect('/')
            else:
                return render(request, 'accounts/verify_phone_invalid.html', {'message': 'Token is expired or already used.'})
        except PhoneVerificationToken.DoesNotExist:
            return render(request, 'accounts/verify_phone_invalid.html', {'message': 'Invalid token.'})

class VerifyPhoneSentView(TemplateView):
    template_name = 'accounts/verify_phone_sent.html'

class EmailVerifiedMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return getattr(user, 'is_email_verified', False) or getattr(user, 'is_superuser', False) or getattr(user, 'is_admin', False)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.warning(self.request, "Please verify your phone number to access this page.")
        return redirect('Eduverse:home') # Or a dedicated verify-prompt page

@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'

    def get_success_url(self):
        user = self.request.user
        if getattr(user, 'is_student', False):
            return '/'
        elif getattr(user, 'is_teacher', False):
            return reverse_lazy('Eduverse:teacher_dashboard')
        elif getattr(user, 'is_admin', False):
            return reverse_lazy('Eduverse:admin_dashboard')
        return '/'

class TeacherDashboardView(TeacherRequiredMixin, TemplateView):
    template_name = 'dashboard/teacher/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.request.user
        
        # Total notes uploaded
        context['total_notes'] = Notes.objects.filter(teacher=teacher).count()
        context['total_questions'] = Question.objects.filter(teacher=teacher).count()
        
        # Purchases stats
        purchases = Purchase.objects.filter(note__teacher=teacher)
        context['total_sales'] = purchases.count()
        context['total_earnings'] = purchases.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['recent_purchases'] = purchases.order_by('-purchased_at')[:5]
        return context

class NoteCreateView(TeacherRequiredMixin, CreateView):
    model = Notes
    template_name = 'dashboard/teacher/upload_note.html'
    fields = ['title', 'description', 'subject', 'file', 'price', 'preview_image', 'is_published']
    success_url = reverse_lazy('Eduverse:teacher_dashboard')

    def form_valid(self, form):
        form.instance.teacher = self.request.user
        messages.success(self.request, "Note uploaded successfully.")
        return super().form_valid(form)

class NoteUpdateView(TeacherRequiredMixin, OwnershipRequiredMixin, UpdateView):
    model = Notes
    template_name = 'dashboard/teacher/upload_note.html'
    fields = ['title', 'description', 'subject', 'file', 'price', 'preview_image', 'is_published']
    success_url = reverse_lazy('Eduverse:teacher_dashboard')

    def form_valid(self, form):
        messages.success(self.request, "Note updated successfully.")
        return super().form_valid(form)

class NoteDeleteView(TeacherRequiredMixin, OwnershipRequiredMixin, DeleteView):
    model = Notes
    template_name = 'dashboard/teacher/confirm_delete.html'
    success_url = reverse_lazy('Eduverse:teacher_dashboard')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Note deleted successfully.")
        return super().delete(request, *args, **kwargs)

class QuestionCreateView(TeacherRequiredMixin, CreateView):
    model = Question
    template_name = 'dashboard/teacher/upload_question.html'
    fields = ['title', 'content', 'subject', 'file', 'is_published']
    success_url = reverse_lazy('Eduverse:teacher_dashboard')

    def form_valid(self, form):
        form.instance.teacher = self.request.user
        messages.success(self.request, "Question uploaded successfully.")
        return super().form_valid(form)

class QuestionUpdateView(TeacherRequiredMixin, OwnershipRequiredMixin, UpdateView):
    model = Question
    template_name = 'dashboard/teacher/upload_question.html'
    fields = ['title', 'content', 'subject', 'file', 'is_published']
    success_url = reverse_lazy('Eduverse:teacher_dashboard')

    def form_valid(self, form):
        messages.success(self.request, "Question updated successfully.")
        return super().form_valid(form)

class QuestionDeleteView(TeacherRequiredMixin, OwnershipRequiredMixin, DeleteView):
    model = Question
    template_name = 'dashboard/teacher/confirm_delete.html'
    success_url = reverse_lazy('Eduverse:teacher_dashboard')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Question deleted successfully.")
        return super().delete(request, *args, **kwargs)

class TeacherEarningsView(TeacherRequiredMixin, ListView):
    model = Purchase
    template_name = 'dashboard/teacher/earnings.html'
    context_object_name = 'purchases'
    paginate_by = 10

    def get_queryset(self):
        return Purchase.objects.filter(note__teacher=self.request.user).order_by('-purchased_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_earnings = Purchase.objects.filter(note__teacher=self.request.user).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        context['total_earnings'] = total_earnings
        return context

from django.db.models import Q
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, View
from .models import Subject
from .mixins import StudentRequiredMixin

class NotesListView(ListView):
    model = Notes
    template_name = 'courses/notes_list.html'
    context_object_name = 'notes'
    paginate_by = 12

    def get_queryset(self):
        # Only show published notes from APPROVED teachers
        qs = Notes.objects.filter(is_published=True, teacher__teacher_profile__is_approved=True)
        q = self.request.GET.get('q')
        subjects = self.request.GET.getlist('subject')
        price_type = self.request.GET.get('price_type')
        teacher = self.request.GET.get('teacher')
        sort = self.request.GET.get('sort')

        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if subjects:
            qs = qs.filter(subject_id__in=subjects)
        if price_type == 'free':
            qs = qs.filter(price=0)
        elif price_type == 'paid':
            qs = qs.filter(price__gt=0)
        if teacher:
            qs = qs.filter(Q(teacher__username__icontains=teacher) | Q(teacher__email__icontains=teacher))

        if sort == 'price_asc':
            qs = qs.order_by('price')
        elif sort == 'price_desc':
            qs = qs.order_by('-price')
        else: # default newest
            qs = qs.order_by('-created_at')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subjects'] = Subject.objects.all()
        return context

class NoteDetailView(DetailView):
    model = Notes
    template_name = 'courses/note_detail.html'
    context_object_name = 'note'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        note = self.object
        has_purchased = False
        if self.request.user.is_authenticated:
            has_purchased = Purchase.has_purchased(self.request.user, note)
        context['has_purchased'] = has_purchased
        return context

class SecureFileDownloadView(View):
    def get(self, request, pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("You must be logged in to access this file.")
        
        note = get_object_or_404(Notes, pk=pk)
        
        if note.is_free or Purchase.has_purchased(request.user, note):
            return FileResponse(note.file.open('rb'), as_attachment=True, filename=note.file.name.split('/')[-1])
        else:
            return HttpResponseForbidden("You have not purchased this note.")

class StudentDashboardView(StudentRequiredMixin, ListView):
    model = Purchase
    template_name = 'dashboard/student/dashboard.html'
    context_object_name = 'purchases'
    
    def get_queryset(self):
        return Purchase.objects.filter(student=self.request.user).order_by('-purchased_at')

class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'dashboard/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # User Stats
        context['total_students'] = User.objects.filter(role=User.Role.STUDENT).count()
        context['total_teachers'] = User.objects.filter(role=User.Role.TEACHER).count()
        
        # Notes Stats
        context['published_notes'] = Notes.objects.filter(is_published=True).count()
        context['unpublished_notes'] = Notes.objects.filter(is_published=False).count()
        
        # Revenue
        context['total_revenue'] = Purchase.objects.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        
        # Weekly Signups
        last_week = timezone.now() - timedelta(days=7)
        context['weekly_signups'] = User.objects.filter(date_joined__gte=last_week).count()
        
        # Recent Purchases
        context['recent_purchases'] = Purchase.objects.select_related('student', 'note').order_by('-purchased_at')[:10]

        # Recent Payments for Refund Management
        from payments.models import Payment
        context['recent_payments'] = Payment.objects.select_related('student', 'note').order_by('-created_at')[:20]
        
        return context

from django.db.models import Count

class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # All subjects with note counts (filtered by published and approved)
        context['subjects'] = Subject.objects.annotate(
            note_count=Count('notes', filter=Q(notes__is_published=True, notes__teacher__teacher_profile__is_approved=True))
        )
        # 6 most recently published notes
        context['latest_notes'] = Notes.objects.filter(
            is_published=True, 
            teacher__teacher_profile__is_approved=True
        ).order_by('-created_at')[:6]
        return context
