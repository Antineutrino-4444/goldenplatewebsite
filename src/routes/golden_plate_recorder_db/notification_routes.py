import json

from flask import make_response, redirect, render_template_string, request, url_for
from sqlalchemy import func

from . import recorder_bp
from .db import EmailNotificationPreference, School, db_session
from src.services.notification_preferences import NOTIFICATION_TYPES
from src.services.website_notifications import get_website_update_recipients


def _configured_types(email, known_types):
    configured = set()
    if email in {recipient.lower() for recipient in get_website_update_recipients()}:
        configured.update({'server_startup', 'school_registration', 'account_signup', 'invite_signup', 'map_submission'})
    if db_session.query(School.id).filter(func.lower(School.contact_email) == email).first():
        configured.update({'account_signup', 'invite_signup'})
    from .map_routes import _get_map_approval_notify_recipients
    if email in {recipient.lower() for recipient in _get_map_approval_notify_recipients()}:
        configured.add('map_submission')
    if 'map_status' in known_types:
        configured.add('map_status')
    return configured


@recorder_bp.route('/notifications/preferences/<token>', methods=['GET', 'POST'])
def notification_preferences(token):
    preference = db_session.query(EmailNotificationPreference).filter_by(token=token).first() if len(token) == 43 else None
    if not preference:
        return 'This notification preferences link is invalid. Please use the link in a recent Golden Plate email.', 404
    if request.method == 'POST':
        if request.form.get('action') not in {'save', 'unsubscribe_all'}:
            return 'Choose Save preferences or Unsubscribe from all notifications.', 400
        if request.form.get('action') == 'unsubscribe_all':
            disabled = set(NOTIFICATION_TYPES)
        else:
            disabled = {key for key in NOTIFICATION_TYPES if request.form.get(key) != 'on'}
        preference.disabled_types = json.dumps(sorted(disabled))
        db_session.commit()
        return redirect(url_for('recorder.notification_preferences', token=token, saved=1), code=303)

    disabled = set(json.loads(preference.disabled_types))
    configured = _configured_types(preference.email, json.loads(preference.known_types))
    response = make_response(render_template_string(PREFERENCES_PAGE,
        email=preference.email, types=NOTIFICATION_TYPES, disabled=disabled,
        configured=configured, saved=request.args.get('saved') == '1'))
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


PREFERENCES_PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Notification preferences · Golden Plate</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f8fafc;color:#17212f;font:16px/1.5 system-ui,sans-serif}
main{max-width:680px;margin:48px auto;padding:28px;background:white;border:1px solid #e2e8f0;border-radius:18px}
.brand{color:#d86a00;font-size:24px;font-weight:800}h1{font-size:28px;line-height:1.2;margin:14px 0}
p{color:#586577}.email{overflow-wrap:anywhere;font-weight:600}.row{display:flex;gap:14px;padding:18px 0;border-top:1px solid #e2e8f0;cursor:pointer}
input{width:20px;height:20px;flex-shrink:0;margin-top:4px;accent-color:#0f766e}.row span{min-width:0}.row strong{display:block}
small{display:block;color:#586577}.status{margin-top:5px;font-size:12px;color:#0f766e}.buttons{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}
button{padding:12px 18px;border-radius:9px;border:1px solid #cbd5e1;background:white;font:inherit;cursor:pointer}.save{background:#0f766e;color:white;border-color:#0f766e}
.notice{padding:12px;border-radius:8px;background:#ecfdf5;color:#065f46}.note{font-size:13px;margin-top:24px}
@media(max-width:720px){main{margin:16px;padding:20px}h1{font-size:24px}}
</style></head><body><main>
<div class="brand">PLATE</div><h1>Notification preferences</h1>
<p class="email">{{email}}</p>
<p>Choose the notifications you want to receive. Enabled types are sent when your address is on the relevant recipient list.</p>
{% if saved %}<p class="notice" role="status">Your preferences have been saved.</p>{% endif %}
<form method="post">
{% for key, description in types.items() %}
<label class="row"><input type="checkbox" name="{{key}}" {% if key not in disabled %}checked{% endif %}>
<span><strong>{{description[0]}}</strong><small>{{description[1]}}</small>
<span class="status">{% if key in disabled %}Unsubscribed{% elif key in configured %}Currently subscribed{% else %}Enabled · no recipient list configured for this address{% endif %}</span></span></label>
{% endfor %}
<div class="buttons"><button class="save" type="submit" name="action" value="save">Save preferences</button>
<button type="submit" name="action" value="unsubscribe_all">Unsubscribe from all notifications</button></div>
</form>
<p class="note">Verification codes you request will still be sent. Changing these preferences does not add your address to any recipient list.</p>
</main></body></html>'''
