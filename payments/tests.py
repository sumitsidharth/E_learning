from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from Eduverse.models import Subject, Notes, Purchase
from .models import Payment, TransactionLog
from decimal import Decimal

User = get_user_model()

class TestPaymentSystem(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='s', email='s@test.com', password='password', role=User.Role.STUDENT, is_email_verified=True)
        self.teacher = User.objects.create_user(username='t', email='t@test.com', password='password', role=User.Role.TEACHER, is_email_verified=True)
        self.teacher.teacher_profile.is_approved = True
        self.teacher.teacher_profile.save()
        
        self.subject = Subject.objects.create(name='CompSci')
        
        # Free Note
        self.free_note = Notes.objects.create(
            title='Intro to C', teacher=self.teacher, subject=self.subject,
            file=SimpleUploadedFile('c.pdf', b'test'), price=Decimal('0.00'), is_published=True
        )
        
        # Paid Note
        self.paid_note = Notes.objects.create(
            title='Advanced Python', teacher=self.teacher, subject=self.subject,
            file=SimpleUploadedFile('py.pdf', b'test'), price=Decimal('100.00'), is_published=True
        )
        
        self.client = Client()
        self.client.login(username='s', password='password')

    def test_checkout_free_note_fails(self):
        url = reverse('payments:create_checkout_session')
        response = self.client.post(url, {'note_id': self.free_note.id})
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'error': 'Note is free, checkout unnecessary'})

    def test_checkout_paid_note_success(self):
        # We need to mock stripe to prevent actual API calls, but just testing if it handles the request and calls the try block.
        # It's better to mock stripe.checkout.Session.create
        from unittest.mock import patch
        
        url = reverse('payments:create_checkout_session')
        
        with patch('stripe.checkout.Session.create') as mock_create:
            mock_create.return_value.id = 'cs_test_mock'
            mock_create.return_value.url = 'https://checkout.stripe.com/pay/mock'
            
            response = self.client.post(url, {'note_id': self.paid_note.id})
            
            self.assertEqual(response.status_code, 200)
            self.assertTrue(Payment.objects.filter(stripe_session_id='cs_test_mock').exists())
            payment = Payment.objects.get(stripe_session_id='cs_test_mock')
            self.assertEqual(payment.status, 'pending')
            self.assertEqual(payment.currency, 'inr')

    def test_purchase_history_view_access(self):
        url = reverse('payments:purchase_history')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/purchase_history.html')

    def test_payment_success_verification(self):
        from unittest.mock import patch
        url = reverse('payments:success')
        
        # Create a pending payment
        payment = Payment.objects.create(
            student=self.student, note=self.paid_note,
            stripe_session_id='cs_test_verify', amount=self.paid_note.price, currency='inr', status='pending'
        )
        
        with patch('stripe.checkout.Session.retrieve') as mock_retrieve:
            mock_retrieve.return_value.payment_status = 'unpaid'
            
            # Access success page with unpaid payment
            response = self.client.get(url, {'session_id': 'cs_test_verify'})
            self.assertRedirects(response, reverse('payments:cancel'))
            
            # Mark payment as completed (simulating webhook)
            payment.status = 'completed'
            payment.save()
            
            # Access success page with completed payment
            response = self.client.get(url, {'session_id': 'cs_test_verify'})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Payment Successful')
