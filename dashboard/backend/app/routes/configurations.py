"""
Phase 3B: Configuration Management API
=======================================
Email templates, branding, preferences with variable interpolation
"""

import logging
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import asyncpg
import re

from ..database import get_db_pool
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/configurations", tags=["Configuration Management"])


# =====================================================
# Pydantic Models
# =====================================================

class ConfigurationCreate(BaseModel):
    """Create configuration."""
    customer_id: Optional[int] = None  # NULL for global default
    config_type: str
    config_key: str
    config_value: dict
    is_template: bool = False
    template_variables: Optional[List[dict]] = None
    use_ai_phrasing: bool = False
    ai_tone: Optional[str] = None


class ConfigurationUpdate(BaseModel):
    """Update configuration."""
    config_value: Optional[dict] = None
    is_active: Optional[bool] = None
    use_ai_phrasing: Optional[bool] = None
    ai_tone: Optional[str] = None


class InterpolateRequest(BaseModel):
    """Interpolate variables into template."""
    variables: dict


class ConfigurationResponse(BaseModel):
    """Configuration response."""
    id: UUID
    customer_id: Optional[int]
    config_type: str
    config_key: str
    config_value: dict
    is_template: bool
    template_variables: Optional[List[dict]]
    use_ai_phrasing: bool
    ai_tone: Optional[str]
    is_active: bool
    is_default: bool
    created_at: datetime


class InterpolateResponse(BaseModel):
    """Interpolated template response."""
    rendered_content: dict
    missing_variables: List[str]


# =====================================================
# Helper Functions
# =====================================================

def interpolate_variables(template: str, variables: dict) -> tuple[str, List[str]]:
    """
    Interpolate variables into template string.

    Returns: (rendered_string, missing_variables)
    """
    # Find all {{variable}} patterns
    pattern = r'\{\{(\w+)\}\}'
    found_vars = set(re.findall(pattern, template))

    # Track missing variables
    missing = [var for var in found_vars if var not in variables]

    # Replace variables
    rendered = template
    for var_name, var_value in variables.items():
        rendered = rendered.replace(f"{{{{{var_name}}}}}", str(var_value))

    return rendered, missing


# =====================================================
# Endpoints
# =====================================================

@router.post("/", response_model=ConfigurationResponse)
async def create_configuration(
    config: ConfigurationCreate,
    user: dict = Depends(get_current_user)
):
    """
    Create a new configuration.

    customer_id = NULL creates a global default configuration.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # If customer_id provided, verify customer exists
            if config.customer_id:
                customer_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM dna_app.customers WHERE id = $1)",
                    config.customer_id
                )
                if not customer_exists:
                    raise HTTPException(404, "Customer not found")

            # Create configuration
            row = await conn.fetchrow("""
                INSERT INTO dna_app.customer_configuration (
                    customer_id, config_type, config_key, config_value,
                    is_template, template_variables, use_ai_phrasing,
                    ai_tone, created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, customer_id, config_type, config_key, config_value,
                          is_template, template_variables, use_ai_phrasing, ai_tone,
                          is_active, is_default, created_at
            """,
                config.customer_id, config.config_type, config.config_key,
                config.config_value, config.is_template, config.template_variables,
                config.use_ai_phrasing, config.ai_tone, user.get("user_id")
            )

            logger.info(f"Configuration created: {row['id']}")

            return ConfigurationResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                config_type=row['config_type'],
                config_key=row['config_key'],
                config_value=row['config_value'],
                is_template=row['is_template'],
                template_variables=row['template_variables'],
                use_ai_phrasing=row['use_ai_phrasing'],
                ai_tone=row['ai_tone'],
                is_active=row['is_active'],
                is_default=row['is_default'],
                created_at=row['created_at']
            )

    except asyncpg.UniqueViolationError:
        raise HTTPException(400, "Configuration with this key already exists for this customer")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating configuration: {e}")
        raise HTTPException(500, f"Failed to create configuration: {str(e)}")


@router.get("/", response_model=List[ConfigurationResponse])
async def list_configurations(
    customer_id: Optional[int] = Query(None, description="Filter by customer (NULL for global)"),
    config_type: Optional[str] = Query(None),
    is_default: Optional[bool] = Query(None),
    include_inactive: bool = Query(False),
    user: dict = Depends(get_current_user)
):
    """
    List configurations with filters.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            where_clauses = []
            params = []
            param_idx = 1

            if customer_id is not None:
                where_clauses.append(f"customer_id = ${param_idx}")
                params.append(customer_id)
                param_idx += 1
            elif customer_id == "global":
                where_clauses.append("customer_id IS NULL")

            if config_type:
                where_clauses.append(f"config_type = ${param_idx}")
                params.append(config_type)
                param_idx += 1

            if is_default is not None:
                where_clauses.append(f"is_default = ${param_idx}")
                params.append(is_default)
                param_idx += 1

            if not include_inactive:
                where_clauses.append("is_active = true")

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            rows = await conn.fetch(f"""
                SELECT
                    id, customer_id, config_type, config_key, config_value,
                    is_template, template_variables, use_ai_phrasing, ai_tone,
                    is_active, is_default, created_at
                FROM dna_app.customer_configuration
                {where_sql}
                ORDER BY config_type, config_key
            """, *params)

            return [
                ConfigurationResponse(
                    id=row['id'],
                    customer_id=row['customer_id'],
                    config_type=row['config_type'],
                    config_key=row['config_key'],
                    config_value=row['config_value'],
                    is_template=row['is_template'],
                    template_variables=row['template_variables'],
                    use_ai_phrasing=row['use_ai_phrasing'],
                    ai_tone=row['ai_tone'],
                    is_active=row['is_active'],
                    is_default=row['is_default'],
                    created_at=row['created_at']
                )
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Error listing configurations: {e}")
        raise HTTPException(500, f"Failed to list configurations: {str(e)}")


@router.get("/{config_id}", response_model=ConfigurationResponse)
async def get_configuration(
    config_id: UUID,
    user: dict = Depends(get_current_user)
):
    """
    Get configuration by ID.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    id, customer_id, config_type, config_key, config_value,
                    is_template, template_variables, use_ai_phrasing, ai_tone,
                    is_active, is_default, created_at
                FROM dna_app.customer_configuration
                WHERE id = $1
            """, config_id)

            if not row:
                raise HTTPException(404, "Configuration not found")

            return ConfigurationResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                config_type=row['config_type'],
                config_key=row['config_key'],
                config_value=row['config_value'],
                is_template=row['is_template'],
                template_variables=row['template_variables'],
                use_ai_phrasing=row['use_ai_phrasing'],
                ai_tone=row['ai_tone'],
                is_active=row['is_active'],
                is_default=row['is_default'],
                created_at=row['created_at']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(500, f"Failed to get configuration: {str(e)}")


@router.patch("/{config_id}", response_model=ConfigurationResponse)
async def update_configuration(
    config_id: UUID,
    updates: ConfigurationUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update configuration.
    """
    pool = await get_db_pool()

    # Build update query
    update_fields = []
    params = []
    param_idx = 1

    for field, value in updates.dict(exclude_unset=True).items():
        if value is not None:
            update_fields.append(f"{field} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not update_fields:
        raise HTTPException(400, "No fields to update")

    params.extend([user.get("user_id"), config_id])

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                UPDATE dna_app.customer_configuration
                SET {', '.join(update_fields)}, updated_at = NOW(), updated_by = ${param_idx}
                WHERE id = ${param_idx + 1}
                RETURNING id, customer_id, config_type, config_key, config_value,
                          is_template, template_variables, use_ai_phrasing, ai_tone,
                          is_active, is_default, created_at
            """, *params)

            if not row:
                raise HTTPException(404, "Configuration not found")

            logger.info(f"Configuration updated: {config_id}")

            return ConfigurationResponse(
                id=row['id'],
                customer_id=row['customer_id'],
                config_type=row['config_type'],
                config_key=row['config_key'],
                config_value=row['config_value'],
                is_template=row['is_template'],
                template_variables=row['template_variables'],
                use_ai_phrasing=row['use_ai_phrasing'],
                ai_tone=row['ai_tone'],
                is_active=row['is_active'],
                is_default=row['is_default'],
                created_at=row['created_at']
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(500, f"Failed to update configuration: {str(e)}")


@router.post("/{config_id}/interpolate", response_model=InterpolateResponse)
async def interpolate_configuration(
    config_id: UUID,
    request: InterpolateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Interpolate variables into a configuration template.

    Replaces {{variable_name}} patterns with provided values.
    """
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            # Get configuration
            row = await conn.fetchrow("""
                SELECT config_value, is_template
                FROM dna_app.customer_configuration
                WHERE id = $1
            """, config_id)

            if not row:
                raise HTTPException(404, "Configuration not found")

            if not row['is_template']:
                raise HTTPException(400, "This configuration is not a template")

            config_value = row['config_value']
            rendered_content = {}
            all_missing = set()

            # Interpolate each field in config_value
            for key, value in config_value.items():
                if isinstance(value, str):
                    rendered, missing = interpolate_variables(value, request.variables)
                    rendered_content[key] = rendered
                    all_missing.update(missing)
                else:
                    rendered_content[key] = value

            return InterpolateResponse(
                rendered_content=rendered_content,
                missing_variables=list(all_missing)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error interpolating configuration: {e}")
        raise HTTPException(500, f"Failed to interpolate configuration: {str(e)}")
