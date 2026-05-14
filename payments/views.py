import stripe
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView, ListView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.contrib import messages
from Eduverse.models import Notes, Purchase
from Eduverse.mixins import StudentRequiredMixin, AdminRequiredMixin
from .models import Payment, TransactionLog, RefundTracking
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

class CreateCheckoutSessionView(LoginRequiredMixin, StudentRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        note_id = request.POST.get('note_id')
        if not note_id:
            return JsonResponse({'error': 'note_id is required'}, status=400)
            
        note = get_object_or_404(Notes, id=note_id)
        
        # Check if note is free
        if note.is_free:
            return JsonResponse({'error': 'Note is free, checkout unnecessary'}, status=400)
            
        # Check if already purchased
        if Purchase.has_purchased(request.user, note):
            return JsonResponse({'error': 'Already purchased'}, status=400)
            
        domain_url = request.build_absolute_uri('/')[:-1]
        
        try:
            if not settings.STRIPE_SECRET_KEY:
                import uuid
                mock_session_id = f"cs_test_mock_{uuid.uuid4().hex[:12]}"
                mock_success_url = domain_url + f'/payments/success/?session_id={mock_session_id}'
                
                # Mock pending payment and instantly complete
                payment = Payment.objects.create(
                    student=request.user,
                    note=note,
                    stripe_session_id=mock_session_id,
                    amount=note.price,
                    currency='inr',
                    status='completed'
                )
                
                # Mock webhook action
                if not Purchase.objects.filter(student=request.user, note=note).exists():
                    Purchase.objects.create(
                        student=request.user,
                        note=note,
                        amount_paid=note.price,
                        stripe_payment_id=mock_session_id
                    )
                    teacher_profile = note.teacher.teacher_profile
                    teacher_profile.total_earnings += note.price
                    teacher_profile.save()

                return JsonResponse({'sessionId': mock_session_id, 'url': mock_success_url})

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'inr',
                            'unit_amount': int(note.price * 100),
                            'product_data': {
                                'name': note.title,
                                'description': f"Note taught by ID: {note.teacher.id}",
                            },
                        },
                        'quantity': 1,
                    }
                ],
                mode='payment',
                client_reference_id=str(request.user.id),
                success_url=domain_url + f'/payments/success/?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=domain_url + f'/payments/cancel/?note_id={note.id}',
                metadata={
                    'note_id': note.id,
                    'student_id': request.user.id
                }
            )
            
            # Create pending Payment record
            Payment.objects.create(
                student=request.user,
                note=note,
                stripe_session_id=checkout_session.id,
                amount=note.price,
                currency='inr',
                status='pending'
            )
            
            return JsonResponse({'sessionId': checkout_session.id, 'url': checkout_session.url})
        except Exception as e:
            logger.error(f"Checkout Session Error: {e}")
            return JsonResponse({'error': str(e)}, status=500)



@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        event = None

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            # Invalid payload
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return HttpResponse(status=400)

        # Handle the events
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            note_id = session['metadata'].get('note_id')
            student_id = session['metadata'].get('student_id')
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                note = Notes.objects.get(id=note_id)
                student = User.objects.get(id=student_id)
                payment = Payment.objects.get(stripe_session_id=session['id'])
            except (Notes.DoesNotExist, User.DoesNotExist, Payment.DoesNotExist):
                return HttpResponse(status=400)
            
            # Update Payment status
            payment.status = 'completed'
            payment.stripe_payment_intent = session.get('payment_intent', '')
            payment.save()

            # Record transaction log
            TransactionLog.objects.create(
                payment=payment,
                event_type='checkout.session.completed',
                stripe_event_id=event['id'],
                event_data=session
            )
            
            # Idempotency check: see if purchase already exists
            if not Purchase.objects.filter(student=student, note=note).exists():
                # Create Purchase
                Purchase.objects.create(
                    student=student,
                    note=note,
                    amount_paid=note.price,
                    stripe_payment_id=session['id']
                )
                
                # Update Teacher Profile earnings
                teacher_profile = note.teacher.teacher_profile
                teacher_profile.total_earnings += note.price
                teacher_profile.save()

        elif event['type'] == 'charge.succeeded':
            charge = event['data']['object']
            payment_intent_id = charge.get('payment_intent')
            if payment_intent_id:
                try:
                    payment = Payment.objects.get(stripe_payment_intent=payment_intent_id)
                    payment.payment_method = charge.get('payment_method_details', {}).get('type', '')
                    payment.receipt_url = charge.get('receipt_url', '')
                    payment.save()

                    TransactionLog.objects.create(
                        payment=payment,
                        event_type='charge.succeeded',
                        stripe_event_id=event['id'],
                        event_data=charge
                    )
                except Payment.DoesNotExist:
                    pass

        elif event['type'] == 'payment_intent.payment_failed':
            intent = event['data']['object']
            try:
                payment = Payment.objects.get(stripe_payment_intent=intent['id'])
                payment.status = 'failed'
                payment.failure_reason = intent.get('last_payment_error', {}).get('message', 'Unknown failure')
                payment.save()

                TransactionLog.objects.create(
                    payment=payment,
                    event_type='payment_intent.payment_failed',
                    stripe_event_id=event['id'],
                    event_data=intent
                )
            except Payment.DoesNotExist:
                pass

        elif event['type'] == 'charge.refunded':
            charge = event['data']['object']
            payment_intent_id = charge.get('payment_intent')
            if payment_intent_id:
                try:
                    payment = Payment.objects.get(stripe_payment_intent=payment_intent_id)
                    payment.status = 'refunded'
                    payment.save()
                    
                    amount_refunded = charge.get('amount_refunded', 0) / 100.0
                    RefundTracking.objects.create(
                        payment=payment,
                        stripe_refund_id=charge.get('refunds', {}).get('data', [{}])[0].get('id', ''),
                        amount=amount_refunded,
                        reason=charge.get('refunds', {}).get('data', [{}])[0].get('reason', ''),
                        status='completed'
                    )

                    TransactionLog.objects.create(
                        payment=payment,
                        event_type='charge.refunded',
                        stripe_event_id=event['id'],
                        event_data=charge
                    )

                    # Revoke access (delete Purchase)
                    purchase = Purchase.objects.filter(student=payment.student, note=payment.note).first()
                    if purchase:
                        purchase.delete()
                        
                        # Deduct from teacher profile
                        teacher_profile = payment.note.teacher.teacher_profile
                        teacher_profile.total_earnings -= payment.amount
                        teacher_profile.save()

                except Payment.DoesNotExist:
                    pass

        return HttpResponse(status=200)

class InitiateRefundView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, payment_id, *args, **kwargs):
        payment = get_object_or_404(Payment, id=payment_id)
        if payment.status != 'completed':
            messages.error(request, "Only completed payments can be refunded.")
            return redirect('Eduverse:admin_dashboard')

        if not settings.STRIPE_SECRET_KEY and payment.stripe_session_id.startswith('cs_test_mock_'):
            # Mock Refund
            payment.status = 'refunded'
            payment.save()
            purchase = Purchase.objects.filter(student=payment.student, note=payment.note).first()
            if purchase:
                purchase.delete()
                teacher_profile = payment.note.teacher.teacher_profile
                teacher_profile.total_earnings -= payment.amount
                teacher_profile.save()
            
            RefundTracking.objects.create(
                payment=payment,
                stripe_refund_id="re_test_mock_refund",
                amount=payment.amount,
                reason="Requested mock refund",
                status="completed"
            )
            messages.success(request, "Mock refund processed successfully.")
            return redirect('Eduverse:admin_dashboard')

        if not payment.stripe_payment_intent:
            messages.error(request, "Cannot refund: payment intent missing.")
            return redirect('Eduverse:admin_dashboard')

        try:
            refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent
            )
            messages.success(request, f"Refund initiated in Stripe (ID: {refund.id}). Webhook will process the final revocation.")
            
            RefundTracking.objects.create(
                payment=payment,
                stripe_refund_id=refund.id,
                amount=refund.amount / 100.0,
                reason=refund.reason or '',
                status=refund.status
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe Refund Error: {e}")
            messages.error(request, f"Stripe refund error: {str(e)}")

        return redirect('Eduverse:admin_dashboard')

class PaymentSuccessView(LoginRequiredMixin, StudentRequiredMixin, TemplateView):
    template_name = 'payments/success.html'

    def get(self, request, *args, **kwargs):
        session_id = request.GET.get('session_id')
        if not session_id:
            messages.error(request, "Invalid access to payment success page.")
            return redirect('Eduverse:notes_list')

        # Verify against Stripe and local DB
        try:
            payment = Payment.objects.get(stripe_session_id=session_id, student=request.user)
            if payment.status != 'completed':
                # For real Stripe sessions, double-check with Stripe API in case
                # of webhook delay. Skip for local mock sessions.
                if settings.STRIPE_SECRET_KEY and not session_id.startswith('cs_test_mock_'):
                    try:
                        stripe_session = stripe.checkout.Session.retrieve(session_id)
                        if stripe_session.payment_status != 'paid':
                            messages.warning(request, "Your payment is still processing or failed.")
                            return redirect('payments:cancel')
                    except stripe.error.StripeError as e:
                        logger.error(f"Stripe session retrieve failed: {e}")
                        messages.error(request, "Error verifying payment with Stripe.")
                        return redirect('Eduverse:notes_list')
                else:
                    # Local dev: treat completed DB record as authoritative
                    messages.warning(request, "Your payment is still processing or failed.")
                    return redirect('payments:cancel')

            context = self.get_context_data()
            context['payment'] = payment
            return self.render_to_response(context)
        except Payment.DoesNotExist:
            messages.error(request, "Payment record not found.")
            return redirect('Eduverse:notes_list')


class PaymentCancelView(TemplateView):
    template_name = 'payments/cancel.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        note_id = self.request.GET.get('note_id')
        if note_id:
            try:
                context['note'] = Notes.objects.get(id=note_id)
            except Notes.DoesNotExist:
                pass
        return context

class PurchaseHistoryView(LoginRequiredMixin, StudentRequiredMixin, ListView):
    model = Purchase
    template_name = 'payments/purchase_history.html'
    context_object_name = 'purchases'
    paginate_by = 10

    def get_queryset(self):
        return Purchase.objects.filter(student=self.request.user).order_by('-purchased_at')
