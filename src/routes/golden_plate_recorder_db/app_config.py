import os


DEVELOPMENT_ENVIRONMENTS = {'development', 'dev', 'local', 'test', 'testing'}
PRODUCTION_ENVIRONMENTS = {'production', 'prod'}


def get_app_environment():
    raw_value = (
        os.environ.get('APP_ENV')
        or os.environ.get('ENVIRONMENT')
        or os.environ.get('FLASK_ENV')
        or 'development'
    )
    normalized = raw_value.strip().lower()
    if normalized in PRODUCTION_ENVIRONMENTS:
        return 'production'
    if normalized in DEVELOPMENT_ENVIRONMENTS:
        return 'development'
    return normalized or 'development'


def is_development_environment():
    return get_app_environment() == 'development'


def is_production_environment():
    return get_app_environment() == 'production'


def default_admin_credentials_enabled():
    return is_development_environment()


def serialize_app_environment():
    environment = get_app_environment()
    return {
        'environment': environment,
        'is_development': is_development_environment(),
        'is_production': is_production_environment(),
        'default_admin_credentials_enabled': default_admin_credentials_enabled(),
    }


__all__ = [
    'default_admin_credentials_enabled',
    'get_app_environment',
    'is_development_environment',
    'is_production_environment',
    'serialize_app_environment',
]
