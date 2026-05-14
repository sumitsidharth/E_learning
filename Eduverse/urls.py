from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'Eduverse'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('accounts/register/', views.RegisterView.as_view(), name='register'),
    path('accounts/login/', views.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('accounts/verify-phone/<str:token>/', views.VerifyPhoneView.as_view(), name='verify_phone'),
    path('accounts/verify-phone-sent/', views.VerifyPhoneSentView.as_view(), name='verify_phone_sent'),

    # Password Reset
    path('accounts/password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        success_url='/accounts/password-reset/done/'
    ), name='password_reset'),
    path('accounts/password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('accounts/password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('accounts/password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

    # Teacher endpoints
    path('teacher/dashboard/', views.TeacherDashboardView.as_view(), name='teacher_dashboard'),
    path('teacher/notes/add/', views.NoteCreateView.as_view(), name='note_create'),
    path('teacher/notes/<int:pk>/edit/', views.NoteUpdateView.as_view(), name='note_update'),
    path('teacher/notes/<int:pk>/delete/', views.NoteDeleteView.as_view(), name='note_delete'),
    path('teacher/questions/add/', views.QuestionCreateView.as_view(), name='question_create'),
    path('teacher/questions/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='question_update'),
    path('teacher/questions/<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='question_delete'),
    path('teacher/earnings/', views.TeacherEarningsView.as_view(), name='teacher_earnings'),

    # Student endpoints
    path('notes/', views.NotesListView.as_view(), name='notes_list'),
    path('notes/<int:pk>/', views.NoteDetailView.as_view(), name='note_detail'),
    path('notes/<int:pk>/download/', views.SecureFileDownloadView.as_view(), name='note_download'),
    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    # Admin endpoints
    path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
]
