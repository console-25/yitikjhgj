import os, smtplib, ssl
from email.message import EmailMessage

def send_email(job_id):
    from . import create_app
    from .models import db, EmailJob
    app=create_app()
    with app.app_context():
        job=db.session.get(EmailJob,job_id)
        if not job or job.state=='sent': return
        job.attempts+=1; db.session.commit()
        message=EmailMessage(); message['From']=os.environ['SMTP_FROM']; message['To']=job.recipient
        message['Subject']=job.subject; message['Message-ID']=f'<noryx-{job.id}@{os.environ["SMTP_FROM"].split("@")[-1]}>'
        message.set_content(job.body)
        try:
            with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=20) as smtp:
                if os.getenv('SMTP_STARTTLS','true').lower()=='true': smtp.starttls(context=ssl.create_default_context())
                if os.getenv('SMTP_USER'): smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
                smtp.send_message(message)
            job.state='sent'; job.body='[Content removed after successful delivery]'; db.session.commit()
        except Exception:
            job.state='failed'; db.session.commit(); raise
