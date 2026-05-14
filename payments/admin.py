from django.contrib import admin
from .models import Payment, TransactionLog, RefundTracking

class TransactionLogInline(admin.TabularInline):
    model = TransactionLog
    extra = 0
    readonly_fields = ('event_type', 'stripe_event_id', 'created_at', 'event_data')
    can_delete = False

class RefundTrackingInline(admin.TabularInline):
    model = RefundTracking
    extra = 0
    readonly_fields = ('stripe_refund_id', 'amount', 'reason', 'status', 'created_at')
    can_delete = False

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'note', 'amount', 'currency', 'status', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('student__email', 'note__title', 'stripe_session_id', 'stripe_payment_intent')
    readonly_fields = ('stripe_session_id', 'stripe_payment_intent', 'created_at', 'updated_at')
    inlines = [TransactionLogInline, RefundTrackingInline]

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('payment', 'event_type', 'stripe_event_id', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('payment__stripe_session_id', 'stripe_event_id')
    readonly_fields = ('payment', 'event_type', 'event_data', 'stripe_event_id', 'created_at')

    def has_add_permission(self, request):
        return False

@admin.register(RefundTracking)
class RefundTrackingAdmin(admin.ModelAdmin):
    list_display = ('payment', 'stripe_refund_id', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('stripe_refund_id', 'payment__stripe_session_id')
    readonly_fields = ('payment', 'stripe_refund_id', 'amount', 'reason', 'status', 'created_at')

    def has_add_permission(self, request):
        return False
