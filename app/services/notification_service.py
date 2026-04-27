import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(subject: str, body: str, to_email: Optional[str] = None) -> bool:
    """Send email notification via SMTP. Returns True on success."""
    recipient = to_email or settings.NOTIFICATION_EMAIL

    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD, recipient]):
        logger.warning("SMTP not configured — skipping email notification")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = recipient

        # Plain text version
        msg.attach(MIMEText(body, "plain"))

        # HTML version
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    Book Generation System
                </h2>
                <div style="padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                    {body.replace(chr(10), '<br>')}
                </div>
                <p style="color: #7f8c8d; font-size: 12px; margin-top: 20px;">
                    This is an automated notification from the Book Generation System.
                </p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [recipient], msg.as_string())

        logger.info(f"Email sent: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def notify_outline_ready(book_title: str, book_id: str):
    send_email(
        subject=f"Outline Ready for Review: {book_title}",
        body=(
            f"The outline for \"{book_title}\" has been generated and is ready for review.\n\n"
            f"Book ID: {book_id}\n\n"
            "Please review the outline and update the status:\n"
            "- Set status_outline_notes to 'no_notes_needed' to proceed to chapter generation\n"
            "- Set status_outline_notes to 'yes' and add notes for revisions\n"
        ),
    )


def notify_chapter_notes_needed(book_title: str, book_id: str, chapter_number: int):
    send_email(
        subject=f"Chapter {chapter_number} Notes Needed: {book_title}",
        body=(
            f"Chapter {chapter_number} of \"{book_title}\" has been generated.\n\n"
            f"Book ID: {book_id}\n\n"
            "The workflow is paused waiting for chapter notes.\n"
            "Please review and update the chapter notes status to continue."
        ),
    )


def notify_final_draft_compiled(book_title: str, book_id: str):
    send_email(
        subject=f"Final Draft Compiled: {book_title}",
        body=(
            f"The final draft of \"{book_title}\" has been compiled successfully.\n\n"
            f"Book ID: {book_id}\n\n"
            "Output files have been generated in both .txt and .docx formats."
        ),
    )


def notify_workflow_paused(book_title: str, book_id: str, reason: str):
    send_email(
        subject=f"Workflow Paused: {book_title}",
        body=(
            f"The workflow for \"{book_title}\" has been paused.\n\n"
            f"Book ID: {book_id}\n"
            f"Reason: {reason}\n\n"
            "Please provide the missing input to resume the workflow."
        ),
    )
