"""Shared token validation — called by every tool before any DB query."""
from db.connector import db


async def validate_token(token: str) -> dict:
    """
    Validate portal token and return session dict.
    Raises ValueError with user-friendly message on failure.
    Returns: {customer_id, plan_id, customer_name, iso_name, iso_code, plan_name, language}
    """
    row = await db.fetchrow(
        """SELECT cpa.customer_id,
                  c.name AS customer_name,
                  COALESCE(
                      (SELECT cc.config_value::text
                       FROM dna_app.customer_configuration cc
                       WHERE cc.customer_id = cpa.customer_id
                         AND cc.config_type = 'mcp_chat'
                         AND cc.config_key = 'language'
                         AND cc.is_active = true
                       LIMIT 1),
                      (SELECT cc.config_value::text
                       FROM dna_app.customer_configuration cc
                       WHERE cc.customer_id IS NULL
                         AND cc.config_type = 'mcp_chat'
                         AND cc.config_key = 'language'
                       LIMIT 1),
                      '"en"'
                  ) AS language_json
           FROM dna_app.customer_portal_access cpa
           JOIN dna_app.customers c ON c.id = cpa.customer_id
           WHERE cpa.token = $1
             AND cpa.expires_at > NOW()""",
        token,
    )
    if not row:
        raise ValueError("Invalid or expired token. Please request a new link.")

    # Resolve default plan from customer's first active plan
    plan_row = await db.fetchrow(
        """SELECT cip.id AS plan_id, cip.plan_name,
                  iso.code AS iso_code, iso.name AS iso_name
           FROM dna_app.customer_iso_plans cip
           JOIN dna_app.iso_standards iso ON iso.id = cip.iso_standard_id
           WHERE cip.customer_id = $1
           ORDER BY cip.created_at
           LIMIT 1""",
        row["customer_id"],
    )

    import json
    lang = row["language_json"]
    try:
        lang = json.loads(lang)
    except Exception:
        lang = "en"

    return {
        "customer_id": row["customer_id"],
        "plan_id": str(plan_row["plan_id"]) if plan_row else None,
        "customer_name": row["customer_name"],
        "iso_code": plan_row["iso_code"] if plan_row else None,
        "iso_name": plan_row["iso_name"] if plan_row else None,
        "plan_name": plan_row["plan_name"] if plan_row else None,
        "language": lang,
    }
