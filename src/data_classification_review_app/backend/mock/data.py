"""Mock data adapter.

Provides all in-memory data structures needed by the mock API routes.
"""
from __future__ import annotations

# ===== Tag taxonomy =====
_TAG_COLOR = '#1B3139'
_TAG_BG    = '#EEEDE9'

TAG_META: dict[str, dict] = {
    'class.name':          {'label': 'Name',          'short': 'Name',   'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.email_address': {'label': 'Email address', 'short': 'Email',  'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.phone_number':  {'label': 'Phone number',  'short': 'Phone',  'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.location':      {'label': 'Location',      'short': 'Loc.',   'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.address':       {'label': 'Address',       'short': 'Addr.',  'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.ssn':           {'label': 'SSN',           'short': 'SSN',    'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.credit_card':   {'label': 'Credit card',   'short': 'Card',   'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.date_of_birth': {'label': 'Date of birth', 'short': 'DOB',    'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.ip_address':    {'label': 'IP address',    'short': 'IP',     'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.gender':        {'label': 'Gender',        'short': 'Gender', 'color': _TAG_COLOR, 'bg': _TAG_BG},
    'class.bank_account':  {'label': 'Bank account',  'short': 'Bank',   'color': _TAG_COLOR, 'bg': _TAG_BG},
}

# ===== Stewards =====
# Combined users + groups into a single PRINCIPALS dict; id = the key used in JS.
PRINCIPALS: dict[str, dict] = {
    'maria.chen': {
        'id': 'maria.chen', 'name': 'Maria Chen',
        'email': 'maria.chen@example.com',
        'initials': 'MC', 'accent': '#FF3621',
        'team': 'Data Governance · Customer 360',
        'kind': 'user', 'is_admin': False,
        'members': None,
    },
    'arjun.patel': {
        'id': 'arjun.patel', 'name': 'Arjun Patel',
        'email': 'arjun.patel@example.com',
        'initials': 'AP', 'accent': '#2272B4',
        'team': 'Data Governance · Finance',
        'kind': 'user', 'is_admin': False,
        'members': None,
    },
    'lena.koch': {
        'id': 'lena.koch', 'name': 'Lena Koch',
        'email': 'lena.koch@example.com',
        'initials': 'LK', 'accent': '#00875C',
        'team': 'Data Governance · Marketing',
        'kind': 'user', 'is_admin': False,
        'members': None,
    },
    'sam.okafor': {
        'id': 'sam.okafor', 'name': 'Sam Okafor',
        'email': 'sam.okafor@example.com',
        'initials': 'SO', 'accent': '#BA7B23',
        'team': 'Data Governance · Support',
        'kind': 'user', 'is_admin': False,
        'members': None,
    },
    'priya.nair': {
        'id': 'priya.nair', 'name': 'Priya Nair',
        'email': 'priya.nair@example.com',
        'initials': 'PN', 'accent': '#143D4A',
        'team': 'Data Governance · Product',
        'kind': 'user', 'is_admin': True,
        'members': None,
    },
    'jamie.diaz': {
        'id': 'jamie.diaz', 'name': 'Jamie Diaz',
        'email': 'jamie.diaz@example.com',
        'initials': 'JD', 'accent': '#1B3139',
        'team': 'Platform Admin · Unity Catalog',
        'kind': 'user', 'is_admin': True,
        'members': None,
    },
    # Groups
    'finance-data-stewards': {
        'id': 'finance-data-stewards',
        'name': 'Finance data stewards',
        'email': None,
        'initials': 'FD', 'accent': '#2272B4',
        'team': None,
        'kind': 'group', 'is_admin': False,
        'members': 4,
    },
    'marketing-stewards': {
        'id': 'marketing-stewards',
        'name': 'Marketing stewards',
        'email': None,
        'initials': 'MK', 'accent': '#00875C',
        'team': None,
        'kind': 'group', 'is_admin': False,
        'members': 3,
    },
    'security-and-compliance': {
        'id': 'security-and-compliance',
        'name': 'Security & compliance',
        'email': None,
        'initials': 'SC', 'accent': '#143D4A',
        'team': None,
        'kind': 'group', 'is_admin': False,
        'members': 6,
    },
}

# ===== Steward → asset assignments =====
STEWARD_ASSIGNMENTS: list[dict] = [
    # Maria — owns the entire 00vsdb catalog
    {'id': 'a1', 'principal': 'maria.chen',  'principal_kind': 'user',  'scope': 'catalog', 'catalog': '00vsdb', 'schema_name': None, 'table_name': None},
    # Arjun — owns finance schema
    {'id': 'a2', 'principal': 'arjun.patel', 'principal_kind': 'user',  'scope': 'schema',  'catalog': 'main',   'schema_name': 'finance',   'table_name': None},
    # Lena — owns marketing schema
    {'id': 'a3', 'principal': 'lena.koch',   'principal_kind': 'user',  'scope': 'schema',  'catalog': 'main',   'schema_name': 'marketing', 'table_name': None},
    # Sam — owns the prod.support schema
    {'id': 'a4', 'principal': 'sam.okafor',  'principal_kind': 'user',  'scope': 'schema',  'catalog': 'prod',   'schema_name': 'support',   'table_name': None},
    # Priya — owns just one table
    {'id': 'a5', 'principal': 'priya.nair',  'principal_kind': 'user',  'scope': 'table',   'catalog': 'prod',   'schema_name': 'product',   'table_name': 'users'},
    # Group: finance group also has read on finance schema (joint review)
    {'id': 'a6', 'principal': 'finance-data-stewards', 'principal_kind': 'group', 'scope': 'schema', 'catalog': 'main', 'schema_name': 'finance', 'table_name': None},
    # Group: security & compliance has organization-wide visibility on PII findings
    {'id': 'a7', 'principal': 'security-and-compliance', 'principal_kind': 'group', 'scope': 'catalog', 'catalog': 'main', 'schema_name': None, 'table_name': None},
]

# ===== Assignment: which steward owns which (catalog.schema.table) =====
TABLE_OWNERS: dict[str, str] = {
    '00vsdb.agent_analytics.tickets_bronze': 'maria.chen',
    '00vsdb.aiagent.customers':              'maria.chen',
    '00vsdb.dbdemos_ai_agent.customers':     'maria.chen',
    'main.finance.invoices':                 'arjun.patel',
    'main.finance.payroll_v2':               'arjun.patel',
    'main.marketing.leads':                  'lena.koch',
    'main.marketing.events_clickstream':     'lena.koch',
    'prod.support.chat_logs':                'sam.okafor',
    'prod.support.escalations':              'sam.okafor',
    'prod.product.users':                    'priya.nair',
}

# ===== Live-metadata mock fixtures (table description, column description, table tags) =====
TABLE_DESCRIPTIONS: dict[str, str] = {
    '00vsdb.agent_analytics.tickets_bronze': 'Raw support ticket intake, one row per ticket event.',
    'main.finance.payroll_v2':               'Employee payroll records, refreshed nightly.',
}
COLUMN_DESCRIPTIONS: dict[str, str] = {
    '00vsdb.agent_analytics.tickets_bronze.ticket_id': 'Unique ticket identifier.',
    'main.finance.payroll_v2.employee_ssn':            'Employee social security number.',
}
TABLE_TAGS: dict[str, list[str]] = {
    '00vsdb.agent_analytics.tickets_bronze': ['pii_reviewed'],
    'main.finance.payroll_v2':               ['sensitivity=high', 'pii_reviewed'],
}

# ===== Pre-decided status for the synthetic data, to fill the audit log =====
PRE_DECISIONS: dict[str, dict] = {
    'main.finance.payroll_v2.employee_ssn':    {'status': 'approved', 'decided_at': '2026-05-18 14:22', 'reviewer': 'arjun.patel'},
    'main.finance.payroll_v2.full_name':       {'status': 'approved', 'decided_at': '2026-05-18 14:22', 'reviewer': 'arjun.patel'},
    'main.finance.payroll_v2.bank_account_no': {'status': 'approved', 'decided_at': '2026-05-18 14:23', 'reviewer': 'arjun.patel'},
    'main.finance.payroll_v2.date_of_birth':   {'status': 'approved', 'decided_at': '2026-05-18 14:23', 'reviewer': 'arjun.patel'},
    'main.finance.invoices.card_last4':        {
        'status': 'rejected', 'decided_at': '2026-05-19 09:11', 'reviewer': 'arjun.patel',
        'comment': 'Confidence too low — only last 4, not a full PAN. Not PCI in our schema.',
    },
    'main.finance.invoices.billing_email':     {'status': 'approved', 'decided_at': '2026-05-19 09:14', 'reviewer': 'arjun.patel'},
    'main.marketing.leads.contact_email':      {'status': 'approved', 'decided_at': '2026-05-19 11:02', 'reviewer': 'lena.koch'},
    'main.marketing.leads.contact_name':       {
        'status': 'modified', 'decided_at': '2026-05-19 11:03', 'reviewer': 'lena.koch',
        'modified_tag': 'class.location',
        'comment': 'These are B2B contact names, sensitivity is Medium not High in our taxonomy.',
    },
    'main.marketing.events_clickstream.user_email': {
        'status': 'rejected', 'decided_at': '2026-05-19 11:08', 'reviewer': 'lena.koch',
        'comment': 'False positive — anonymous guest sessions.',
    },
    'prod.product.users.signup_email':         {'status': 'approved', 'decided_at': '2026-05-17 16:40', 'reviewer': 'priya.nair'},
    'prod.product.users.display_name':         {
        'status': 'modified', 'decided_at': '2026-05-17 16:42', 'reviewer': 'priya.nair',
        'modified_tag': 'class.location',
        'comment': 'Display names are user-chosen handles, not legal names.',
    },
}

# ===== Daily activity sparkline data (last 14 days) =====
DAILY_ACTIVITY: list[dict] = [
    {'d': 'May 06', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 07', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 08', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 09', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 10', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 11', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 12', 'approved': 0, 'rejected': 0, 'pending': 0},
    {'d': 'May 13', 'approved': 0, 'rejected': 0, 'pending': 4},
    {'d': 'May 14', 'approved': 0, 'rejected': 0, 'pending': 9},
    {'d': 'May 15', 'approved': 0, 'rejected': 0, 'pending': 12},
    {'d': 'May 16', 'approved': 1, 'rejected': 0, 'pending': 14},
    {'d': 'May 17', 'approved': 2, 'rejected': 0, 'pending': 14},
    {'d': 'May 18', 'approved': 4, 'rejected': 0, 'pending': 12},
    {'d': 'May 19', 'approved': 3, 'rejected': 3, 'pending': 6},
]

# ===== Raw column data =====
# Each tuple: (catalog, schema, table, column, dataType, classTag[, confidence, frequency, samples])
# classTag=None → untagged column (shown for context, excluded from proposals).
_RAW: list[tuple] = [
    # ── 00vsdb.agent_analytics.tickets_bronze ──────────────────────────────────
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'call_transcript', 'string', 'class.name', 'HIGH', 0.0024, [
        "Good morning! You've reached [Insurance Co]. May I have your policy number?\nCustomer: Rich how reveal probably throw clear.\nSystem: Suggested response — 'Let me verify that in our system'\nAgent: Could you confirm the last 4 digits…",
        "Good morning! You've reached [Insurance Co]. May I have your policy number?\nCustomer: Bill finish central can.\nSystem: Suggested response — 'Let me verify that in our system'\nAgent: Let me verify…",
        "Good morning! You've reached [Insurance Co]. May I have your policy number?\nCustomer: Guy thank serious cover building star.\nAgent: Umm, let me check…\nAgent: Could you confirm the last 4…",
        "Hello! Thank you for calling [Insurance Co]. How can I help you today?\nCustomer: Bill worker other product individual.\nAgent: Umm, let me check…",
    ]),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'customer_email', 'string', 'class.email_address', 'HIGH', 1.0,
     ['m.alvarez@example.com', 'jordan_p@mail.net', 't.huynh@example.com', 'rk.osei@workmail.org', 'priya.k@example.com']),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'customer_phone', 'string', 'class.phone_number', 'HIGH', 0.98,
     ['+1-415-555-0142', '+1-617-555-0119', '+44-20-7946-0817', '+1-212-555-0173', '+1-503-555-0125']),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'customer_city', 'string', 'class.location', 'HIGH', 0.94,
     ['Boston', 'Reno', 'Portland', 'Brooklyn', 'Austin', 'San Jose']),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'agent_notes', 'string', 'class.name', 'LOW', 0.012,
     ['Caller mentioned a relative by name once.', 'No notable PII; routine renewal call.', 'Caller upset about billing — escalated.']),
    # Untagged columns
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'agent_experience_level',    'bigint',    None),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'agent_specialization_match','boolean',   None),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'call_sentiment_score',       'double',    None),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'close_time',                 'timestamp', None),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'ticket_id',                  'string',    None),
    ('00vsdb', 'agent_analytics', 'tickets_bronze', 'product_line',               'string',    None),

    # ── 00vsdb.aiagent.customers ───────────────────────────────────────────────
    ('00vsdb', 'aiagent', 'customers', 'full_name', 'string', 'class.name', 'HIGH', 1.0,
     ['Marisol Alvarez', 'Jordan Park', 'Thi Huynh', 'Reni Osei', 'Priya Krishnan']),
    ('00vsdb', 'aiagent', 'customers', 'primary_email', 'string', 'class.email_address', 'HIGH', 1.0,
     ['m.alvarez@example.com', 'jpark@mail.net', 't.huynh@example.com', 'rk.osei@workmail.org', 'priya.k@example.com']),
    ('00vsdb', 'aiagent', 'customers', 'home_phone', 'string', 'class.phone_number', 'HIGH', 0.83,
     ['+1-415-555-0142', '+1-617-555-0119', '+1-212-555-0173', '+1-503-555-0125']),
    ('00vsdb', 'aiagent', 'customers', 'work_phone', 'string', 'class.phone_number', 'HIGH', 0.71,
     ['+1-415-555-2204', '+1-617-555-9013', '+1-212-555-3318']),
    ('00vsdb', 'aiagent', 'customers', 'mailing_city', 'string', 'class.location', 'HIGH', 0.99,
     ['Boston', 'Reno', 'Portland', 'Brooklyn', 'Austin']),
    ('00vsdb', 'aiagent', 'customers', 'support_notes', 'string', 'class.name', 'LOW', 0.06,
     ['Spoke with Maria from the team about renewals.', 'Customer prefers email contact.', 'Routine onboarding.']),
    # Untagged
    ('00vsdb', 'aiagent', 'customers', 'customer_id',    'string',    None),
    ('00vsdb', 'aiagent', 'customers', 'created_at',     'timestamp', None),
    ('00vsdb', 'aiagent', 'customers', 'lifetime_value', 'double',    None),

    # ── 00vsdb.dbdemos_ai_agent.customers ─────────────────────────────────────
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'name', 'string', 'class.name', 'HIGH', 1.0,
     ['Marisol Alvarez', 'Jordan Park', 'Thi Huynh', 'Reni Osei', 'Priya Krishnan']),
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'email', 'string', 'class.email_address', 'HIGH', 1.0,
     ['m.alvarez@example.com', 'jpark@mail.net', 't.huynh@example.com', 'rk.osei@workmail.org', 'priya.k@example.com']),
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'phone', 'string', 'class.phone_number', 'HIGH', 0.92,
     ['+1-415-555-0142', '+1-617-555-0119', '+1-212-555-0173']),
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'city', 'string', 'class.location', 'HIGH', 0.98,
     ['Boston', 'Reno', 'Portland', 'Brooklyn', 'Austin', 'San Jose']),
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'feedback', 'string', 'class.name', 'LOW', 0.018,
     ['Loved the new dashboard. — Alex', 'Great experience overall.', 'Spoke with the rep, very helpful.']),
    # Untagged
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'customer_id', 'string', None),
    ('00vsdb', 'dbdemos_ai_agent', 'customers', 'segment',     'string', None),

    # ── main.finance.invoices ──────────────────────────────────────────────────
    ('main', 'finance', 'invoices', 'customer_id',    'string',  None),
    ('main', 'finance', 'invoices', 'billing_email',  'string',  'class.email_address', 'HIGH', 0.99,
     ['accounts@acme.io', 'ap@globex.com', 'finance@initech.net']),
    ('main', 'finance', 'invoices', 'billing_address','string',  'class.address', 'HIGH', 0.98,
     ['1200 Market St, San Francisco, CA', '85 Broad St, New York, NY']),
    ('main', 'finance', 'invoices', 'bank_routing',   'string',  'class.bank_account', 'HIGH', 0.94,
     ['026009593', '121000358', '322271627']),
    ('main', 'finance', 'invoices', 'card_last4',     'string',  'class.credit_card', 'LOW', 0.22,
     ['4242', '0001', '7711']),
    ('main', 'finance', 'invoices', 'amount_usd',     'decimal', None),

    # ── main.finance.payroll_v2 ────────────────────────────────────────────────
    ('main', 'finance', 'payroll_v2', 'employee_ssn',    'string', 'class.ssn', 'HIGH', 1.0,
     ['***-**-1234', '***-**-9821']),
    ('main', 'finance', 'payroll_v2', 'full_name',       'string', 'class.name', 'HIGH', 1.0,
     ['Anna Liu', 'Marcus Webb', 'Carla Diaz']),
    ('main', 'finance', 'payroll_v2', 'bank_account_no', 'string', 'class.bank_account', 'HIGH', 1.0,
     ['00029384741', '00118273645']),
    ('main', 'finance', 'payroll_v2', 'date_of_birth',   'date',   'class.date_of_birth', 'HIGH', 1.0,
     ['1989-04-12', '1972-11-03']),
    ('main', 'finance', 'payroll_v2', 'department',      'string', None),

    # ── main.marketing.leads ──────────────────────────────────────────────────
    ('main', 'marketing', 'leads', 'contact_name',  'string', 'class.name', 'HIGH', 0.96,
     ['Sara Patel', 'Diego Mora', 'Helen Brooks']),
    ('main', 'marketing', 'leads', 'contact_email', 'string', 'class.email_address', 'HIGH', 1.0,
     ['s.patel@corp.io', 'dmora@corp.io']),
    ('main', 'marketing', 'leads', 'contact_phone', 'string', 'class.phone_number', 'HIGH', 0.71,
     ['+1-415-555-9013']),
    ('main', 'marketing', 'leads', 'company_city',  'string', 'class.location', 'HIGH', 0.97,
     ['Seattle', 'Chicago', 'Miami']),
    ('main', 'marketing', 'leads', 'lead_score',    'double', None),
    ('main', 'marketing', 'leads', 'utm_source',    'string', None),

    # ── main.marketing.events_clickstream ─────────────────────────────────────
    ('main', 'marketing', 'events_clickstream', 'user_ip',    'string',    'class.ip_address', 'HIGH', 1.0,
     ['192.168.0.1', '10.0.34.18']),
    ('main', 'marketing', 'events_clickstream', 'user_email', 'string',    'class.email_address', 'LOW', 0.31,
     ['guest@example.com']),
    ('main', 'marketing', 'events_clickstream', 'event_name', 'string',    None),
    ('main', 'marketing', 'events_clickstream', 'event_ts',   'timestamp', None),

    # ── prod.support.chat_logs ────────────────────────────────────────────────
    ('prod', 'support', 'chat_logs', 'agent_name',     'string', 'class.name', 'HIGH', 0.99,
     ['Kira O.', 'Devon S.', 'Mei L.']),
    ('prod', 'support', 'chat_logs', 'customer_email', 'string', 'class.email_address', 'HIGH', 0.96,
     ['help@example.com']),
    ('prod', 'support', 'chat_logs', 'attachment_url', 'string', None),
    ('prod', 'support', 'chat_logs', 'transcript',     'string', 'class.name', 'LOW', 0.04,
     ['Customer said "Hi, this is Alex"']),

    # ── prod.support.escalations ──────────────────────────────────────────────
    ('prod', 'support', 'escalations', 'reporter_email', 'string', 'class.email_address', 'HIGH', 1.0,
     ['help@corp.io']),
    ('prod', 'support', 'escalations', 'reporter_phone', 'string', 'class.phone_number', 'LOW', 0.18,
     ['+1-415-555-0001']),
    ('prod', 'support', 'escalations', 'severity',       'string', None),

    # ── prod.product.users ────────────────────────────────────────────────────
    ('prod', 'product', 'users', 'display_name',  'string', 'class.name', 'HIGH', 1.0,
     ['lumi_dev', 'sara84', 'dmora']),
    ('prod', 'product', 'users', 'signup_email',  'string', 'class.email_address', 'HIGH', 1.0,
     ['help@corp.io']),
    ('prod', 'product', 'users', 'gender',        'string', 'class.gender', 'HIGH', 0.88,
     ['F', 'M', 'NB']),
    ('prod', 'product', 'users', 'locale',        'string', None),
]


def _row_to_col(row: tuple) -> dict:
    """Convert a raw tuple into a column dict with optional tagged fields."""
    catalog, schema, table, column, data_type, class_tag = row[:6]
    table_key = f'{catalog}.{schema}.{table}'
    base = {
        'catalog': catalog,
        'schema': schema,
        'table': table,
        'column': column,
        'data_type': data_type,
        'table_key': table_key,
        'class_tag': class_tag,
        'owner': TABLE_OWNERS.get(table_key, 'maria.chen'),
        'confidence': None,
        'frequency': None,
        'samples': [],
    }
    if class_tag and len(row) > 6:
        base['confidence'] = row[6]
        base['frequency'] = row[7]
        base['samples'] = list(row[8]) if len(row) > 8 else []
    return base


def build_proposals() -> list[dict]:
    """Build proposals list (only tagged columns) with pre-decision status applied."""
    proposals = []
    for row in _RAW:
        col = _row_to_col(row)
        if col['class_tag'] is None:
            continue
        key = f"{col['catalog']}.{col['schema']}.{col['table']}.{col['column']}"
        pre = PRE_DECISIONS.get(key, {})
        proposals.append({
            **col,
            'key': key,
            'status': pre.get('status', 'pending'),
            'decided_at': pre.get('decided_at'),
            'reviewer': pre.get('reviewer'),
            'comment': pre.get('comment'),
            'modified_tag': pre.get('modified_tag'),
            'user_added': False,
            'applied_at': None,
        })
    return proposals


def build_all_columns() -> list[dict]:
    """All columns including untagged, for steward review detail screen."""
    result = []
    for row in _RAW:
        col = _row_to_col(row)
        result.append(col)
    return result


# Cached at module load
PROPOSALS: list[dict] = build_proposals()
ALL_COLUMNS: list[dict] = build_all_columns()
