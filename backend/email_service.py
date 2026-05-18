import logging
import os
import ssl
import certifi

import sendgrid
from sendgrid.helpers.mail import Email, HtmlContent, Mail, To

logger = logging.getLogger("atomquest.email")

_api_key = os.getenv("SENDGRID_API_KEY")
sg = sendgrid.SendGridAPIClient(api_key=_api_key) if _api_key else None

FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "manjugupta.jjk@gmail.com")
FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "AtomQuest Goal Portal")
BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def get_base_template(content: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width">
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f3f4f6; margin: 0; padding: 20px;
    }}
    .container {{
      max-width: 600px; margin: 0 auto; background: white;
      border-radius: 12px; overflow: hidden;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .header {{
      background: linear-gradient(135deg, #1e40af, #3b82f6);
      padding: 30px; text-align: center;
    }}
    .header h1 {{ color: white; margin: 0; font-size: 24px; }}
    .header p {{ color: #bfdbfe; margin: 5px 0 0; font-size: 14px; }}
    .body {{ padding: 30px; }}
    .alert-box {{ padding: 16px; border-radius: 8px; margin: 20px 0; }}
    .alert-yellow {{ background: #fef3c7; border-left: 4px solid #f59e0b; }}
    .alert-orange {{ background: #ffedd5; border-left: 4px solid #f97316; }}
    .alert-red {{ background: #fee2e2; border-left: 4px solid #dc2626; }}
    .alert-green {{ background: #d1fae5; border-left: 4px solid #10b981; }}
    .alert-blue {{ background: #dbeafe; border-left: 4px solid #3b82f6; }}
    .btn {{
      display: inline-block; padding: 12px 28px; border-radius: 8px;
      text-decoration: none; font-weight: 600; font-size: 15px; margin: 20px 0;
    }}
    .btn-blue {{ background: #3b82f6; color: white; }}
    .btn-orange {{ background: #f97316; color: white; }}
    .btn-red {{ background: #dc2626; color: white; }}
    .footer {{
      background: #f9fafb; padding: 20px 30px; text-align: center;
      color: #6b7280; font-size: 12px; border-top: 1px solid #e5e7eb;
    }}
    .detail-row {{ display: flex; padding: 8px 0; border-bottom: 1px solid #f3f4f6; }}
    .detail-label {{ font-weight: 600; color: #374151; width: 140px; flex-shrink: 0; }}
    .detail-value {{ color: #6b7280; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⚡ AtomQuest</h1>
      <p>Goal Management Portal</p>
    </div>
    <div class="body">{content}</div>
    <div class="footer">
      <p>This is an automated notification from AtomQuest Goal Portal.</p>
      <p>© 2026 AtomQuest | Powered by Atomberg</p>
    </div>
  </div>
</body>
</html>"""


async def send_email_sendgrid(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
) -> bool:
    if not sg or not FROM_EMAIL:
        logger.warning("SendGrid not configured; skipping email to %s", to_email)
        return False
    try:
      import urllib.request
      ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )
      message = Mail(
        from_email=Email(FROM_EMAIL, FROM_NAME),
        to_emails=To(to_email, to_name),
        subject=subject,
        html_content=HtmlContent(html_content),
        )
      response = sg.client.mail.send.post(request_body=message.get())
      print(f"Email sent: status {response.status_code}")
      return response.status_code in (200, 202)
    except Exception as exc:
        logger.error("SendGrid error: %s", exc)
        return False


async def send_goal_submitted_notification(
    manager_email: str,
    manager_name: str,
    employee_name: str,
    goal_count: int,
) -> None:
    subject = f"[AtomQuest] {employee_name} submitted {goal_count} goals for your approval"
    content = f"""
    <h2>New Goals Awaiting Approval</h2>
    <p>Hi {manager_name},</p>
    <p><strong>{employee_name}</strong> has submitted <strong>{goal_count} goals</strong>
    for your review and approval.</p>
    <div class="alert-box alert-blue">
      <strong>Action Required:</strong> Please review and approve or return these goals
      as soon as possible.
    </div>
    <a href="{BASE_URL}/manager/dashboard" class="btn btn-blue">Review Goals Now →</a>
    """
    await send_email_sendgrid(
        manager_email, manager_name, subject, get_base_template(content, subject)
    )


async def send_goal_approved_notification(
    employee_email: str,
    employee_name: str,
    goal_title: str,
    manager_name: str,
) -> None:
    subject = "[AtomQuest] Your goal was approved ✅"
    content = f"""
    <h2>Goal Approved! ✅</h2>
    <p>Hi {employee_name},</p>
    <p>Great news! Your goal has been approved and locked.</p>
    <div class="alert-box alert-green">
      <div class="detail-row">
        <span class="detail-label">Goal:</span>
        <span class="detail-value">{goal_title}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Approved by:</span>
        <span class="detail-value">{manager_name}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Status:</span>
        <span class="detail-value">🔒 Locked & Active</span>
      </div>
    </div>
    <p>You can now log quarterly check-ins for this goal.</p>
    <a href="{BASE_URL}/employee/checkins" class="btn btn-blue">Go to Check-ins →</a>
    """
    await send_email_sendgrid(
        employee_email, employee_name, subject, get_base_template(content, subject)
    )


async def send_goal_returned_notification(
    employee_email: str,
    employee_name: str,
    goal_title: str,
    manager_name: str,
    return_reason: str,
) -> None:
    subject = "[AtomQuest] Action needed: Goal returned for revision"
    content = f"""
    <h2>Goal Returned for Revision ↩️</h2>
    <p>Hi {employee_name},</p>
    <p>Your manager has returned one of your goals for revision.</p>
    <div class="alert-box alert-yellow">
      <div class="detail-row">
        <span class="detail-label">Goal:</span>
        <span class="detail-value">{goal_title}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Returned by:</span>
        <span class="detail-value">{manager_name}</span>
      </div>
    </div>
    <p><strong>Manager's feedback:</strong></p>
    <div class="alert-box alert-orange">"{return_reason}"</div>
    <p>Please revise your goal based on the feedback and resubmit.</p>
    <a href="{BASE_URL}/employee/dashboard" class="btn btn-orange">Revise & Resubmit →</a>
    """
    await send_email_sendgrid(
        employee_email, employee_name, subject, get_base_template(content, subject)
    )


async def send_checkin_reminder(
    employee_email: str,
    employee_name: str,
    quarter: str,
    pending_goals: list[str],
) -> None:
    goals_html = "".join([f"<li>{g}</li>" for g in pending_goals])
    subject = f"[AtomQuest] Reminder: Log your {quarter} check-ins"
    content = f"""
    <h2>Check-in Reminder 📊</h2>
    <p>Hi {employee_name},</p>
    <p>You have <strong>{len(pending_goals)} goals</strong> with pending
    <strong>{quarter}</strong> check-ins.</p>
    <div class="alert-box alert-yellow">
      <strong>Goals needing check-in:</strong>
      <ul>{goals_html}</ul>
    </div>
    <a href="{BASE_URL}/employee/checkins" class="btn btn-blue">Log Check-ins Now →</a>
    """
    await send_email_sendgrid(
        employee_email, employee_name, subject, get_base_template(content, subject)
    )


async def send_escalation_employee(
    employee_email: str,
    employee_name: str,
    action: str,
    days_overdue: int,
    goal_title: str | None = None,
) -> None:
    goal_line = f"<br/>Goal: {goal_title}" if goal_title else ""
    subject = "[AtomQuest] ⚠️ Reminder: Action Required"
    content = f"""
    <h2>Action Required ⚠️</h2>
    <p>Hi {employee_name},</p>
    <p>The following action has been pending for <strong>{days_overdue} days</strong>:</p>
    <div class="alert-box alert-yellow">
      <strong>{action}</strong>{goal_line}
    </div>
    <p>Please complete this action immediately to avoid further escalation.</p>
    <a href="{BASE_URL}/employee/dashboard" class="btn btn-blue">Take Action Now →</a>
    """
    await send_email_sendgrid(
        employee_email, employee_name, subject, get_base_template(content, subject)
    )


async def send_escalation_manager(
    manager_email: str,
    manager_name: str,
    employee_name: str,
    action: str,
    days_overdue: int,
    goal_title: str | None = None,
) -> None:
    goal_line = f"<br/>Goal: {goal_title}" if goal_title else ""
    subject = f"[AtomQuest] 🔔 Team escalation: {employee_name} needs attention"
    content = f"""
    <h2>Team Escalation 🔔</h2>
    <p>Hi {manager_name},</p>
    <p>Your team member <strong>{employee_name}</strong> has a pending action for
    <strong>{days_overdue} days</strong>. They have been notified but have not taken action yet.</p>
    <div class="alert-box alert-orange">
      <strong>{action}</strong>{goal_line}
    </div>
    <p>Please follow up with {employee_name} or take action directly.</p>
    <a href="{BASE_URL}/manager/dashboard" class="btn btn-orange">View Team Dashboard →</a>
    """
    await send_email_sendgrid(
        manager_email, manager_name, subject, get_base_template(content, subject)
    )


async def send_escalation_hr(
    hr_email: str,
    hr_name: str,
    employee_name: str,
    manager_name: str,
    action: str,
    days_overdue: int,
    goal_title: str | None = None,
) -> None:
    goal_row = ""
    if goal_title:
        goal_row = f"""
      <div class="detail-row">
        <span class="detail-label">Goal:</span>
        <span class="detail-value">{goal_title}</span>
      </div>"""
    subject = f"[AtomQuest] 🚨 Critical Escalation: {employee_name} — {days_overdue} days overdue"
    content = f"""
    <h2>🚨 Critical Escalation — HR Action Needed</h2>
    <p>Hi {hr_name},</p>
    <p>This is a skip-level escalation. Both the employee and their manager have been notified
    but no action has been taken after <strong>{days_overdue} days</strong>.</p>
    <div class="alert-box alert-red">
      <div class="detail-row">
        <span class="detail-label">Employee:</span>
        <span class="detail-value">{employee_name}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Manager:</span>
        <span class="detail-value">{manager_name}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Action:</span>
        <span class="detail-value">{action}</span>
      </div>
      {goal_row}
      <div class="detail-row">
        <span class="detail-label">Days Overdue:</span>
        <span class="detail-value" style="color: red; font-weight: bold;">{days_overdue} days</span>
      </div>
    </div>
    <p>Immediate intervention is required. Please review and resolve this escalation.</p>
    <a href="{BASE_URL}/admin/escalations" class="btn btn-red">View Escalation Dashboard →</a>
    """
    await send_email_sendgrid(hr_email, hr_name, subject, get_base_template(content, subject))

