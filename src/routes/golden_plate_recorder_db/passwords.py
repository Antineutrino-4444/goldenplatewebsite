import hmac

from werkzeug.security import check_password_hash, generate_password_hash


HASH_METHOD_PREFIXES = ('pbkdf2:', 'scrypt:')


def is_password_hash(stored_value):
    if not isinstance(stored_value, str):
        return False
    return stored_value.startswith(HASH_METHOD_PREFIXES) and stored_value.count('$') >= 2


def hash_password(plaintext):
    return generate_password_hash(plaintext or '', method='pbkdf2:sha256:1000000')


def verify_password(stored_value, plaintext):
    if not stored_value:
        return False
    if is_password_hash(stored_value):
        try:
            return check_password_hash(stored_value, plaintext or '')
        except ValueError:
            return False
    return hmac.compare_digest(str(stored_value), plaintext or '')


__all__ = ['hash_password', 'is_password_hash', 'verify_password']
