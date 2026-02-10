"""
Credentials Utility
===================

Generate portal usernames and passwords for customers.
"""

import re
import secrets
import string
import hashlib
import base64


def generate_username(company_name: str, suffix: str = "portal") -> str:
    """
    Generate portal username from company name.

    Args:
        company_name: Company name
        suffix: Suffix to add (default: "portal")

    Returns:
        str: Username in format: {sanitized_company_name}_{suffix}

    Examples:
        >>> generate_username("Acme Corp")
        'acme_corp_portal'
        >>> generate_username("Smith & Sons Ltd.")
        'smith_sons_ltd_portal'
    """
    # Convert to lowercase
    username = company_name.lower().strip()

    # Remove special characters except spaces and hyphens
    username = re.sub(r'[^\w\s-]', '', username)

    # Replace spaces and hyphens with underscores
    username = re.sub(r'[\s-]+', '_', username)

    # Remove consecutive underscores
    username = re.sub(r'_{2,}', '_', username)

    # Remove leading/trailing underscores
    username = username.strip('_')

    # Add suffix
    if suffix:
        username = f"{username}_{suffix}"

    return username


def generate_password(length: int = 16, use_symbols: bool = True) -> str:
    """
    Generate a secure random password.

    Args:
        length: Password length (default: 16)
        use_symbols: Include symbols (default: True)

    Returns:
        str: Randomly generated password

    Examples:
        >>> generate_password(16)
        'Xk9#mP2$vN8@qL4!'
        >>> generate_password(12, use_symbols=False)
        'aB3dE5gH9jK2'
    """
    # Character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()-_=+[]{}|;:,.<>?" if use_symbols else ""

    # Ensure at least one character from each set
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
    ]

    if use_symbols:
        password.append(secrets.choice(symbols))

    # Fill remaining length with random characters
    all_chars = lowercase + uppercase + digits + symbols
    remaining_length = length - len(password)

    for _ in range(remaining_length):
        password.append(secrets.choice(all_chars))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def hash_password(password: str) -> str:
    """
    Hash password using SHA256 with salt.

    Note: For production, use proper bcrypt or argon2.
    This is a simplified version for MVP.

    Args:
        password: Plain text password

    Returns:
        str: Hashed password (format: salt$hash)
    """
    # Generate random salt
    salt = secrets.token_hex(16)

    # Hash password with salt
    hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
    password_hash = hash_obj.hexdigest()

    # Return salt + hash
    return f"{salt}${password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against hash.

    Args:
        password: Plain text password
        password_hash: Hashed password (format: salt$hash)

    Returns:
        bool: True if password matches hash
    """
    try:
        # Extract salt and hash
        salt, stored_hash = password_hash.split('$')

        # Hash provided password with stored salt
        hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
        computed_hash = hash_obj.hexdigest()

        # Compare hashes
        return computed_hash == stored_hash
    except ValueError:
        return False


def generate_portal_credentials(company_name: str) -> tuple[str, str, str]:
    """
    Generate complete portal credentials for a customer.

    Args:
        company_name: Company name

    Returns:
        tuple: (username, plain_password, hashed_password)

    Example:
        >>> username, password, password_hash = generate_portal_credentials("Acme Corp")
        >>> print(f"Username: {username}")
        Username: acme_corp_portal
        >>> print(f"Password: {password}")
        Password: Xk9#mP2$vN8@qL4!
    """
    username = generate_username(company_name)
    password = generate_password(16, use_symbols=True)
    password_hash = hash_password(password)

    return username, password, password_hash
