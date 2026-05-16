import os
# pyrefly: ignore [missing-import]
from django.core.exceptions import ValidationError

def validate_file_security(value):
    """
    Validates file extension, MIME type, and file size (max 50MB).
    """
    # 1. Extension Validation
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError(f'Unsupported file extension: {ext}. Allowed are: .pdf, .doc, .docx, .jpg, .png.')

    # 2. File Size Validation (50 MB limit)
    filesize = value.size
    if filesize > 50 * 1024 * 1024:
        raise ValidationError("The maximum file size that can be uploaded is 50MB")

    # 3. MIME Type Validation (Django's built-in content_type)
    # This is a basic check. For higher security, use python-magic in prod.
    valid_mime_types = [
        'application/pdf', 
        'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/jpeg',
        'image/png'
    ]
    
    if hasattr(value, 'content_type'):
        if value.content_type not in valid_mime_types:
            raise ValidationError(f'Unsupported MIME type: {value.content_type}.')

def validate_file_extension(value):
    # Backward compatibility
    validate_file_security(value)

import uuid
import logging

logger = logging.getLogger(__name__)

def send_verification_sms(user, request):
    # pyrefly: ignore [import-outside-toplevel, missing-import]
    from .models import PhoneVerificationToken
    # pyrefly: ignore [import-outside-toplevel, missing-import]
    from django.urls import reverse
    import os

    # Generate Token
    token_str = str(uuid.uuid4())
    token = PhoneVerificationToken.objects.create(user=user, token=token_str)

    # Build Verification URL
    protocol = 'https' if request.is_secure() else 'http'
    domain = request.get_host()
    verify_url = f"{protocol}://{domain}{reverse('Eduverse:verify_phone', kwargs={'token': token_str})}"

    message_body = f"Welcome! Your Eduverse verification link is: {verify_url}\nThe link expires in 15 minutes."

    # Try sending SMS
    twilio_sid = os.getenv('TWILIO_ACCOUNT_SID')
    twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    twilio_number = os.getenv('TWILIO_PHONE_NUMBER')

    if twilio_sid and twilio_auth_token and twilio_number:
        try:
            # pyrefly: ignore [missing-import]
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_auth_token)
            message = client.messages.create(
                body=message_body,
                from_=twilio_number,
                to=user.phone_number
            )
            logger.info(f"Sent SMS to {user.phone_number}. SID: {message.sid}")
        except Exception as e:
            logger.error(f"Failed to send SMS to {user.phone_number}: {e}")
            print(f"Fallback SMS log: {message_body}")
    else:
        logger.warning(f"Twilio credentials not found. Simulating SMS to {user.phone_number}.")
        print(f"--- SIMULATED SMS TO {user.phone_number} ---")
        print(message_body)
        print("---------------------------------------")
