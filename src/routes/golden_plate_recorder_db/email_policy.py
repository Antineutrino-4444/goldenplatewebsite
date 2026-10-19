"""School-scoped email eligibility, separate from proof of email ownership."""

import json
import re
from datetime import datetime, timezone


def normalize_domain(value):
    if not isinstance(value, str):
        raise ValueError('Enter domains such as school.edu.')
    value = value.strip().lower().removeprefix('@')
    try:
        domain = value.encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('Enter a valid email domain.') from None
    labels = domain.split('.')
    if len(domain) > 253 or len(labels) < 2 or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
        for label in labels
    ):
        raise ValueError('Enter domains such as school.edu, without wildcards or URLs.')
    return domain


def normalize_email(value):
    if not isinstance(value, str):
        raise ValueError('Enter a valid email address.')
    value = value.strip().lower()
    if len(value) > 320 or not re.fullmatch(r'[^@\s,;<>]+@[^@\s,;<>]+', value):
        raise ValueError('Enter a valid email address.')
    local, domain = value.rsplit('@', 1)
    return f'{local}@{normalize_domain(domain)}'


def validate_policy(data):
    if not isinstance(data, dict) or type(data.get('enabled')) is not bool:
        raise ValueError('Choose whether to enable school email rules.')
    normalized = {'enabled': data['enabled']}
    for key in ('allowed_domains', 'exceptions'):
        entries = data.get(key)
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError('Use at most 100 domains or exceptions per list.')
        values = []
        for entry in entries:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError('Remove empty entries from the email rules.')
            entry = entry.strip()
            value = (normalize_email(entry) if key == 'exceptions' and '@' in entry.lstrip('@')
                     else normalize_domain(entry))
            if value not in values:
                values.append(value)
        normalized[key] = values
    if normalized['enabled'] and not (normalized['allowed_domains'] or normalized['exceptions']):
        raise ValueError('Add at least one allowed domain or exception before enabling email rules.')
    return normalized


def school_email_policy(school):
    if school and school.signup_email_policy:
        return json.loads(school.signup_email_policy)
    return {'enabled': False, 'allowed_domains': [], 'exceptions': []}


def email_allowed(school, email):
    policy = school_email_policy(school)
    if not policy['enabled']:
        return True
    try:
        email = normalize_email(email)
    except ValueError:
        return False
    domain = email.rsplit('@', 1)[1]
    return domain in policy['allowed_domains'] or domain in policy['exceptions'] or email in policy['exceptions']


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def account_requires_email(user, authenticated_at=None):
    if user.role == 'user':
        return school_email_policy(user.school)['enabled'] and (
            not user.email_verified_at or not user.email or not email_allowed(user.school, user.email)
        )
    if user.role != 'admin' or not user.admin_email_required_at:
        return False
    if user.email_verified_at and aware(user.email_verified_at) >= aware(user.admin_email_required_at):
        return False
    if authenticated_at is None:
        return True
    try:
        login_at = aware(datetime.fromisoformat(authenticated_at))
    except (ValueError, TypeError):
        return False  # Existing sessions predate this feature and the requirement.
    return login_at >= aware(user.admin_email_required_at)
