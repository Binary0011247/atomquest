import asyncio
import os
import sys
import ssl

# ─── SSL Fix for Mac ───────────────────────────────────────────
try:
    import certifi
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    print("✅ SSL certificates loaded from certifi")
except ImportError:
    print("⚠️  certifi not found — applying SSL bypass for local dev")
    ssl._create_default_https_context = ssl._create_unverified_context

# ─── Load .env ─────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ─── Validate env vars before anything else ────────────────────
SENDGRID_API_KEY   = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")
SENDGRID_FROM_NAME  = os.getenv("SENDGRID_FROM_NAME", "AtomQuest Goal Portal")
FRONTEND_URL        = os.getenv("FRONTEND_URL", "http://localhost:5173")

errors = []
if not SENDGRID_API_KEY:
    errors.append("❌ SENDGRID_API_KEY is missing from .env")
if not SENDGRID_API_KEY.startswith("SG."):
    errors.append("❌ SENDGRID_API_KEY looks invalid (should start with SG.)")
if not SENDGRID_FROM_EMAIL:
    errors.append("❌ SENDGRID_FROM_EMAIL is missing from .env")

if errors:
    print("\n" + "="*50)
    print("  CONFIGURATION ERRORS")
    print("="*50)
    for e in errors:
        print(e)
    print("\nFix your backend/.env file and try again.")
    sys.exit(1)

# ─── SendGrid setup ────────────────────────────────────────────
import sendgrid as sg_module
from sendgrid.helpers.mail import Mail, Email, To, HtmlContent

sg_client = sg_module.SendGridAPIClient(api_key=SENDGRID_API_KEY)

# ─── Get recipient email ───────────────────────────────────────
TEST_EMAIL = sys.argv[1] if len(sys.argv) > 1 else input(
    "\nEnter your email to receive test emails: "
).strip()

if not TEST_EMAIL or "@" not in TEST_EMAIL:
    print("❌ Invalid email address. Please provide a valid email.")
    sys.exit(1)

# ─── Results tracker ───────────────────────────────────────────
results = []

# ─── Base HTML template ────────────────────────────────────────
def get_base_template(content: str, title: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>{title}</title>
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont,
          'Segoe UI', sans-serif;
          background: #f3f4f6; margin: 0; padding: 20px;
        }}
        .container {{
          max-width: 600px; margin: 0 auto;
          background: white; border-radius: 12px;
          overflow: hidden;
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
        .alert-green {{ background: #d1fae5; border-left: 4px solid #10b981; }}
        .alert-yellow {{ background: #fef3c7; border-left: 4px solid #f59e0b; }}
        .alert-orange {{ background: #ffedd5; border-left: 4px solid #f97316; }}
        .alert-red {{ background: #fee2e2; border-left: 4px solid #dc2626; }}
        .alert-blue {{ background: #dbeafe; border-left: 4px solid #3b82f6; }}
        .btn {{
          display: inline-block; padding: 12px 28px;
          border-radius: 8px; text-decoration: none;
          font-weight: 600; font-size: 15px; margin: 20px 0;
        }}
        .btn-blue {{ background: #3b82f6; color: white; }}
        .btn-orange {{ background: #f97316; color: white; }}
        .btn-red {{ background: #dc2626; color: white; }}
        .detail-row {{
          display: flex; padding: 8px 0;
          border-bottom: 1px solid #f3f4f6;
        }}
        .detail-label {{
          font-weight: 600; color: #374151; width: 140px; flex-shrink: 0;
        }}
        .detail-value {{ color: #6b7280; }}
        .chain-row {{
          display: flex; align-items: center;
          gap: 8px; margin: 16px 0; flex-wrap: wrap;
        }}
        .chain-badge {{
          padding: 4px 12px; border-radius: 20px;
          font-size: 12px; font-weight: 600;
        }}
        .badge-green {{ background: #22c55e; color: white; }}
        .badge-orange {{ background: #f97316; color: white; }}
        .badge-red {{ background: #dc2626; color: white; }}
        .badge-gray {{ background: #e5e7eb; color: #374151; }}
        .footer {{
          background: #f9fafb; padding: 20px 30px;
          text-align: center; color: #6b7280;
          font-size: 12px; border-top: 1px solid #e5e7eb;
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>⚡ AtomQuest</h1>
          <p>Goal Management Portal</p>
        </div>
        <div class="body">
          {content}
        </div>
        <div class="footer">
          <p>This is an automated notification from AtomQuest Goal Portal.</p>
          <p>© 2026 AtomQuest | Powered by Atomberg</p>
        </div>
      </div>
    </body>
    </html>
    """

# ─── Core send function ────────────────────────────────────────
async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str
) -> bool:
    message = Mail(
        from_email=Email(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
        to_emails=To(to_email, to_name),
        subject=subject,
        html_content=HtmlContent(html_content)
    )
    response = sg_client.client.mail.send.post(
        request_body=message.get()
    )
    print(f"    📨 SendGrid response: HTTP {response.status_code}")
    if response.status_code not in [200, 202]:
        raise Exception(
            f"SendGrid returned status {response.status_code}"
        )
    return True

# ─── Email builders ────────────────────────────────────────────

async def test_goal_approved(to_email: str):
    subject = "[AtomQuest] Your goal was approved ✅"
    content = f"""
    <h2>Goal Approved! ✅</h2>
    <p>Hi Priya Employee,</p>
    <p>Great news! Your goal has been approved and locked by your manager.</p>
    <div class="alert-box alert-green">
      <div class="detail-row">
        <span class="detail-label">Goal:</span>
        <span class="detail-value">Monthly Revenue Target</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Approved by:</span>
        <span class="detail-value">Meera Manager</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Status:</span>
        <span class="detail-value">🔒 Locked & Active</span>
      </div>
    </div>
    <p>You can now log quarterly check-ins for this goal.</p>
    <a href="{FRONTEND_URL}/employee/checkins" class="btn btn-blue">
      Go to Check-ins →
    </a>
    """
    await send_email(
        to_email, "Priya Employee", subject,
        get_base_template(content, subject)
    )

async def test_goal_returned(to_email: str):
    subject = "[AtomQuest] Action needed: Goal returned for revision ↩️"
    content = f"""
    <h2>Goal Returned for Revision ↩️</h2>
    <p>Hi Priya Employee,</p>
    <p>Your manager has returned one of your goals for revision.</p>
    <div class="alert-box alert-yellow">
      <div class="detail-row">
        <span class="detail-label">Goal:</span>
        <span class="detail-value">Product Launch Timeline</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Returned by:</span>
        <span class="detail-value">Meera Manager</span>
      </div>
    </div>
    <p><strong>Manager's feedback:</strong></p>
    <div class="alert-box alert-orange">
      "Please revise the target date to Q3 end.
       Current timeline is too aggressive given team capacity."
    </div>
    <p>Please revise your goal based on the feedback and resubmit.</p>
    <a href="{FRONTEND_URL}/employee/dashboard" class="btn btn-orange">
      Revise &amp; Resubmit →
    </a>
    """
    await send_email(
        to_email, "Priya Employee", subject,
        get_base_template(content, subject)
    )

async def test_goal_submitted(to_email: str):
    subject = "[AtomQuest] Priya Employee submitted 4 goals for your approval"
    content = f"""
    <h2>New Goals Awaiting Approval 📋</h2>
    <p>Hi Meera Manager,</p>
    <p>
      <strong>Priya Employee</strong> has submitted
      <strong>4 goals</strong> for your review and approval.
    </p>
    <div class="alert-box alert-blue">
      <strong>Action Required:</strong> Please review and approve
      or return these goals as soon as possible.
    </div>
    <a href="{FRONTEND_URL}/manager/dashboard" class="btn btn-blue">
      Review Goals Now →
    </a>
    """
    await send_email(
        to_email, "Meera Manager", subject,
        get_base_template(content, subject)
    )

async def test_checkin_reminder(to_email: str):
    subject = "[AtomQuest] Reminder: Log your Q1 check-ins 📊"
    pending = [
        "Monthly Revenue Target",
        "Customer Satisfaction Score",
        "Product Launch Timeline"
    ]
    goals_html = "".join([f"<li>{g}</li>" for g in pending])
    content = f"""
    <h2>Check-in Reminder 📊</h2>
    <p>Hi Priya Employee,</p>
    <p>
      You have <strong>{len(pending)} goals</strong> with
      pending <strong>Q1</strong> check-ins.
    </p>
    <div class="alert-box alert-yellow">
      <strong>Goals needing check-in:</strong>
      <ul>{goals_html}</ul>
    </div>
    <p>The Q1 check-in window is open. Please log your actuals now.</p>
    <a href="{FRONTEND_URL}/employee/checkins" class="btn btn-blue">
      Log Check-ins Now →
    </a>
    """
    await send_email(
        to_email, "Priya Employee", subject,
        get_base_template(content, subject)
    )

async def test_escalation_employee(to_email: str):
    subject = "[AtomQuest] ⚠️ Reminder: Action Required — 3 days overdue"
    content = f"""
    <h2>Action Required ⚠️</h2>
    <p>Hi Priya Employee,</p>
    <p>
      The following action has been pending for
      <strong>3 days</strong>:
    </p>
    <div class="alert-box alert-yellow">
      <strong>Submit your goals for approval</strong><br/>
      Goal: Monthly Revenue Target
    </div>
    <p><strong>Escalation chain status:</strong></p>
    <div class="chain-row">
      <span class="chain-badge badge-green">✅ You notified</span>
      <span>→</span>
      <span class="chain-badge badge-gray">👥 Manager (next)</span>
      <span>→</span>
      <span class="chain-badge badge-gray">🏢 HR</span>
    </div>
    <p>
      Please complete this action immediately
      to avoid further escalation to your manager.
    </p>
    <a href="{FRONTEND_URL}/employee/dashboard" class="btn btn-blue">
      Take Action Now →
    </a>
    """
    await send_email(
        to_email, "Priya Employee", subject,
        get_base_template(content, subject)
    )

async def test_escalation_manager(to_email: str):
    subject = "[AtomQuest] 🔔 Team escalation: Priya Employee needs attention"
    content = f"""
    <h2>Team Escalation 🔔</h2>
    <p>Hi Meera Manager,</p>
    <p>
      Your team member <strong>Priya Employee</strong>
      has a pending action for <strong>5 days</strong>.
      They have been notified but have not taken action yet.
    </p>
    <div class="alert-box alert-orange">
      <strong>Approve submitted goals</strong><br/>
      Goal: Monthly Revenue Target
    </div>
    <p><strong>Escalation chain status:</strong></p>
    <div class="chain-row">
      <span class="chain-badge badge-green">✅ Employee notified</span>
      <span>→</span>
      <span class="chain-badge badge-orange">✅ You notified</span>
      <span>→</span>
      <span class="chain-badge badge-gray">🏢 HR (next)</span>
    </div>
    <p>
      Please follow up with Priya Employee
      or take action directly in the portal.
    </p>
    <a href="{FRONTEND_URL}/manager/dashboard" class="btn btn-orange">
      View Team Dashboard →
    </a>
    """
    await send_email(
        to_email, "Meera Manager", subject,
        get_base_template(content, subject)
    )

async def test_escalation_hr(to_email: str):
    subject = "[AtomQuest] 🚨 Critical Escalation: Priya Employee — 7 days overdue"
    content = f"""
    <h2>🚨 Critical Escalation — HR Action Needed</h2>
    <p>Hi Aryan Admin,</p>
    <p>
      This is a skip-level escalation. Both the employee
      and their manager have been notified but no action
      has been taken after <strong>7 days</strong>.
    </p>
    <div class="alert-box alert-red">
      <div class="detail-row">
        <span class="detail-label">Employee:</span>
        <span class="detail-value">Priya Employee</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Manager:</span>
        <span class="detail-value">Meera Manager</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Action:</span>
        <span class="detail-value">Goals not submitted after 7 days</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Goal:</span>
        <span class="detail-value">Monthly Revenue Target</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Days Overdue:</span>
        <span class="detail-value" style="color:red; font-weight:bold;">
          7 days
        </span>
      </div>
    </div>
    <p><strong>Escalation chain status:</strong></p>
    <div class="chain-row">
      <span class="chain-badge badge-green">✅ Employee notified</span>
      <span>→</span>
      <span class="chain-badge badge-green">✅ Manager notified</span>
      <span>→</span>
      <span class="chain-badge badge-red">🚨 HR escalated</span>
    </div>
    <p>Immediate intervention is required.</p>
    <a href="{FRONTEND_URL}/admin/escalations" class="btn btn-red">
      View Escalation Dashboard →
    </a>
    """
    await send_email(
        to_email, "Aryan Admin", subject,
        get_base_template(content, subject)
    )

# ─── Test runner ───────────────────────────────────────────────
async def run_test(name: str, coro):
    print(f"\n{'='*50}")
    print(f"  Testing: {name}")
    print(f"{'='*50}")
    try:
        await coro
        print(f"  ✅ PASSED: {name}")
        results.append({"test": name, "status": "✅ PASS"})
    except Exception as e:
        print(f"  ❌ FAILED: {name}")
        print(f"  Error: {str(e)}")
        results.append({"test": name, "status": f"❌ FAIL: {str(e)}"})

# ─── Main ──────────────────────────────────────────────────────
async def main():
    print("\n" + "="*50)
    print("  ATOMQUEST SENDGRID EMAIL TESTER")
    print("="*50)
    print(f"  Recipient : {TEST_EMAIL}")
    print(f"  From      : {SENDGRID_FROM_EMAIL}")
    print(f"  From Name : {SENDGRID_FROM_NAME}")
    print(f"  API Key   : SG.{'*' * 20}")
    print(f"  Frontend  : {FRONTEND_URL}")
    print("="*50)
    print("\n  Running 7 email tests...\n")

    await run_test(
        "1. Goal Approved Email",
        test_goal_approved(TEST_EMAIL)
    )
    await asyncio.sleep(1)

    await run_test(
        "2. Goal Returned Email",
        test_goal_returned(TEST_EMAIL)
    )
    await asyncio.sleep(1)

    await run_test(
        "3. Goals Submitted (Manager Notification)",
        test_goal_submitted(TEST_EMAIL)
    )
    await asyncio.sleep(1)

    await run_test(
        "4. Check-in Reminder Email",
        test_checkin_reminder(TEST_EMAIL)
    )
    await asyncio.sleep(1)

    await run_test(
        "5. Escalation — Employee Level (Day 3)",
        test_escalation_employee(TEST_EMAIL)
    )
    await asyncio.sleep(1)

    await run_test(
        "6. Escalation — Manager Level (Day 5)",
        test_escalation_manager(TEST_EMAIL)
    )
    await asyncio.sleep(1)

    await run_test(
        "7. Escalation — HR Critical (Day 7)",
        test_escalation_hr(TEST_EMAIL)
    )

    # ── Summary ──────────────────────────────────────────────
    print("\n" + "="*50)
    print("  TEST RESULTS SUMMARY")
    print("="*50)
    for r in results:
        print(f"  {r['status']} — {r['test']}")

    passed = len([r for r in results if "PASS" in r["status"]])
    failed = len([r for r in results if "FAIL" in r["status"]])

    print(f"\n  Total  : {len(results)}")
    print(f"  Passed : {passed} ✅")
    print(f"  Failed : {failed} ❌")

    if failed == 0:
        print(f"""
  🎉 All emails sent successfully!

  ✅ Next steps:
  1. Check inbox: {TEST_EMAIL}
  2. Check spam/junk if not in inbox
  3. Verify in SendGrid dashboard:
     → app.sendgrid.com → Activity Feed
     → All 7 should show as "Delivered"

  📧 Emails sent:
     1. Goal Approved
     2. Goal Returned with manager comment
     3. Goals Submitted (manager notification)
     4. Check-in Reminder (3 goals listed)
     5. Escalation — Employee level
     6. Escalation — Manager level
     7. Escalation — HR Critical
        """)
    else:
        print(f"""
  ⚠️  {failed} email(s) failed. Common fixes:

  1. SSL issue on Mac:
     → Run: pip install certifi
     → Run: /Applications/Python\\ 3.11/Install\\ Certificates.command

  2. Invalid API key:
     → Check SENDGRID_API_KEY starts with SG.
     → Regenerate at app.sendgrid.com → API Keys

  3. Sender not verified:
     → Go to SendGrid → Settings → Sender Authentication
     → Verify {SENDGRID_FROM_EMAIL}

  4. Free tier limit reached:
     → SendGrid free = 100 emails/day
     → Check app.sendgrid.com → Activity for quota
        """)

if __name__ == "__main__":
    asyncio.run(main())