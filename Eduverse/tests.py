import os
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.core import mail
from decimal import Decimal
from .models import User, Subject, Notes, Purchase, TeacherProfile, StudentProfile

User = get_user_model()

class TestUserAuth(TestCase):
    def setUp(self):
        self.client = Client()

    def test_student_registration(self):
        url = reverse('Eduverse:register')
        data = {
            'username': 'teststudent',
            'email': 'student@test.com',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'role': User.Role.STUDENT
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('Eduverse:verify_email_sent'))
        self.assertTrue(User.objects.filter(username='teststudent').exists())
        user = User.objects.get(username='teststudent')
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_teacher_registration(self):
        url = reverse('Eduverse:register')
        data = {
            'username': 'testteacher',
            'email': 'teacher@test.com',
            'password1': 'testpassword123',
            'password2': 'testpassword123',
            'role': User.Role.TEACHER
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('Eduverse:verify_email_sent'))
        self.assertTrue(User.objects.filter(username='testteacher').exists())
        user = User.objects.get(username='testteacher')
        self.assertEqual(user.role, User.Role.TEACHER)
        self.assertFalse(user.is_email_verified)
        # Profile should be created but NOT approved
        self.assertFalse(user.teacher_profile.is_approved)

class TestContentManagement(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username='teacher', email='teacher@test.com', password='password', 
            role=User.Role.TEACHER, is_email_verified=True
        )
        self.teacher_profile = self.teacher_user.teacher_profile
        self.subject = Subject.objects.create(name='Math', description='Math notes')
        self.client = Client()
        self.client.login(username='teacher', password='password')

    def test_note_upload_validation(self):
        # Test valid PDF upload
        url = reverse('Eduverse:note_create')
        pdf_content = b'%PDF-1.4 test'
        uploaded_file = SimpleUploadedFile('test.pdf', pdf_content, content_type='application/pdf')
        data = {
            'title': 'Test Note',
            'description': 'Description',
            'subject': self.subject.id,
            'file': uploaded_file,
            'price': '9.99',
            'is_published': True
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Notes.objects.filter(title='Test Note').exists())

    def test_note_approval_visibility(self):
        # Teacher is NOT approved yet
        note = Notes.objects.create(
            title='Invisible Note', teacher=self.teacher_user, subject=self.subject,
            file=SimpleUploadedFile('test.pdf', b'test'), price=0, is_published=True
        )
        url = reverse('Eduverse:notes_list')
        response = self.client.get(url)
        self.assertNotContains(response, 'Invisible Note')

        # Approve teacher
        self.teacher_profile.is_approved = True
        self.teacher_profile.save()
        response = self.client.get(url)
        self.assertContains(response, 'Invisible Note')

class TestStudentBrowsing(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='t', role=User.Role.TEACHER, is_email_verified=True)
        self.teacher.teacher_profile.is_approved = True
        self.teacher.teacher_profile.save()
        self.subject = Subject.objects.create(name='Physics', description='Physics')
        self.note = Notes.objects.create(
            title='Physics 101', teacher=self.teacher, subject=self.subject,
            file=SimpleUploadedFile('test.pdf', b'test'), price=10.00, is_published=True
        )
        self.client = Client()

    def test_homepage_metrics(self):
        url = reverse('Eduverse:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PHYSICS')
        self.assertContains(response, '1 NOTES')

class TestPurchaseFulfillment(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='s', role=User.Role.STUDENT, is_email_verified=True)
        self.teacher = User.objects.create_user(username='t', role=User.Role.TEACHER, is_email_verified=True)
        self.teacher.teacher_profile.is_approved = True
        self.teacher.teacher_profile.save()
        self.subject = Subject.objects.create(name='Bio')
        self.note = Notes.objects.create(
            title='Bio 101', teacher=self.teacher, subject=self.subject,
            file=SimpleUploadedFile('test.pdf', b'test'), price=Decimal('15.00'), is_published=True
        )
        self.client = Client()

    def test_webhook_fulfillment(self):
        # Mocking Stripe Webhook
        url = reverse('payments:webhook')
        # This test requires mocking Stripe.signature.verify
        # For simplicity, we'll verify the Purchase logic directly or use a mock
        from unittest.mock import patch
        with patch('stripe.Webhook.construct_event') as mock_event:
            mock_event.return_value = {
                'type': 'checkout.session.completed',
                'data': {
                    'object': {
                        'id': 'cs_test_123',
                        'metadata': {
                            'note_id': str(self.note.id),
                            'student_id': str(self.student.id)
                        },
                        'amount_total': 1500 # in cents
                    }
                }
            }
            # Mock CSRF and Stripe Signature
            response = self.client.post(url, HTTP_STRIPE_SIGNATURE='fake_sig')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(Purchase.objects.filter(student=self.student, note=self.note).exists())
            self.teacher.teacher_profile.refresh_from_db()
            self.assertEqual(self.teacher.teacher_profile.total_earnings, Decimal('15.00'))

class TestAdminPanel(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin', password='password', is_email_verified=True)
        self.admin.role = User.Role.ADMIN
        self.admin.save()
        self.client = Client()

    def test_admin_dashboard_access(self):
        url = reverse('Eduverse:admin_dashboard')
        # Non-logged in
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Logged in as admin
        self.client.login(username='admin', password='password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PLATFORM ANALYTICS')
