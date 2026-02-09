"""
Template Validation Module
===========================

Validates template structure and semantics to prevent bad data from entering the database.
Provides detailed error reporting for LLM self-healing.
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class ValidationError:
    """Represents a single validation error."""

    def __init__(self, error_type: str, message: str, severity: str = "error"):
        self.error_type = error_type  # e.g., "missing_field", "invalid_type"
        self.message = message
        self.severity = severity  # "error" or "warning"

    def __str__(self):
        return f"[{self.severity.upper()}] {self.error_type}: {self.message}"


class TemplateValidator:
    """
    Validates template structure and semantics.

    Two validation levels:
    - Structural: Required fields, correct types (blocking errors)
    - Semantic: Logical consistency, best practices (warnings)
    """

    def validate(self, template: dict) -> Tuple[List[ValidationError], List[ValidationError]]:
        """
        Validate template completely.

        Returns:
            (errors, warnings) - Two lists of ValidationError objects
        """
        errors = []
        warnings = []

        # Structural validation (critical)
        errors.extend(self._validate_structure(template))

        # Semantic validation (non-critical)
        warnings.extend(self._validate_semantics(template))

        if errors:
            logger.warning(f"Template validation found {len(errors)} errors")
        if warnings:
            logger.info(f"Template validation found {len(warnings)} warnings")

        return errors, warnings

    def _validate_structure(self, template: dict) -> List[ValidationError]:
        """
        Validate required structure and types.

        Critical errors that prevent template from working.
        """
        errors = []

        # Top-level required fields
        required_top_level = ["document_title", "fixed_sections", "fillable_sections"]
        for field in required_top_level:
            if field not in template:
                errors.append(ValidationError(
                    "missing_field",
                    f"Missing required top-level field: '{field}'"
                ))

        # Validate document_title
        if "document_title" in template:
            if not isinstance(template["document_title"], str):
                errors.append(ValidationError(
                    "invalid_type",
                    "document_title must be a string"
                ))
            elif len(template["document_title"].strip()) == 0:
                errors.append(ValidationError(
                    "invalid_value",
                    "document_title cannot be empty"
                ))

        # Validate fixed_sections
        if "fixed_sections" in template:
            if not isinstance(template["fixed_sections"], list):
                errors.append(ValidationError(
                    "invalid_type",
                    "fixed_sections must be a list"
                ))
            else:
                for i, section in enumerate(template["fixed_sections"]):
                    errors.extend(self._validate_fixed_section(section, i))

        # Validate fillable_sections
        if "fillable_sections" in template:
            if not isinstance(template["fillable_sections"], list):
                errors.append(ValidationError(
                    "invalid_type",
                    "fillable_sections must be a list"
                ))
            else:
                for i, section in enumerate(template["fillable_sections"]):
                    errors.extend(self._validate_fillable_section(section, i))

        return errors

    def _validate_fixed_section(self, section: Any, index: int) -> List[ValidationError]:
        """Validate a single fixed section."""
        errors = []

        if not isinstance(section, dict):
            errors.append(ValidationError(
                "invalid_type",
                f"Fixed section {index} must be a dictionary"
            ))
            return errors

        # Required fields for fixed sections
        required = ["id", "title", "content"]
        for field in required:
            if field not in section:
                errors.append(ValidationError(
                    "missing_field",
                    f"Fixed section {index} ('{section.get('id', 'unknown')}') missing required field: '{field}'"
                ))

        # Validate types
        if "id" in section and not isinstance(section["id"], str):
            errors.append(ValidationError(
                "invalid_type",
                f"Fixed section {index}: 'id' must be a string"
            ))

        if "title" in section and not isinstance(section["title"], str):
            errors.append(ValidationError(
                "invalid_type",
                f"Fixed section {index}: 'title' must be a string"
            ))

        if "content" in section and not isinstance(section["content"], str):
            errors.append(ValidationError(
                "invalid_type",
                f"Fixed section {index}: 'content' must be a string"
            ))

        return errors

    def _validate_fillable_section(self, section: Any, index: int) -> List[ValidationError]:
        """Validate a single fillable section."""
        errors = []

        if not isinstance(section, dict):
            errors.append(ValidationError(
                "invalid_type",
                f"Fillable section {index} must be a dictionary"
            ))
            return errors

        # Required fields for fillable sections
        required = ["id", "title", "type", "semantic_tags"]
        for field in required:
            if field not in section:
                errors.append(ValidationError(
                    "missing_field",
                    f"Fillable section {index} ('{section.get('id', 'unknown')}') missing required field: '{field}'"
                ))

        # Validate types
        if "id" in section and not isinstance(section["id"], str):
            errors.append(ValidationError(
                "invalid_type",
                f"Fillable section {index}: 'id' must be a string"
            ))

        if "title" in section and not isinstance(section["title"], str):
            errors.append(ValidationError(
                "invalid_type",
                f"Fillable section {index}: 'title' must be a string"
            ))

        if "type" in section:
            if not isinstance(section["type"], str):
                errors.append(ValidationError(
                    "invalid_type",
                    f"Fillable section {index}: 'type' must be a string"
                ))
            elif section["type"] not in ["table", "paragraph", "list", "field"]:
                errors.append(ValidationError(
                    "invalid_value",
                    f"Fillable section {index}: 'type' must be one of: table, paragraph, list, field (got: '{section['type']}')"
                ))

        # Validate semantic_tags
        if "semantic_tags" in section:
            if not isinstance(section["semantic_tags"], list):
                errors.append(ValidationError(
                    "invalid_type",
                    f"Fillable section {index} ('{section.get('id', 'unknown')}'): 'semantic_tags' must be a list"
                ))
            elif len(section["semantic_tags"]) == 0:
                errors.append(ValidationError(
                    "invalid_value",
                    f"Fillable section {index} ('{section.get('id', 'unknown')}'): 'semantic_tags' cannot be empty"
                ))
            else:
                for tag in section["semantic_tags"]:
                    if not isinstance(tag, str):
                        errors.append(ValidationError(
                            "invalid_type",
                            f"Fillable section {index} ('{section.get('id', 'unknown')}'): semantic_tags must contain strings"
                        ))
                        break

        # Validate mandatory_confidence (if present)
        if "mandatory_confidence" in section:
            confidence = section["mandatory_confidence"]
            if not isinstance(confidence, (int, float)):
                errors.append(ValidationError(
                    "invalid_type",
                    f"Fillable section {index} ('{section.get('id', 'unknown')}'): 'mandatory_confidence' must be a number"
                ))
            elif not (0 <= confidence <= 1):
                errors.append(ValidationError(
                    "invalid_value",
                    f"Fillable section {index} ('{section.get('id', 'unknown')}'): 'mandatory_confidence' must be between 0 and 1 (got: {confidence})"
                ))

        # Validate is_mandatory (if present)
        if "is_mandatory" in section and not isinstance(section["is_mandatory"], bool):
            errors.append(ValidationError(
                "invalid_type",
                f"Fillable section {index} ('{section.get('id', 'unknown')}'): 'is_mandatory' must be a boolean"
            ))

        return errors

    def _validate_semantics(self, template: dict) -> List[ValidationError]:
        """
        Validate logical consistency.

        Non-critical issues that should be logged but don't prevent usage.
        """
        warnings = []

        # Check for duplicate IDs
        fillable_ids = [s.get("id") for s in template.get("fillable_sections", []) if "id" in s]
        fixed_ids = [s.get("id") for s in template.get("fixed_sections", []) if "id" in s]

        # Check fillable duplicates
        if len(fillable_ids) != len(set(fillable_ids)):
            duplicates = [id for id in fillable_ids if fillable_ids.count(id) > 1]
            warnings.append(ValidationError(
                "duplicate_id",
                f"Duplicate IDs in fillable sections: {set(duplicates)}",
                severity="warning"
            ))

        # Check fixed duplicates
        if len(fixed_ids) != len(set(fixed_ids)):
            duplicates = [id for id in fixed_ids if fixed_ids.count(id) > 1]
            warnings.append(ValidationError(
                "duplicate_id",
                f"Duplicate IDs in fixed sections: {set(duplicates)}",
                severity="warning"
            ))

        # Check if mandatory fields have high confidence
        for section in template.get("fillable_sections", []):
            if section.get("is_mandatory") and section.get("mandatory_confidence", 0) < 0.85:
                warnings.append(ValidationError(
                    "low_confidence_mandatory",
                    f"Section '{section.get('id')}' marked mandatory but has low confidence: {section.get('mandatory_confidence')}",
                    severity="warning"
                ))

        # Check total section count is reasonable
        total_sections = len(fillable_ids) + len(fixed_ids)
        if total_sections > 150:
            warnings.append(ValidationError(
                "excessive_sections",
                f"Unusually high section count: {total_sections} (may indicate parsing issue)",
                severity="warning"
            ))
        elif total_sections == 0:
            warnings.append(ValidationError(
                "no_sections",
                "Template has no sections at all",
                severity="warning"
            ))

        # Check if fillable sections have semantic tags
        sections_without_tags = [
            s.get("id") for s in template.get("fillable_sections", [])
            if len(s.get("semantic_tags", [])) == 0
        ]
        if sections_without_tags:
            warnings.append(ValidationError(
                "missing_semantic_tags",
                f"{len(sections_without_tags)} fillable sections have no semantic tags",
                severity="warning"
            ))

        return warnings


# Singleton instance
_validator = TemplateValidator()


def validate_template(template: dict) -> Tuple[List[ValidationError], List[ValidationError]]:
    """
    Validate template structure and semantics.

    Returns:
        (errors, warnings) - Two lists of ValidationError objects
    """
    return _validator.validate(template)
