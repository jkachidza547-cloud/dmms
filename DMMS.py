
import streamlit as st
import sqlite3
import hashlib
import secrets
import os
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════
DB_PATH = "marketing_os.db"
APP_NAME = "DMMS"

st.set_page_config(page_title=APP_NAME, page_icon="", layout="wide")

ROLES = [
    "CEO", "Marketing Executive", "Marketing Manager", "Campaign Manager",
    "Digital Marketing Specialist", "Content Creator", "Graphic Designer",
    "Research Analyst", "Finance Officer", "Marketing Assistant",
    "System Administrator",
]

CAMPAIGN_STATUSES = [
    "Draft", "Submitted", "Under Review", "Approved",
    "Scheduled", "Active", "Completed", "Evaluated", "Rejected", "Cancelled",
]

TASK_STATUSES = ["To Do", "In Progress", "Blocked", "Done", "Cancelled"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
KPI_TYPES = ["Higher is better", "Lower is better", "Exact target", "Range-based"]

# ═══════════════════════════════════════════════════════════════
# DB SCHEMA
# ═══════════════════════════════════════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS organisations (
  organisation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, currency TEXT DEFAULT 'USD', timezone TEXT DEFAULT 'UTC',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS departments (
  department_id INTEGER PRIMARY KEY AUTOINCREMENT,
  organisation_id INTEGER NOT NULL, name TEXT NOT NULL,
  parent_department_id INTEGER,
  FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id)
);
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  organisation_id INTEGER NOT NULL, full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'Marketing Assistant',
  department_id INTEGER, is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id)
);
CREATE TABLE IF NOT EXISTS strategic_plans (
  plan_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
  start_date TEXT NOT NULL, end_date TEXT NOT NULL,
  status TEXT DEFAULT 'Draft', created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS business_objectives (
  objective_id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL,
  title TEXT NOT NULL, description TEXT, owner_id INTEGER,
  status TEXT DEFAULT 'Active', created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (plan_id) REFERENCES strategic_plans(plan_id)
);
CREATE TABLE IF NOT EXISTS marketing_objectives (
  marketing_objective_id INTEGER PRIMARY KEY AUTOINCREMENT,
  business_objective_id INTEGER NOT NULL, title TEXT NOT NULL,
  description TEXT, owner_id INTEGER, target_value REAL DEFAULT 0,
  current_value REAL DEFAULT 0, unit TEXT DEFAULT 'units',
  due_date TEXT, status TEXT DEFAULT 'Active',
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (business_objective_id) REFERENCES business_objectives(objective_id)
);
CREATE TABLE IF NOT EXISTS milestones (
  milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
  marketing_objective_id INTEGER NOT NULL, title TEXT NOT NULL,
  due_date TEXT, status TEXT DEFAULT 'Pending',
  FOREIGN KEY (marketing_objective_id) REFERENCES marketing_objectives(marketing_objective_id)
);
CREATE TABLE IF NOT EXISTS kpis (
  kpi_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  definition TEXT, formula_type TEXT DEFAULT 'Higher is better',
  unit TEXT DEFAULT 'units', owner_id INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS kpi_targets (
  target_id INTEGER PRIMARY KEY AUTOINCREMENT, kpi_id INTEGER NOT NULL,
  period_start TEXT NOT NULL, period_end TEXT NOT NULL, target_value REAL NOT NULL,
  FOREIGN KEY (kpi_id) REFERENCES kpis(kpi_id)
);
CREATE TABLE IF NOT EXISTS kpi_measurements (
  measurement_id INTEGER PRIMARY KEY AUTOINCREMENT, kpi_id INTEGER NOT NULL,
  period_start TEXT NOT NULL, period_end TEXT NOT NULL,
  actual_value REAL NOT NULL, recorded_by INTEGER,
  recorded_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (kpi_id) REFERENCES kpis(kpi_id)
);
CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  description TEXT, marketing_objective_id INTEGER, owner_id INTEGER,
  campaign_type TEXT DEFAULT 'Digital', status TEXT DEFAULT 'Draft',
  start_date TEXT, end_date TEXT, target_audience TEXT,
  expected_results TEXT, actual_results TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS marketing_channels (
  channel_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS campaign_channels (
  campaign_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
  PRIMARY KEY (campaign_id, channel_id)
);
CREATE TABLE IF NOT EXISTS campaign_results (
  result_id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
  metric_name TEXT NOT NULL, value REAL NOT NULL,
  recorded_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
  description TEXT, campaign_id INTEGER, assigned_to INTEGER,
  priority TEXT DEFAULT 'Medium', status TEXT DEFAULT 'To Do',
  start_date TEXT, due_date TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS budgets (
  budget_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  period_start TEXT NOT NULL, period_end TEXT NOT NULL,
  total_amount REAL NOT NULL, status TEXT DEFAULT 'Draft',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS budget_allocations (
  allocation_id INTEGER PRIMARY KEY AUTOINCREMENT, budget_id INTEGER NOT NULL,
  campaign_id INTEGER, category TEXT, amount REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS expenses (
  expense_id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER,
  budget_id INTEGER, category TEXT, description TEXT,
  amount REAL NOT NULL, expense_date TEXT NOT NULL,
  status TEXT DEFAULT 'Pending', submitted_by INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS research_projects (
  research_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
  owner_id INTEGER, status TEXT DEFAULT 'Active',
  findings TEXT, recommendation TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS competitors (
  competitor_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  website TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS competitor_observations (
  observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  competitor_id INTEGER NOT NULL, observed_date TEXT NOT NULL,
  findings TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content_assets (
  asset_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
  asset_type TEXT DEFAULT 'Image', file_path TEXT,
  status TEXT DEFAULT 'Draft', owner_id INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS content_schedules (
  schedule_id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER NOT NULL,
  channel_id INTEGER, publish_date TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
  requested_by INTEGER, approver_id INTEGER,
  status TEXT DEFAULT 'Pending', decision_notes TEXT,
  created_at TEXT DEFAULT (datetime('now')), decided_at TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
  notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL, message TEXT NOT NULL,
  is_read INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS role_permissions (
  permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
  role TEXT NOT NULL, page TEXT NOT NULL,
  can_view INTEGER DEFAULT 1, can_edit INTEGER DEFAULT 0,
  UNIQUE(role, page)
);
CREATE TABLE IF NOT EXISTS app_settings (
  setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
  action TEXT NOT NULL, entity TEXT, entity_id INTEGER,
  details TEXT, timestamp TEXT DEFAULT (datetime('now'))
);
"""

# ═══════════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + pw).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.sha256((salt + pw).encode()).hexdigest() == h
    except Exception:
        return False


def query(sql, params=()):
    with get_conn() as c:
        df = pd.read_sql_query(sql, c, params=params)
    return scoped_frame(df) if "scoped_frame" in globals() else df


def execute(sql, params=()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def log_audit(user_id, action, entity="", entity_id=None, details=""):
    execute(
        "INSERT INTO audit_logs (user_id, action, entity, entity_id, details) "
        "VALUES (?,?,?,?,?)",
        (user_id, action, entity, entity_id, details),
    )


def notify(user_id, message):
    execute(
        "INSERT INTO notifications (user_id, message) VALUES (?,?)",
        (user_id, message),
    )


# ═══════════════════════════════════════════════════════════════
# SEED DATA
# ═══════════════════════════════════════════════════════════════
def seed(conn):
    org_id = conn.execute(
        "INSERT INTO organisations (name, currency) VALUES (?,?)",
        ("Delma Inc", "USD"),
    ).lastrowid
    dept_id = conn.execute(
        "INSERT INTO departments (organisation_id, name) VALUES (?,?)",
        (org_id, "Marketing"),
    ).lastrowid

    demo_users = [
        ("Alice Banda", "ceo@delma.inc", "CEO", "admin123"),
        ("Brian Moyo", "exec@delma.inc", "Marketing Executive", "admin123"),
        ("Chido Ncube", "manager@delma.inc", "Marketing Manager", "admin123"),
        ("Diana Phiri", "campaign@delma.inc", "Campaign Manager", "admin123"),
        ("Eli Tembo", "finance@delma.inc", "Finance Officer", "admin123"),
        ("Fara Zulu", "content@delma.inc", "Content Creator", "admin123"),
    ]
    for name, email, role, pw in demo_users:
        conn.execute(
            "INSERT INTO users (organisation_id, full_name, email, password_hash, role, department_id) "
            "VALUES (?,?,?,?,?,?)",
            (org_id, name, email, hash_password(pw), role, dept_id),
        )

    plan_id = conn.execute(
        "INSERT INTO strategic_plans (title, start_date, end_date, status) VALUES (?,?,?,?)",
        ("FY2026 Marketing Plan", "2026-01-01", "2026-12-31", "Active"),
    ).lastrowid
    bo_id = conn.execute(
        "INSERT INTO business_objectives (plan_id, title, description, owner_id, status) "
        "VALUES (?,?,?,?,?)",
        (plan_id, "Increase annual revenue by 25%", "Grow top-line revenue", 1, "Active"),
    ).lastrowid
    mo_id = conn.execute(
        "INSERT INTO marketing_objectives "
        "(business_objective_id, title, description, owner_id, target_value, current_value, unit, due_date, status) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (bo_id, "Generate 3,000 qualified leads", "Lead gen across all channels",
         2, 3000, 850, "leads", "2026-12-31", "Active"),
    ).lastrowid

    channels = ["Instagram", "TikTok", "Facebook", "Email", "WhatsApp",
                "Google Ads", "Website", "Word of Mouth"]
    for ch in channels:
        conn.execute("INSERT INTO marketing_channels (name) VALUES (?)", (ch,))

    for kpi in [
        ("Leads Generated", "Total qualified leads per month", "Higher is better", "leads", 2),
        ("Customer Acquisition Cost", "Avg cost to acquire a customer", "Lower is better", "USD", 5),
        ("Email Open Rate", "Percentage of emails opened", "Higher is better", "%", 6),
    ]:
        conn.execute(
            "INSERT INTO kpis (name, definition, formula_type, unit, owner_id) VALUES (?,?,?,?,?)",
            kpi,
        )
    conn.execute(
        "INSERT INTO kpi_targets (kpi_id, period_start, period_end, target_value) "
        "VALUES (1, '2026-01-01', '2026-01-31', 300)"
    )
    conn.execute(
        "INSERT INTO kpi_measurements (kpi_id, period_start, period_end, actual_value, recorded_by) "
        "VALUES (1, '2026-01-01', '2026-01-31', 275, 2)"
    )

    camp_id = conn.execute(
        "INSERT INTO campaigns "
        "(name, description, marketing_objective_id, owner_id, campaign_type, status, "
        " start_date, end_date, target_audience, expected_results) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Q1 Social Launch", "Q1 multi-channel campaign", mo_id, 4, "Digital",
         "Active", "2026-01-15", "2026-03-31", "Millennials 25-40", "500 leads"),
    ).lastrowid
    conn.execute(
        "INSERT INTO campaign_channels (campaign_id, channel_id) VALUES (?,?)",
        (camp_id, 1),
    )
    conn.execute(
        "INSERT INTO campaign_channels (campaign_id, channel_id) VALUES (?,?)",
        (camp_id, 2),
    )

    for t in [
        ("Design Q1 banners", "Create 10 Instagram stories", camp_id, 6, "High", "In Progress",
         "2026-01-10", "2026-01-20"),
        ("Schedule TikTok videos", "5 videos for launch", camp_id, 4, "Medium", "To Do",
         "2026-01-15", "2026-02-01"),
    ]:
        conn.execute(
            "INSERT INTO tasks (title, description, campaign_id, assigned_to, priority, status, "
            "                   start_date, due_date) VALUES (?,?,?,?,?,?,?,?)",
            t,
        )

    bud_id = conn.execute(
        "INSERT INTO budgets (name, period_start, period_end, total_amount, status) "
        "VALUES (?,?,?,?,?)",
        ("Q1 2026 Marketing Budget", "2026-01-01", "2026-03-31", 50000, "Approved"),
    ).lastrowid
    conn.execute(
        "INSERT INTO budget_allocations (budget_id, campaign_id, category, amount) "
        "VALUES (?,?,?,?)",
        (bud_id, camp_id, "Advertising", 15000),
    )
    conn.execute(
        "INSERT INTO expenses (campaign_id, budget_id, category, description, amount, "
        "                      expense_date, status, submitted_by) VALUES (?,?,?,?,?,?,?,?)",
        (camp_id, bud_id, "Advertising", "Instagram ads week 1", 1200,
         "2026-01-18", "Approved", 4),
    )

    conn.execute(
        "INSERT INTO competitors (name, website, notes) VALUES (?,?,?)",
        ("Rival Co", "rival.co", "Strong Instagram presence"),
    )
    conn.execute(
        "INSERT INTO research_projects (title, owner_id, status, findings, recommendation) "
        "VALUES (?,?,?,?,?)",
        ("Q1 Customer Survey", 5, "Active",
         "Customers want faster delivery", "Improve logistics communication"),
    )

    conn.commit()


def init_db():
    is_new = not os.path.exists(DB_PATH)
    with get_conn() as c:
        c.executescript(SCHEMA)
        c.commit()
        if is_new:
            seed(c)


init_db()


# ═══════════════════════════════════════════════════════════════
# ACCESS CONTROL AND SYSTEM CONFIGURATION
# ═══════════════════════════════════════════════════════════════
DEFAULT_PAGES = [
    "Dashboard", "Strategic Plans", "Objectives", "KPIs", "Campaigns",
    "Tasks", "Budgets & Expenses", "Market Intelligence", "Content Assets",
    "Approvals", "Reports", "Team", "Audit Log", "Settings",
]

ADMIN_ROLES = {"CEO", "Marketing Executive", "System Administrator"}

# Default access is deliberately conservative for finance and administration.
# These are module-level permissions; they are not a substitute for row-level
# data isolation in every SQL query.
ROLE_PAGE_DEFAULTS = {
    "CEO": set(DEFAULT_PAGES),
    "Marketing Executive": set(DEFAULT_PAGES),
    "System Administrator": set(DEFAULT_PAGES),
    "Marketing Manager": set(DEFAULT_PAGES) - {"Team", "Audit Log", "Settings"},
    "Campaign Manager": {"Dashboard", "Objectives", "KPIs", "Campaigns", "Tasks", "Content Assets", "Approvals", "Reports"},
    "Digital Marketing Specialist": {"Dashboard", "Campaigns", "Tasks", "Market Intelligence", "Content Assets", "Reports"},
    "Content Creator": {"Dashboard", "Campaigns", "Tasks", "Content Assets", "Reports"},
    "Graphic Designer": {"Dashboard", "Campaigns", "Tasks", "Content Assets"},
    "Research Analyst": {"Dashboard", "Objectives", "KPIs", "Market Intelligence", "Reports"},
    "Finance Officer": {"Dashboard", "Budgets & Expenses", "Reports", "Approvals"},
    "Marketing Assistant": {"Dashboard", "Campaigns", "Tasks", "Content Assets"},
}


def ensure_configuration():
    """Seed role permissions and baseline settings without overwriting edits."""
    defaults = {
        "organisation_name": "Delma Inc",
        "currency": "USD",
        "timezone": "Africa/Harare",
        "theme": "Light",
    }
    for key, value in defaults.items():
        execute(
            "INSERT OR IGNORE INTO app_settings(setting_key, setting_value) VALUES (?, ?)",
            (key, value),
        )
    for role in ROLES:
        allowed = ROLE_PAGE_DEFAULTS.get(role, {"Dashboard"})
        for page_name in DEFAULT_PAGES:
            can_view = int(page_name in allowed)
            can_edit = int(can_view and role not in {"Research Analyst"})
            execute(
                "INSERT OR IGNORE INTO role_permissions(role, page, can_view, can_edit) VALUES (?, ?, ?, ?)",
                (role, page_name, can_view, can_edit),
            )


def get_setting(key, default=""):
    rows = query("SELECT setting_value FROM app_settings WHERE setting_key=?", (key,))
    return str(rows.iloc[0]["setting_value"]) if not rows.empty else default


def can_access(page_name):
    user = st.session_state.get("user")
    if not user:
        return False
    if user.get("role") in ADMIN_ROLES:
        return True
    rows = query(
        "SELECT can_view FROM role_permissions WHERE role=? AND page=?",
        (user.get("role"), page_name),
    )
    return bool(not rows.empty and int(rows.iloc[0]["can_view"]) == 1)


ensure_configuration()


# ═══════════════════════════════════════════════════════════════
# PDF HELPERS
# ═══════════════════════════════════════════════════════════════
def _register_pdf_fonts():
    candidates = [
        ("CenturyGothic", r"C:\\Windows\\Fonts\\GOTHIC.TTF"),
        ("CenturyGothicBold", r"C:\\Windows\\Fonts\\GOTHICB.TTF"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    return ("CenturyGothic" if "CenturyGothic" in pdfmetrics.getRegisteredFontNames() else "Helvetica",
            "CenturyGothicBold" if "CenturyGothicBold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold")

def _pdf_styles():
    regular, bold = _register_pdf_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleBlue", parent=styles["Title"],
        textColor=colors.HexColor("#1e40af"),
        fontName=bold, fontSize=20, leading=25, spaceAfter=7, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="SubHeader", parent=styles["Heading2"],
        textColor=colors.HexColor("#0f172a"),
        fontName=bold, fontSize=12, leading=16, spaceBefore=12, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Meta", parent=styles["Normal"],
        fontName=regular, fontSize=8.5, leading=12, textColor=colors.HexColor("#64748b"),
    ))
    return styles


def _pdf_table(data, col_widths=None):
    regular, bold = _register_pdf_fonts()
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), regular),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("ALIGN", (0, 1), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _pdf_header_footer(canvas, doc, user_name="", user_role=""):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(colors.HexColor("#040713"))
    canvas.rect(0, h - 1.2 * cm, w, 1.2 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    _, pdf_bold = _register_pdf_fonts()
    pdf_regular, _ = _register_pdf_fonts()
    canvas.setFont(pdf_bold, 11)
    canvas.drawString(1.5 * cm, h - 0.85 * cm, "Marketing Management System")
    canvas.setFont(pdf_regular, 7.5)
    canvas.drawRightString(
        w - 1.5 * cm, h - 0.85 * cm,
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont(pdf_regular, 7.5)
    canvas.drawString(
        1.5 * cm, 1 * cm,
        f"Requested By: {user_name} ({user_role})",
    )
    canvas.drawRightString(w - 1.5 * cm, 1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_report_pdf(title: str, sections: list,
                     user_name: str = "", user_role: str = "",
                     period_start=None, period_end=None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=title,
    )
    styles = _pdf_styles()
    story = [
        Paragraph(title, styles["TitleBlue"]),
        Paragraph(
            f"Report period: "
            f"{(period_start or date.today().replace(day=1)).strftime('%d %b %Y')} — "
            f"{(period_end or date.today()).strftime('%d %b %Y')}",
            styles["Meta"],
        ),
        Spacer(1, 0.4 * cm),
    ]

    for sec in sections:
        if sec.get("heading"):
            story.append(Paragraph(sec["heading"], styles["SubHeader"]))
        if sec.get("paragraph"):
            story.append(Paragraph(sec["paragraph"], styles["Normal"]))
            story.append(Spacer(1, 0.2 * cm))
            
        tbl = sec.get("table")
        if tbl and tbl.get("rows"):
            data = [tbl["headers"]] + [
                [str(c) if c is not None else "" for c in row]
                for row in tbl["rows"]
            ]
            story.append(_pdf_table(data, tbl.get("col_widths")))
            story.append(Spacer(1, 0.3 * cm))

    def _hf(canvas, doc):
        _pdf_header_footer(canvas, doc, user_name, user_role)

    doc.build(story, onFirstPage=_hf, onLaterPages=_hf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# APPLICATION STYLES
# ═══════════════════════════════════════════════════════════════
def inject_styles():
    """Apply a consistent navy-on-light DMMS theme to the app and login screen."""
    st.markdown(
        """
        <style>
        :root {
            --dmms-navy: #10243A;
            --dmms-blue: #173B5E;
            --dmms-accent: #2F6B9A;
            --dmms-bg: #F4F7FA;
            --dmms-border: #D5DFE9;
            --dmms-text: #10243A;
        }

        html, body, [class*="css"], [data-testid="stAppViewContainer"],
        [data-testid="stMarkdownContainer"], label, p, span, div {
            font-family: "Century Gothic", "CenturyGothic", "AppleGothic",
                         "URW Gothic", Arial, sans-serif;
        }
        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
            background: var(--dmms-bg) !important;
            color: var(--dmms-navy) !important;
        }
        [data-testid="stHeader"] {
            background: rgba(244,247,250,.96) !important;
        }
        h1, h2, h3, h4, h5, h6,
        p, label, [data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"], [data-testid="stWidgetLabel"] {
            color: var(--dmms-navy) !important;
        }

        /* Sidebar remains a contrasting navy navigation rail. */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #10243A 0%, #173B5E 100%) !important;
        }
        [data-testid="stSidebar"] * { color: #F5F8FC !important; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            padding: .38rem .55rem;
            border-radius: 7px;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background: rgba(255,255,255,.12);
        }

        /* Inputs and selection controls use the same light background as the app. */
        input, textarea,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea,
        [data-baseweb="select"] > div,
        [data-testid="stDateInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stNumberInput"] input {
            background: var(--dmms-bg) !important;
            color: var(--dmms-navy) !important;
            -webkit-text-fill-color: var(--dmms-navy) !important;
            border-color: var(--dmms-border) !important;
            caret-color: var(--dmms-navy) !important;
        }
        input::placeholder, textarea::placeholder {
            color: #607286 !important;
            -webkit-text-fill-color: #607286 !important;
            opacity: 1 !important;
        }
        [data-baseweb="select"] *, [data-baseweb="popover"] *,
        [role="listbox"] *, [role="option"] {
            color: var(--dmms-navy) !important;
        }
        [data-baseweb="popover"], [role="listbox"] {
            background: var(--dmms-bg) !important;
        }
        [data-testid="stCheckbox"] label,
        [data-testid="stRadio"] label,
        [data-testid="stToggle"] label,
        [data-testid="stSlider"] label {
            color: var(--dmms-navy) !important;
        }
        [data-testid="stCheckbox"] svg,
        [data-testid="stRadio"] svg { color: var(--dmms-navy) !important; }

        /* Buttons: navy text on the shared light surface. */
        div.stButton > button, div.stDownloadButton > button,
        [data-testid="stFormSubmitButton"] button,
        button[kind="primary"], button[kind="secondary"] {
            background: var(--dmms-bg) !important;
            color: var(--dmms-navy) !important;
            border: 1px solid #B9C8D8 !important;
            border-radius: 9px !important;
            font-weight: 700 !important;
            transition: all .15s ease-in-out;
        }
        div.stButton > button:hover, div.stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            background: #E8EEF4 !important;
            color: var(--dmms-navy) !important;
            border-color: var(--dmms-accent) !important;
        }

        [data-testid="stMetric"] {
            background: #FFFFFF;
            color: var(--dmms-navy) !important;
            border: 1px solid var(--dmms-border);
            border-radius: 11px;
            padding: 14px 16px;
            box-shadow: 0 2px 8px rgba(16,36,58,.045);
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
            color: var(--dmms-navy) !important;
        }
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border: 1px solid var(--dmms-border);
            border-radius: 9px;
            overflow: hidden;
        }
        div[data-testid="stForm"], div[data-testid="stExpander"] {
            background: var(--dmms-bg) !important;
            border: 1px solid var(--dmms-border) !important;
            border-radius: 12px !important;
        }

        /* Login experience */
        .dmms-login-heading {
            text-align: center;
            color: var(--dmms-navy);
            font-size: 2.15rem;
            font-weight: 800;
            letter-spacing: .08em;
            margin: .25rem 0 .25rem;
        }
        .dmms-login-subtitle {
            text-align: center;
            color: #536A80;
            font-size: .98rem;
            margin: 0 0 1.3rem;
        }
        .dmms-login-accent {
            width: 58px;
            height: 4px;
            border-radius: 10px;
            background: var(--dmms-accent);
            margin: .75rem auto 1.2rem;
        }
        [data-testid="stForm"] {
            box-shadow: 0 12px 34px rgba(16,36,58,.07);
            padding: 1.1rem 1.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════
def login_screen():
    """Render a centered, modern DMMS sign-in screen."""
    left, center, right = st.columns([1, 1.35, 1])
    with center:
        st.markdown(
            """
            <div class="dmms-login-heading">DMMS</div>
            <div class="dmms-login-accent"></div>
            <div class="dmms-login-subtitle">
                Marketing Management System<br>
                Sign in to access your workspace
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login", clear_on_submit=False):
            st.markdown("### Welcome back")
            email = st.text_input("Email address", placeholder="name@company.com").strip().lower()
            pw = st.text_input("Password", type="password", placeholder="Enter your password")
            ok = st.form_submit_button("Sign in", type="primary", use_container_width=True)

        if ok:
            if not email or not pw:
                st.error("Enter both your email and password.")
            else:
                rows = query(
                    "SELECT * FROM users WHERE LOWER(email)=? AND is_active=1",
                    (email,),
                )
                if rows.empty:
                    st.error(
                        f"No active account found for **{email}**. "
                        "Check the email address or contact your system administrator."
                    )
                elif not verify_password(pw, rows.iloc[0]["password_hash"]):
                    st.error("The password is incorrect. Please try again.")
                else:
                    u = rows.iloc[0].to_dict()
                    st.session_state.user = u
                    log_audit(u["user_id"], "LOGIN")
                    st.rerun()

        with st.expander("Demo accounts and login help"):
            st.caption(
                "Demo password: `admin123`\\n\\n"
                "• ceo@delma.inc (CEO)\\n"
                "• exec@delma.inc (Marketing Executive)\\n"
                "• manager@delma.inc (Marketing Manager)\\n"
                "• campaign@delma.inc (Campaign Manager)\\n"
                "• finance@delma.inc (Finance Officer)\\n"
                "• content@delma.inc (Content Creator)"
            )
            st.caption(
                "If you are unable to sign in, contact your system administrator. "
                "Database reset should only be performed during development because "
                "it permanently deletes application data."
            )


inject_styles()

if "user" not in st.session_state:
    login_screen()
    st.stop()

USER = st.session_state.user
IS_ADMIN = USER["role"] in ("CEO", "Marketing Executive", "System Administrator")
CAN_APPROVE = USER["role"] in (
    "CEO", "Marketing Executive", "Marketing Manager", "Finance Officer",
)


# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption(f"{USER['full_name']}  \n_{USER['role']}_")
    st.divider()
    PAGES = [p for p in DEFAULT_PAGES if can_access(p)]
    if not PAGES:
        st.error("Your account has not been granted access to any module. Contact an administrator.")
        st.stop()
    page = st.radio("Navigate", PAGES, index=0, label_visibility="collapsed")
    st.divider()
    unread = query(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id=? AND is_read=0",
        (USER["user_id"],),
    ).iloc[0]["n"]
    with st.expander(f"🔔 Notifications ({unread})"):
        notifs = query(
            "SELECT * FROM notifications WHERE user_id=? "
            "ORDER BY notification_id DESC LIMIT 10",
            (USER["user_id"],),
        )
        if notifs.empty:
            st.caption("No notifications")
        else:
            for _, n in notifs.iterrows():
                st.markdown(f"- {n['message']}")
            if st.button("Mark all read"):
                execute(
                    "UPDATE notifications SET is_read=1 WHERE user_id=?",
                    (USER["user_id"],),
                )
                st.rerun()
    if st.button("🚪 Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════
def user_options():
    df = query(
        "SELECT user_id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    )
    return {f"{r.full_name}": int(r.user_id) for r in df.itertuples()}


def channel_options():
    df = query("SELECT channel_id, name FROM marketing_channels ORDER BY name")
    return {r.name: int(r.channel_id) for r in df.itertuples()}


def campaign_options():
    df = query("SELECT campaign_id, name FROM campaigns ORDER BY name")
    return {r.name: int(r.campaign_id) for r in df.itertuples()}


def budget_options():
    df = query("SELECT budget_id, name FROM budgets ORDER BY name")
    return {r.name: int(r.budget_id) for r in df.itertuples()}


def compute_kpi_achievement(actual, target, formula_type):
    if target in (0, None):
        return 0.0
    if formula_type == "Higher is better":
        return actual / target * 100
    if formula_type == "Lower is better":
        return (target / actual * 100) if actual > 0 else 0.0
    return 100.0 if actual == target else 0.0


# ═══════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.title("Executive Dashboard")

    kpis = query("""
        SELECT k.kpi_id, k.name, k.formula_type, k.unit,
               (SELECT target_value FROM kpi_targets t WHERE t.kpi_id=k.kpi_id
                 ORDER BY period_end DESC LIMIT 1) AS target,
               (SELECT actual_value FROM kpi_measurements m WHERE m.kpi_id=k.kpi_id
                 ORDER BY period_end DESC LIMIT 1) AS actual
        FROM kpis k
    """)
    campaigns = query("SELECT * FROM campaigns")
    tasks = query("SELECT * FROM tasks")
    budgets = query("SELECT * FROM budgets")
    expenses = query("SELECT * FROM expenses WHERE status='Approved'")

    total_budget = budgets["total_amount"].sum() if not budgets.empty else 0
    spent = expenses["amount"].sum() if not expenses.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Active Campaigns",
        int((campaigns["status"] == "Active").sum()) if not campaigns.empty else 0,
    )
    c2.metric(
        "Open Tasks",
        int((tasks["status"] != "Done").sum()) if not tasks.empty else 0,
    )
    c3.metric("Budget", f"${total_budget:,.0f}")
    c4.metric(
        "Spent", f"${spent:,.0f}",
        delta=f"{(spent/total_budget*100 if total_budget else 0):.1f}%",
    )

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("KPI Performance")
        if kpis.empty:
            st.info("No KPIs yet")
        else:
            kpis["achievement"] = kpis.apply(
                lambda r: compute_kpi_achievement(
                    r["actual"] or 0, r["target"] or 0, r["formula_type"]
                ),
                axis=1,
            )
            fig = px.bar(
                kpis, x="name", y="achievement", color="achievement",
                color_continuous_scale="RdYlGn", range_color=[0, 150],
            )
            fig.add_hline(y=100, line_dash="dash", line_color="white")
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Campaign Status")
        if campaigns.empty:
            st.info("No campaigns yet")
        else:
            counts = campaigns.groupby("status").size().reset_index(name="count")
            fig = px.pie(counts, names="status", values="count", hole=0.4)
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Objectives Progress")
    objs = query("""
        SELECT mo.title, mo.target_value, mo.current_value, mo.unit,
               bo.title AS business_objective
        FROM marketing_objectives mo
        JOIN business_objectives bo ON bo.objective_id = mo.business_objective_id
    """)
    if objs.empty:
        st.info("No objectives yet")
    else:
        objs["progress"] = (
            objs["current_value"] / objs["target_value"].replace(0, 1) * 100
        ).clip(0, 150)
        for _, o in objs.iterrows():
            st.markdown(
                f"**{o['title']}** — "
                f"{o['current_value']:,.0f}/{o['target_value']:,.0f} {o['unit']}"
            )
            st.progress(min(o["progress"] / 100, 1.0))


# ═══════════════════════════════════════════════════════════════
# PAGE: STRATEGIC PLANS
# ═══════════════════════════════════════════════════════════════
elif page == "Strategic Plans":
    st.title("Strategic Plans")
    with st.form("new_plan"):
        c1, c2, c3 = st.columns([2, 1, 1])
        title = c1.text_input("Plan title")
        sd = c2.date_input("Start", date.today())
        ed = c3.date_input(
            "End", date.today().replace(year=date.today().year + 1)
        )
        if st.form_submit_button("Create plan", type="primary") and title:
            pid = execute(
                "INSERT INTO strategic_plans (title, start_date, end_date) "
                "VALUES (?,?,?)",
                (title, sd.isoformat(), ed.isoformat()),
            )
            log_audit(USER["user_id"], "CREATE", "strategic_plan", pid, title)
            st.success("Plan created")
            st.rerun()

    plans = query("SELECT * FROM strategic_plans ORDER BY start_date DESC")
    st.dataframe(plans, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: OBJECTIVES
# ═══════════════════════════════════════════════════════════════
elif page == "Objectives":
    st.title("Objectives (Business → Marketing)")
    tab1, tab2 = st.tabs(["Business Objectives", "Marketing Objectives"])

    with tab1:
        plans = query("SELECT plan_id, title FROM strategic_plans")
        if plans.empty:
            st.warning("Create a strategic plan first")
        else:
            plan_map = {r.title: int(r.plan_id) for r in plans.itertuples()}
            with st.form("bo_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                plan = c1.selectbox("Plan", list(plan_map))
                owner = c2.selectbox("Owner", list(user_options()))
                title = st.text_input("Objective title")
                desc = st.text_area("Description")
                if st.form_submit_button(
                    "Add business objective", type="primary"
                ) and title:
                    oid = execute(
                        "INSERT INTO business_objectives "
                        "(plan_id, title, description, owner_id) VALUES (?,?,?,?)",
                        (plan_map[plan], title, desc, user_options()[owner]),
                    )
                    log_audit(
                        USER["user_id"], "CREATE", "business_objective", oid, title
                    )
                    st.rerun()
        st.dataframe(query("""
            SELECT bo.objective_id, bo.title, bo.description,
                   sp.title AS plan, u.full_name AS owner
            FROM business_objectives bo
            JOIN strategic_plans sp ON sp.plan_id = bo.plan_id
            LEFT JOIN users u ON u.user_id = bo.owner_id
        """), use_container_width=True, hide_index=True)

    with tab2:
        bos = query("SELECT objective_id, title FROM business_objectives")
        if bos.empty:
            st.warning("Add a business objective first")
        else:
            bo_map = {r.title: int(r.objective_id) for r in bos.itertuples()}
            with st.form("mo_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                bo = c1.selectbox("Business objective", list(bo_map))
                owner = c2.selectbox("Owner", list(user_options()))
                title = st.text_input("Marketing objective title")
                desc = st.text_area("Description")
                c3, c4, c5 = st.columns(3)
                target = c3.number_input("Target", min_value=0.0, value=1000.0)
                unit = c4.text_input("Unit", value="leads")
                due = c5.date_input(
                    "Due date", date.today() + timedelta(days=90)
                )
                if st.form_submit_button(
                    "Add marketing objective", type="primary"
                ) and title:
                    mid = execute(
                        "INSERT INTO marketing_objectives "
                        "(business_objective_id, title, description, owner_id, "
                        " target_value, unit, due_date) VALUES (?,?,?,?,?,?,?)",
                        (bo_map[bo], title, desc, user_options()[owner],
                         target, unit, due.isoformat()),
                    )
                    log_audit(
                        USER["user_id"], "CREATE",
                        "marketing_objective", mid, title,
                    )
                    st.rerun()
        st.dataframe(query("""
            SELECT mo.marketing_objective_id, mo.title,
                   bo.title AS business_objective,
                   mo.target_value, mo.current_value, mo.unit,
                   u.full_name AS owner
            FROM marketing_objectives mo
            JOIN business_objectives bo
              ON bo.objective_id = mo.business_objective_id
            LEFT JOIN users u ON u.user_id = mo.owner_id
        """), use_container_width=True, hide_index=True)

        st.subheader("Update progress")
        mos = query(
            "SELECT marketing_objective_id, title, current_value "
            "FROM marketing_objectives"
        )
        if not mos.empty:
            m = st.selectbox(
                "Marketing objective", mos["title"].tolist(), key="mo_progress"
            )
            row = mos[mos["title"] == m].iloc[0]
            new_val = st.number_input(
                "Current value", value=float(row["current_value"])
            )
            if st.button("Save progress"):
                execute(
                    "UPDATE marketing_objectives SET current_value=? "
                    "WHERE marketing_objective_id=?",
                    (new_val, int(row["marketing_objective_id"])),
                )
                log_audit(
                    USER["user_id"], "UPDATE", "marketing_objective",
                    int(row["marketing_objective_id"]), f"current={new_val}",
                )
                st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE: KPIs
# ═══════════════════════════════════════════════════════════════
elif page == "KPIs":
    st.title("KPI Management")
    tab1, tab2, tab3 = st.tabs(["Definitions", "Targets", "Measurements"])

    with tab1:
        with st.form("kpi_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("KPI name")
            formula = c2.selectbox("Formula type", KPI_TYPES)
            definition = st.text_area("Definition")
            c3, c4 = st.columns(2)
            unit = c3.text_input("Unit", value="units")
            owner = c4.selectbox("Owner", list(user_options()))
            if st.form_submit_button("Create KPI", type="primary") and name:
                kid = execute(
                    "INSERT INTO kpis "
                    "(name, definition, formula_type, unit, owner_id) "
                    "VALUES (?,?,?,?,?)",
                    (name, definition, formula, unit, user_options()[owner]),
                )
                log_audit(USER["user_id"], "CREATE", "kpi", kid, name)
                st.rerun()
        st.dataframe(query("""
            SELECT k.kpi_id, k.name, k.formula_type, k.unit,
                   u.full_name AS owner
            FROM kpis k LEFT JOIN users u ON u.user_id = k.owner_id
        """), use_container_width=True, hide_index=True)

    with tab2:
        kpis = query("SELECT kpi_id, name FROM kpis")
        if kpis.empty:
            st.info("Create a KPI first")
        else:
            kpi_map = {r.name: int(r.kpi_id) for r in kpis.itertuples()}
            with st.form("target_form", clear_on_submit=True):
                kpi = st.selectbox("KPI", list(kpi_map))
                c1, c2 = st.columns(2)
                ps = c1.date_input("Period start", date.today().replace(day=1))
                pe = c2.date_input("Period end", date.today())
                target = st.number_input(
                    "Target value", min_value=0.0, value=100.0
                )
                if st.form_submit_button("Add target", type="primary"):
                    execute(
                        "INSERT INTO kpi_targets "
                        "(kpi_id, period_start, period_end, target_value) "
                        "VALUES (?,?,?,?)",
                        (kpi_map[kpi], ps.isoformat(), pe.isoformat(), target),
                    )
                    st.rerun()
        st.dataframe(query("""
            SELECT t.target_id, k.name, t.period_start, t.period_end,
                   t.target_value
            FROM kpi_targets t JOIN kpis k ON k.kpi_id = t.kpi_id
            ORDER BY t.period_end DESC
        """), use_container_width=True, hide_index=True)

    with tab3:
        kpis = query("SELECT kpi_id, name FROM kpis")
        if kpis.empty:
            st.info("Create a KPI first")
        else:
            kpi_map = {r.name: int(r.kpi_id) for r in kpis.itertuples()}
            with st.form("measure_form", clear_on_submit=True):
                kpi = st.selectbox("KPI", list(kpi_map))
                c1, c2 = st.columns(2)
                ps = c1.date_input(
                    "Period start", date.today().replace(day=1), key="mp_s"
                )
                pe = c2.date_input("Period end", date.today(), key="mp_e")
                actual = st.number_input(
                    "Actual value", min_value=0.0, value=0.0
                )
                if st.form_submit_button(
                    "Record measurement", type="primary"
                ):
                    execute(
                        "INSERT INTO kpi_measurements "
                        "(kpi_id, period_start, period_end, actual_value, recorded_by) "
                        "VALUES (?,?,?,?,?)",
                        (kpi_map[kpi], ps.isoformat(), pe.isoformat(),
                         actual, USER["user_id"]),
                    )
                    log_audit(
                        USER["user_id"], "CREATE",
                        "kpi_measurement", None, f"kpi={kpi}",
                    )
                    st.rerun()
        st.dataframe(query("""
            SELECT m.measurement_id, k.name, m.period_start, m.period_end,
                   m.actual_value
            FROM kpi_measurements m JOIN kpis k ON k.kpi_id = m.kpi_id
            ORDER BY m.period_end DESC
        """), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: CAMPAIGNS
# ═══════════════════════════════════════════════════════════════
elif page == "Campaigns":
    st.title("Campaign Management")

    with st.expander("Create campaign", expanded=False):
        mos = query(
            "SELECT marketing_objective_id, title FROM marketing_objectives"
        )
        mo_map = (
            {r.title: int(r.marketing_objective_id)
             for r in mos.itertuples()}
            if not mos.empty else {}
        )
        with st.form("camp_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Campaign name")
            ctype = c2.selectbox(
                "Type", ["Digital", "Social", "Email", "Event", "PR", "Mixed"]
            )
            c3, c4 = st.columns(2)
            owner = c3.selectbox("Owner", list(user_options()))
            mo = c4.selectbox(
                "Marketing objective", ["—"] + list(mo_map.keys())
            )
            desc = st.text_area("Description")
            c5, c6 = st.columns(2)
            sd = c5.date_input("Start", date.today())
            ed = c6.date_input("End", date.today() + timedelta(days=30))
            audience = st.text_input("Target audience")
            expected = st.text_input("Expected results")
            channels_sel = st.multiselect(
                "Channels", list(channel_options().keys())
            )
            if st.form_submit_button(
                "Create campaign", type="primary"
            ) and name:
                cid = execute(
                    """INSERT INTO campaigns
                       (name, description, marketing_objective_id, owner_id,
                        campaign_type, status, start_date, end_date,
                        target_audience, expected_results)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (name, desc, mo_map.get(mo), user_options()[owner],
                     ctype, "Draft", sd.isoformat(), ed.isoformat(),
                     audience, expected),
                )
                ch_map = channel_options()
                for ch in channels_sel:
                    execute(
                        "INSERT INTO campaign_channels "
                        "(campaign_id, channel_id) VALUES (?,?)",
                        (cid, ch_map[ch]),
                    )
                log_audit(USER["user_id"], "CREATE", "campaign", cid, name)
                st.success("Campaign created")
                st.rerun()

    df = query("""
        SELECT c.campaign_id, c.name, c.campaign_type, c.status,
               c.start_date, c.end_date,
               u.full_name AS owner, mo.title AS objective
        FROM campaigns c
        LEFT JOIN users u ON u.user_id = c.owner_id
        LEFT JOIN marketing_objectives mo
          ON mo.marketing_objective_id = c.marketing_objective_id
        ORDER BY c.campaign_id DESC
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.subheader("Update status")
        sel = st.selectbox(
            "Campaign", df["name"].tolist(), key="camp_status"
        )
        row = df[df["name"] == sel].iloc[0]
        new_status = st.selectbox(
            "New status", CAMPAIGN_STATUSES,
            index=CAMPAIGN_STATUSES.index(row["status"]),
        )
        if st.button("Save status"):
            execute(
                "UPDATE campaigns SET status=? WHERE campaign_id=?",
                (new_status, int(row["campaign_id"])),
            )
            log_audit(
                USER["user_id"], "UPDATE", "campaign",
                int(row["campaign_id"]), f"status={new_status}",
            )
            if new_status == "Submitted":
                approvers = query(
                    "SELECT user_id FROM users WHERE role IN "
                    "('CEO','Marketing Executive','Marketing Manager') "
                    "AND is_active=1"
                )
                approver_id = (
                    int(approvers.iloc[0]["user_id"])
                    if not approvers.empty else USER["user_id"]
                )
                execute(
                    "INSERT INTO approvals "
                    "(entity_type, entity_id, requested_by, approver_id, status) "
                    "VALUES ('campaign', ?, ?, ?, 'Pending')",
                    (int(row["campaign_id"]), USER["user_id"], approver_id),
                )
                notify(
                    approver_id,
                    f"Campaign '{sel}' submitted for approval",
                )
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE: TASKS
# ═══════════════════════════════════════════════════════════════
elif page == "Tasks":
    st.title("✅ Task Management")
    with st.expander("➕ Create task", expanded=False):
        camps = campaign_options()
        with st.form("task_form", clear_on_submit=True):
            title = st.text_input("Task title")
            desc = st.text_area("Description")
            c1, c2 = st.columns(2)
            camp = c1.selectbox("Campaign", ["—"] + list(camps.keys()))
            assignee = c2.selectbox("Assigned to", list(user_options()))
            c3, c4 = st.columns(2)
            pri = c3.selectbox("Priority", PRIORITIES, index=1)
            status = c4.selectbox("Status", TASK_STATUSES)
            c5, c6 = st.columns(2)
            sd = c5.date_input("Start", date.today())
            dd = c6.date_input("Due", date.today() + timedelta(days=7))
            if st.form_submit_button(
                "Create task", type="primary"
            ) and title:
                tid = execute(
                    """INSERT INTO tasks
                       (title, description, campaign_id, assigned_to,
                        priority, status, start_date, due_date)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (title, desc, camps.get(camp), user_options()[assignee],
                     pri, status, sd.isoformat(), dd.isoformat()),
                )
                log_audit(USER["user_id"], "CREATE", "task", tid, title)
                notify(user_options()[assignee], f"New task assigned: {title}")
                st.rerun()

    df = query("""
        SELECT t.task_id, t.title, t.priority, t.status, t.due_date,
               u.full_name AS assignee, c.name AS campaign
        FROM tasks t
        LEFT JOIN users u ON u.user_id = t.assigned_to
        LEFT JOIN campaigns c ON c.campaign_id = t.campaign_id
        ORDER BY t.task_id DESC
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.subheader("Update task")
        sel = st.selectbox("Task", df["title"].tolist(), key="task_sel")
        row = df[df["title"] == sel].iloc[0]
        new_status = st.selectbox(
            "Status", TASK_STATUSES,
            index=TASK_STATUSES.index(row["status"]), key="task_status",
        )
        if st.button("Save"):
            execute(
                "UPDATE tasks SET status=? WHERE task_id=?",
                (new_status, int(row["task_id"])),
            )
            log_audit(
                USER["user_id"], "UPDATE", "task",
                int(row["task_id"]), f"status={new_status}",
            )
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE: BUDGETS & EXPENSES
# ═══════════════════════════════════════════════════════════════
elif page == "Budgets & Expenses":
    st.title("💰 Budgets & Expenses")
    tab1, tab2, tab3 = st.tabs(["Budgets", "Expenses", "Allocations"])

    with tab1:
        with st.form("budget_form", clear_on_submit=True):
            name = st.text_input("Budget name")
            c1, c2, c3 = st.columns(3)
            ps = c1.date_input(
                "Period start", date.today().replace(month=1, day=1)
            )
            pe = c2.date_input(
                "Period end", date.today().replace(month=12, day=31)
            )
            amt = c3.number_input(
                "Total amount", min_value=0.0, value=10000.0
            )
            if st.form_submit_button(
                "Create budget", type="primary"
            ) and name:
                bid = execute(
                    "INSERT INTO budgets "
                    "(name, period_start, period_end, total_amount) "
                    "VALUES (?,?,?,?)",
                    (name, ps.isoformat(), pe.isoformat(), amt),
                )
                log_audit(USER["user_id"], "CREATE", "budget", bid, name)
                st.rerun()
        st.dataframe(query("""
            SELECT b.budget_id, b.name, b.period_start, b.period_end,
                   b.total_amount, b.status,
                   COALESCE((SELECT SUM(amount) FROM expenses e
                             WHERE e.budget_id=b.budget_id
                               AND e.status='Approved'),0) AS spent
            FROM budgets b
        """), use_container_width=True, hide_index=True)

    with tab2:
        camps = campaign_options()
        buds = budget_options()
        with st.form("expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            camp = c1.selectbox("Campaign", ["—"] + list(camps.keys()))
            bud = c2.selectbox("Budget", ["—"] + list(buds.keys()))
            c3, c4 = st.columns(2)
            cat = c3.text_input("Category")
            amt = c4.number_input("Amount", min_value=0.0, value=100.0)
            desc = st.text_input("Description")
            edate = st.date_input("Expense date", date.today())
            if st.form_submit_button("Submit expense", type="primary"):
                eid = execute(
                    """INSERT INTO expenses
                       (campaign_id, budget_id, category, description,
                        amount, expense_date, submitted_by)
                       VALUES (?,?,?,?,?,?,?)""",
                    (camps.get(camp), buds.get(bud), cat, desc, amt,
                     edate.isoformat(), USER["user_id"]),
                )
                log_audit(
                    USER["user_id"], "CREATE", "expense", eid, f"${amt}"
                )
                finance = query(
                    "SELECT user_id FROM users WHERE role='Finance Officer' "
                    "AND is_active=1"
                )
                if not finance.empty:
                    notify(
                        int(finance.iloc[0]["user_id"]),
                        f"New expense submitted: ${amt}",
                    )
                st.rerun()
        st.dataframe(query("""
            SELECT e.expense_id, e.description, e.category, e.amount,
                   e.expense_date, e.status,
                   c.name AS campaign, u.full_name AS submitted_by
            FROM expenses e
            LEFT JOIN campaigns c ON c.campaign_id = e.campaign_id
            LEFT JOIN users u ON u.user_id = e.submitted_by
            ORDER BY e.expense_id DESC
        """), use_container_width=True, hide_index=True)

    with tab3:
        buds = budget_options()
        camps = campaign_options()
        if buds and camps:
            with st.form("alloc_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                bud = c1.selectbox("Budget", list(buds.keys()))
                camp = c2.selectbox("Campaign", ["—"] + list(camps.keys()))
                c3, c4 = st.columns(2)
                cat = c3.text_input("Category")
                amt = c4.number_input(
                    "Amount", min_value=0.0, value=500.0
                )
                if st.form_submit_button("Allocate", type="primary"):
                    execute(
                        "INSERT INTO budget_allocations "
                        "(budget_id, campaign_id, category, amount) "
                        "VALUES (?,?,?,?)",
                        (buds[bud], camps.get(camp), cat, amt),
                    )
                    st.rerun()
        st.dataframe(query("""
            SELECT a.allocation_id, b.name AS budget, c.name AS campaign,
                   a.category, a.amount
            FROM budget_allocations a
            LEFT JOIN budgets b ON b.budget_id = a.budget_id
            LEFT JOIN campaigns c ON c.campaign_id = a.campaign_id
        """), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: MARKET INTELLIGENCE
# ═══════════════════════════════════════════════════════════════
elif page == "Market Intelligence":
    st.title("Market Intelligence")
    tab1, tab2, tab3 = st.tabs(["Competitors", "Observations", "Research"])

    with tab1:
        with st.form("comp_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Competitor name")
            site = c2.text_input("Website")
            notes = st.text_area("Notes")
            if st.form_submit_button(
                "Add competitor", type="primary"
            ) and name:
                execute(
                    "INSERT INTO competitors (name, website, notes) "
                    "VALUES (?,?,?)",
                    (name, site, notes),
                )
                st.rerun()
        st.dataframe(
            query("SELECT * FROM competitors"),
            use_container_width=True, hide_index=True,
        )

    with tab2:
        comps = query("SELECT competitor_id, name FROM competitors")
        if comps.empty:
            st.info("Add a competitor first")
        else:
            comp_map = {r.name: int(r.competitor_id)
                        for r in comps.itertuples()}
            with st.form("obs_form", clear_on_submit=True):
                comp = st.selectbox("Competitor", list(comp_map))
                obs_date = st.date_input("Date", date.today())
                findings = st.text_area("Findings")
                if st.form_submit_button(
                    "Log observation", type="primary"
                ) and findings:
                    execute(
                        "INSERT INTO competitor_observations "
                        "(competitor_id, observed_date, findings) "
                        "VALUES (?,?,?)",
                        (comp_map[comp], obs_date.isoformat(), findings),
                    )
                    st.rerun()
        st.dataframe(query("""
            SELECT o.observation_id, c.name AS competitor,
                   o.observed_date, o.findings
            FROM competitor_observations o
            JOIN competitors c ON c.competitor_id = o.competitor_id
            ORDER BY o.observed_date DESC
        """), use_container_width=True, hide_index=True)

    with tab3:
        with st.form("research_form", clear_on_submit=True):
            title = st.text_input("Research project title")
            owner = st.selectbox("Owner", list(user_options()))
            findings = st.text_area("Findings")
            rec = st.text_area("Recommendation")
            if st.form_submit_button(
                "Create research", type="primary"
            ) and title:
                execute(
                    "INSERT INTO research_projects "
                    "(title, owner_id, findings, recommendation) "
                    "VALUES (?,?,?,?)",
                    (title, user_options()[owner], findings, rec),
                )
                st.rerun()
        st.dataframe(query("""
            SELECT r.research_id, r.title, u.full_name AS owner,
                   r.status, r.findings, r.recommendation
            FROM research_projects r
            LEFT JOIN users u ON u.user_id = r.owner_id
        """), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: CONTENT ASSETS
# ═══════════════════════════════════════════════════════════════
elif page == "Content Assets":
    st.title("Content Assets")
    with st.form("asset_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        title = c1.text_input("Asset title")
        atype = c2.selectbox(
            "Type", ["Image", "Video", "Copy", "Document", "Other"]
        )
        file_path = st.text_input("File path (or URL)")
        owner = st.selectbox("Owner", list(user_options()))
        status = st.selectbox(
            "Status", ["Draft", "Under Review", "Approved", "Published"]
        )
        if st.form_submit_button(
            "Add asset", type="primary"
        ) and title:
            execute(
                "INSERT INTO content_assets "
                "(title, asset_type, file_path, status, owner_id) "
                "VALUES (?,?,?,?,?)",
                (title, atype, file_path, status, user_options()[owner]),
            )
            st.rerun()
    st.dataframe(query("""
        SELECT a.asset_id, a.title, a.asset_type, a.status,
               u.full_name AS owner, a.created_at
        FROM content_assets a LEFT JOIN users u ON u.user_id = a.owner_id
    """), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# PAGE: APPROVALS
# ═══════════════════════════════════════════════════════════════
elif page == "Approvals":
    st.title("✔️ Approvals")
    pending = query("""
        SELECT a.approval_id, a.entity_type, a.entity_id, a.status,
               a.created_at, u.full_name AS requested_by
        FROM approvals a LEFT JOIN users u ON u.user_id = a.requested_by
        ORDER BY a.approval_id DESC
    """)
    st.dataframe(pending, use_container_width=True, hide_index=True)

    if not pending.empty and CAN_APPROVE:
        st.subheader("Decide")
        open_pending = pending[pending["status"] == "Pending"]
        if open_pending.empty:
            st.info("No pending approvals.")
        else:
            sel = st.selectbox(
                "Approval ID", open_pending["approval_id"].tolist()
            )
            decision = st.radio(
                "Decision", ["Approved", "Rejected"], horizontal=True
            )
            notes = st.text_area("Notes")
            if st.button("Submit decision", type="primary"):
                execute(
                    "UPDATE approvals SET status=?, decision_notes=?, "
                    "approver_id=?, decided_at=datetime('now') "
                    "WHERE approval_id=?",
                    (decision, notes, USER["user_id"], int(sel)),
                )
                row = pending[pending["approval_id"] == sel].iloc[0]
                if row["entity_type"] == "campaign":
                    execute(
                        "UPDATE campaigns SET status=? WHERE campaign_id=?",
                        ("Approved" if decision == "Approved" else "Rejected",
                         int(row["entity_id"])),
                    )
                    camp = query(
                        "SELECT owner_id, name FROM campaigns "
                        "WHERE campaign_id=?",
                        (int(row["entity_id"]),),
                    )
                    if not camp.empty:
                        notify(
                            int(camp.iloc[0]["owner_id"]),
                            f"Your campaign '{camp.iloc[0]['name']}' "
                            f"was {decision.lower()}",
                        )
                log_audit(
                    USER["user_id"], decision.upper(),
                    "approval", int(sel), notes,
                )
                st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE: REPORTS
# ═══════════════════════════════════════════════════════════════
elif page == "Reports":
    st.title("Reports")
    st.caption("Export as PDF (formatted) or CSV (raw data)")
    r1, r2 = st.columns(2)
    period_start = r1.date_input("Reporting period — start", date.today().replace(day=1), key="report_start")
    period_end = r2.date_input("Reporting period — end", date.today(), key="report_end")
    if period_start > period_end:
        st.error("The reporting period start must be on or before the end date.")
        st.stop()

    tab1, tab2, tab3 = st.tabs([
        "Campaign Performance", "Budget Report", "KPI Report"
    ])

    # ── Campaign Performance ─────────────────────────────────
    with tab1:
        df = query("""
            SELECT c.name AS Campaign, c.status AS Status,
                   c.start_date AS Start, c.end_date AS "End",
                   COALESCE(u.full_name,'—') AS Owner,
                   (SELECT COALESCE(SUM(amount),0) FROM expenses e
                     WHERE e.campaign_id=c.campaign_id
                       AND e.status='Approved'
                       AND e.expense_date BETWEEN ? AND ?) AS Spend
            FROM campaigns c LEFT JOIN users u ON u.user_id = c.owner_id
        """, (period_start.isoformat(), period_end.isoformat()))
        if not df.empty:
            df = df[(df["Start"].fillna("") <= period_end.isoformat()) &
                    (df["End"].fillna("9999-12-31") >= period_start.isoformat())]
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            total_spend = float(df["Spend"].sum())
            total = len(df)
            by_status = df.groupby("Status").size().to_dict()

            sections = [
                {"heading": "Summary",
                 "paragraph": (
                     f"<b>Total campaigns:</b> {total} &nbsp;|&nbsp; "
                     f"<b>Total approved spend:</b> ${total_spend:,.2f}"
                 )},
               
                {"heading": "Campaigns",
                 "table": {
                     "headers": list(df.columns),
                     "rows": df.values.tolist(),
                     "col_widths":[8*cm,2*cm,2*cm,2*cm,2*cm,2*cm],
                 }},
            ]
            pdf_bytes = build_report_pdf(
                "Campaign Performance Report", sections,
                USER["full_name"], USER["role"],
            )
            c1, c2 = st.columns(2)
            c1.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name=f"campaign_report_{date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
            c2.download_button(
                "📊 Download CSV",
                data=df.to_csv(index=False),
                file_name=f"campaign_report_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # ── Budget Report ────────────────────────────────────────
    with tab2:
        df = query("""
            SELECT b.name AS Budget, b.total_amount AS Allocated,
                   COALESCE((SELECT SUM(amount) FROM expenses e
                             WHERE e.budget_id=b.budget_id
                               AND e.status='Approved'
                               AND e.expense_date BETWEEN ? AND ?),0) AS Spent
            FROM budgets b
            WHERE b.period_start <= ? AND b.period_end >= ?
        """, (period_start.isoformat(), period_end.isoformat(),
              period_end.isoformat(), period_start.isoformat()))
        if not df.empty:
            df["Remaining"] = df["Allocated"] - df["Spent"]
            df["Utilization %"] = (
                df["Spent"] / df["Allocated"].replace(0, 1) * 100
            ).round(1)
            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = px.bar(
                df, x="Budget", y=["Allocated", "Spent"],
                barmode="group", title="Budget vs Spend",
            )
            st.plotly_chart(fig, use_container_width=True)

            sections = [
                {"heading": "Summary",
                 "paragraph": (
                     f"<b>Total allocated:</b> "
                     f"${df['Allocated'].sum():,.2f} &nbsp;|&nbsp; "
                     f"<b>Total spent:</b> ${df['Spent'].sum():,.2f} &nbsp;|&nbsp; "
                     f"<b>Utilization:</b> "
                     f"{(df['Spent'].sum() / max(df['Allocated'].sum(),1) * 100):.1f}%"
                 )},
                {"heading": "Budget detail",
                 "table": {
                     "headers": list(df.columns),
                     "rows": df.values.tolist(),
                 }},
            ]
            pdf_bytes = build_report_pdf(
                "Budget Report", sections,
                USER["full_name"], USER["role"],
            )
            c1, c2 = st.columns(2)
            c1.download_button(
                "📄 Download PDF", data=pdf_bytes,
                file_name=f"budget_report_{date.today()}.pdf",
                mime="application/pdf", use_container_width=True,
            )
            c2.download_button(
                "📊 Download CSV", data=df.to_csv(index=False),
                file_name=f"budget_report_{date.today()}.csv",
                mime="text/csv", use_container_width=True,
            )
        else:
            st.info("No budgets yet.")

    # ── KPI Report ───────────────────────────────────────────
    with tab3:
        df = query("""
            SELECT k.name AS KPI, k.formula_type AS "Formula",
                   k.unit AS Unit,
                   (SELECT target_value FROM kpi_targets t
                     WHERE t.kpi_id=k.kpi_id
                       AND t.period_start <= ? AND t.period_end >= ?
                     ORDER BY period_end DESC LIMIT 1) AS Target,
                   (SELECT actual_value FROM kpi_measurements m
                     WHERE m.kpi_id=k.kpi_id
                       AND m.period_start <= ? AND m.period_end >= ?
                     ORDER BY period_end DESC LIMIT 1) AS Actual
            FROM kpis k
        """, (period_end.isoformat(), period_start.isoformat(),
              period_end.isoformat(), period_start.isoformat()))
        if not df.empty:
            df["Achievement %"] = df.apply(
                lambda r: round(compute_kpi_achievement(
                    r["Actual"] or 0, r["Target"] or 0, r["Formula"]), 1),
                axis=1,
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = px.bar(
                df, x="KPI", y="Achievement %",
                color="Achievement %",
                color_continuous_scale="RdYlGn",
                range_color=[0, 150],
                title="KPI Achievement vs Target",
            )
            fig.add_hline(y=100, line_dash="dash")
            st.plotly_chart(fig, use_container_width=True)

            sections = [
                {"heading": "Summary",
                 "paragraph": (
                     f"<b>Total KPIs:</b> {len(df)} &nbsp;|&nbsp; "
                     f"<b>Meeting target:</b> "
                     f"{int((df['Achievement %'] >= 100).sum())}"
                 )},
                {"heading": "KPI details",
                 "table": {
                     "headers": list(df.columns),
                     "rows": df.values.tolist(),
                 }},
            ]
            pdf_bytes = build_report_pdf(
                "KPI Performance Report", sections,
                USER["full_name"], USER["role"],
            )
            c1, c2 = st.columns(2)
            c1.download_button(
                "📄 Download PDF", data=pdf_bytes,
                file_name=f"kpi_report_{date.today()}.pdf",
                mime="application/pdf", use_container_width=True,
            )
            c2.download_button(
                "📊 Download CSV", data=df.to_csv(index=False),
                file_name=f"kpi_report_{date.today()}.csv",
                mime="text/csv", use_container_width=True,
            )
        else:
            st.info("No KPIs yet.")


# ═══════════════════════════════════════════════════════════════
# PAGE: TEAM
# ═══════════════════════════════════════════════════════════════
elif page == "Team":
    st.title("👥 Team Management")

    CAN_CREATE_USERS = USER["role"] in (
        "CEO", "Marketing Executive", "System Administrator"
    )

    if CAN_CREATE_USERS:
        with st.expander("➕ Add team member", expanded=True):
            with st.form("user_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                name = c1.text_input("Full name")
                email = c2.text_input("Email").strip().lower()
                c3, c4 = st.columns(2)
                role = c3.selectbox("Role", ROLES)
                pw = c4.text_input("Initial password", type="password")
                submitted = st.form_submit_button(
                    "Create user", type="primary"
                )

                if submitted:
                    if not (name and email and pw):
                        st.error("Name, email, and password are required.")
                    elif len(pw) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        existing = query(
                            "SELECT 1 FROM users WHERE LOWER(email)=?",
                            (email,),
                        )
                        if not existing.empty:
                            st.error(
                                "An account with that email already exists."
                            )
                        else:
                            org = query(
                                "SELECT organisation_id FROM organisations LIMIT 1"
                            )
                            org_id = (
                                int(org.iloc[0]["organisation_id"])
                                if not org.empty else 1
                            )
                            dept = query(
                                "SELECT department_id FROM departments LIMIT 1"
                            )
                            dept_id = (
                                int(dept.iloc[0]["department_id"])
                                if not dept.empty else None
                            )
                            uid = execute(
                                """INSERT INTO users
                                   (organisation_id, full_name, email,
                                    password_hash, role, department_id)
                                   VALUES (?,?,?,?,?,?)""",
                                (org_id, name, email, hash_password(pw),
                                 role, dept_id),
                            )
                            log_audit(
                                USER["user_id"], "CREATE", "user", uid, name
                            )
                            st.success(
                                f"✅ Created {name} ({role}). They can now log in."
                            )
                            st.rerun()
    else:
        st.info(
            f"Your role (**{USER['role']}**) cannot create users. "
            "Sign in as CEO, Marketing Executive, or System Administrator."
        )

    st.subheader("All users")
    st.dataframe(
        query("""SELECT user_id, full_name, email, role, is_active, created_at
                 FROM users ORDER BY user_id"""),
        use_container_width=True, hide_index=True,
    )


# ═══════════════════════════════════════════════════════════════
# PAGE: AUDIT LOG
# ═══════════════════════════════════════════════════════════════
elif page == "Audit Log":
    st.title("🧾 Audit Log")
    df = query("""
        SELECT a.audit_id, a.timestamp, u.full_name AS user,
               a.action, a.entity, a.entity_id, a.details
        FROM audit_logs a LEFT JOIN users u ON u.user_id = a.user_id
        ORDER BY a.audit_id DESC LIMIT 500
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV", df.to_csv(index=False),
        "audit_log.csv", "text/csv",
    )

# ═══════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ═══════════════════════════════════════════════════════════════
elif page == "Settings":
    st.title("System Settings")
    if USER["role"] not in ADMIN_ROLES:
        st.error("Only authorised administrators can configure the system.")
        st.stop()

    tab_general, tab_access, tab_users = st.tabs(
        ["Organisation & Appearance", "Role Permissions", "Account Administration"]
    )
    with tab_general:
        with st.form("general_settings"):
            org_name = st.text_input("Organisation name", get_setting("organisation_name", "Delma Inc"))
            currency = st.text_input("Reporting currency", get_setting("currency", "USD"))
            timezone = st.text_input("Timezone", get_setting("timezone", "Africa/Harare"))
            theme = st.selectbox("Interface theme", ["Light", "Dark"], index=0 if get_setting("theme","Light")=="Light" else 1)
            submitted = st.form_submit_button("Save system settings", type="primary")
            if submitted:
                for key, value in {"organisation_name":org_name, "currency":currency,
                                   "timezone":timezone, "theme":theme}.items():
                    execute("INSERT INTO app_settings(setting_key,setting_value) VALUES (?,?) "
                            "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                            (key, value))
                log_audit(USER["user_id"], "UPDATE", "app_settings", None, "General settings updated")
                st.success("Settings saved.")
                st.rerun()

    with tab_access:
        st.caption("Configure which modules each role can view and edit. Administrators retain full system access.")
        role = st.selectbox("Role to configure", ROLES)
        perms = query("SELECT page, can_view, can_edit FROM role_permissions WHERE role=? ORDER BY page", (role,))
        if role in ADMIN_ROLES:
            st.info("Administrator roles have full access and cannot be restricted here.")
        elif not perms.empty:
            with st.form("permissions_form"):
                changes = {}
                for _, row in perms.iterrows():
                    c1, c2, c3 = st.columns([2,1,1])
                    c1.write(row["page"])
                    view = c2.checkbox("View", value=bool(row["can_view"]), key=f"v_{role}_{row['page']}")
                    edit = c3.checkbox("Edit", value=bool(row["can_edit"]), key=f"e_{role}_{row['page']}")
                    changes[row["page"]] = (int(view), int(edit and view))
                if st.form_submit_button("Save permissions", type="primary"):
                    for pg, (view, edit) in changes.items():
                        execute("UPDATE role_permissions SET can_view=?, can_edit=? WHERE role=? AND page=?",
                                (view, edit, role, pg))
                    log_audit(USER["user_id"], "UPDATE", "role_permissions", None, f"Updated {role}")
                    st.success("Role permissions updated.")
                    st.rerun()

    with tab_users:
        users = query("SELECT user_id, full_name, email, role, is_active FROM users ORDER BY full_name")
        st.dataframe(users, use_container_width=True, hide_index=True)
        if not users.empty:
            selected = st.selectbox("Account", users["user_id"].tolist(),
                                    format_func=lambda x: f"{users.loc[users.user_id==x,'full_name'].iloc[0]} — {users.loc[users.user_id==x,'email'].iloc[0]}")
            target = users[users["user_id"] == selected].iloc[0]
            c1, c2 = st.columns(2)
            new_role = c1.selectbox("Change role", ROLES, index=ROLES.index(target["role"]) if target["role"] in ROLES else 0)
            active = c2.checkbox("Account active", value=bool(target["is_active"]))
            if st.button("Update account", type="primary"):
                if int(selected) == int(USER["user_id"]) and not active:
                    st.error("You cannot deactivate your own active session.")
                else:
                    execute("UPDATE users SET role=?, is_active=? WHERE user_id=?",
                            (new_role, int(active), int(selected)))
                    log_audit(USER["user_id"], "UPDATE", "user", int(selected),
                              f"role={new_role}; active={active}")
                    st.success("Account updated.")
                    st.rerun()
