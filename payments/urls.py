from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('create-checkout-session/', views.CreateCheckoutSessionView.as_view(), name='create_checkout_session'),
    path('webhook/', views.StripeWebhookView.as_view(), name='webhook'),
    path('success/', views.PaymentSuccessView.as_view(), name='success'),
    path('cancel/', views.PaymentCancelView.as_view(), name='cancel'),
    path('history/', views.PurchaseHistoryView.as_view(), name='purchase_history'),
    path('<int:payment_id>/refund/', views.InitiateRefundView.as_view(), name='initiate_refund'),
]
