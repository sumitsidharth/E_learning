# pyrefly: ignore [missing-import]
from django.db import models
# pyrefly: ignore [missing-import]
from django.contrib.auth.models import AbstractUser
# pyrefly: ignore [missing-import]
from django.utils.translation import gettext_lazy as _
# pyrefly: ignore [missing-import]
from django.utils.text import slugify
# pyrefly: ignore [missing-import]
from .utils import validate_file_security

class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', _('Student')
        TEACHER = 'TEACHER', _('Teacher')
        ADMIN = 'ADMIN', _('Admin')

    role = models.CharField(max_length=50, choices=Role.choices, default=Role.STUDENT)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    is_email_verified = models.BooleanField(default=True)

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.email or self.username

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/students/', blank=True, null=True)
    date_joined_platform = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Student Profile: {self.user.email}"

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/teachers/', blank=True, null=True)
    qualification = models.CharField(max_length=255, blank=True)
    is_approved = models.BooleanField(default=False)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Teacher Profile: {self.user.email}"

class Subject(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    icon = models.ImageField(upload_to='subjects/icons/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Notes(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_notes')
    subject = models.CharField(max_length=200)
    file = models.FileField(upload_to='protected/notes/%Y/%m/%d/', validators=[validate_file_security])
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    preview_image = models.ImageField(upload_to='notes/previews/', blank=True, null=True)

    @property
    def is_free(self):
        return self.price == 0

    def clean(self):
        if self.file:
            validate_file_security(self.file)
        super().clean()

    def __str__(self):
        return self.title

class Question(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions')
    subject = models.CharField(max_length=200)
    file = models.FileField(upload_to='protected/questions/%Y/%m/%d/', blank=True, null=True, validators=[validate_file_security])
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Purchase(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    note = models.ForeignKey(Notes, on_delete=models.CASCADE, related_name='purchases')
    purchased_at = models.DateTimeField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_id = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('student', 'note')

    @classmethod
    def has_purchased(cls, student, note):
        return cls.objects.filter(student=student, note=note).exists()

    def __str__(self):
        return f"{self.student.email} bought {self.note.title}"

class PhoneVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phone_tokens')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # pyrefly: ignore [missing-import]
        from django.utils import timezone
        import datetime
        return not self.is_used and (timezone.now() - self.created_at) < datetime.timedelta(minutes=15)

    def __str__(self):
        return f"Token for {self.user.email}"
