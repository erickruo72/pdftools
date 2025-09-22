from flask import current_app
from flask_mail import Message

def send_contact_email(name, email, subject, message_body):
    """
    Sends a contact form submission email to the specified recipient.
    
    Args:
        name (str): The sender's name.
        email (str): The sender's email address.
        subject (str): The subject of the message.
        message_body (str): The body of the message.
    """
    try:
        # The 'mail' object is accessed from the current application context.
        # This assumes Flask-Mail has been configured in the main app.py file.
        mail = current_app.extensions.get('mail')
        if not mail:
            raise RuntimeError("Flask-Mail extension not initialized.")

        # Create the email message
        msg = Message(
            subject=f"New Contact Form Submission: {subject}",
            sender=current_app.config['MAIL_USERNAME'],
            recipients=['erickruo72@gmail.com'],  # Your email address
            reply_to=email,
            body=f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_body}"
        )
        
        # Send the email
        mail.send(msg)
        return True
    except Exception as e:
        # Re-raise the exception for the caller to handle
        raise e