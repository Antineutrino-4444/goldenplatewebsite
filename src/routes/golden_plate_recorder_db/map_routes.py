import logging
import os
import random
import re
import secrets
import string
import base64
from datetime import timedelta, timezone
from io import BytesIO
import html as _html_lib

import requests as http_requests
from flask import jsonify, request, send_file, session
from sqlalchemy import func
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from . import recorder_bp
from .db import DEFAULT_SCHOOL_ID
from .email_service import VERIFICATION_CODE_EXPIRY_MINUTES, send_email_via_brevo
from .map_db import (
    MapBackground,
    MapEmailVerification,
    MapPin,
    MapSetting,
    MapSubmission,
    MapSubmissionImage,
    MapSubmitterAccount,
    _map_now_utc,
    map_db_session,
)
from .security import get_current_user, is_interschool_user, require_admin, require_superadmin

logger = logging.getLogger(__name__)

MAP_VERIFICATION_PURPOSE = 'map_submission'
MAX_VERIFICATION_ATTEMPTS = 5
MAP_EMAIL_VERIFICATION_MAX_AGE_MINUTES = 30
MAX_IMAGE_BYTES = 50 * 1024 * 1024
# Recipients notified whenever a new map submission is awaiting approval.
# Override at runtime via the MAP_APPROVAL_NOTIFY_EMAILS env var (comma-separated)
# or — preferred — from the Map admin UI (stored in the ``map_settings`` table
# under the key below).
DEFAULT_MAP_APPROVAL_NOTIFY_EMAILS = (
    'antineutrino-044@outlook.com',
    'leo.li2026@sac.on.ca',
    'nick.wang@sac.on.ca',
    'matthew.jaekel@sac.on.ca',
)
MAP_SETTING_APPROVAL_RECIPIENTS = 'approval_notify_emails'
# Image MIMEs that browsers can render natively in <img> tags.
BROWSER_NATIVE_IMAGE_MIMES = {
    'image/jpeg',
    'image/pjpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/avif',
    'image/bmp',
    'image/x-bmp',
    'image/x-ms-bmp',
    'image/vnd.microsoft.icon',
    'image/x-icon',
}
# Image MIMEs the server should transcode to PNG before storing/serving,
# because browsers can't decode them in <img> or because we want to strip
# any embedded scripts (SVG).
HEIC_IMAGE_MIMES = {'image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'}
TIFF_IMAGE_MIMES = {'image/tiff', 'image/tif', 'image/x-tiff'}
SVG_IMAGE_MIMES = {'image/svg+xml', 'image/svg'}
# Camera RAW formats. We list a representative set of common MIMEs; most
# browsers don't actually emit MIMEs for these so the file extension below
# is what usually triggers conversion.
RAW_IMAGE_MIMES = {
    'image/x-canon-cr2', 'image/x-canon-cr3', 'image/x-canon-crw',
    'image/x-nikon-nef', 'image/x-nikon-nrw',
    'image/x-sony-arw', 'image/x-sony-srf', 'image/x-sony-sr2',
    'image/x-fuji-raf', 'image/x-fujifilm-raf',
    'image/x-adobe-dng', 'image/dng',
    'image/x-olympus-orf',
    'image/x-panasonic-rw2', 'image/x-panasonic-raw',
    'image/x-pentax-pef',
    'image/x-samsung-srw',
    'image/x-sigma-x3f',
    'image/x-leica-rwl',
}
SERVER_CONVERTIBLE_IMAGE_MIMES = (
    HEIC_IMAGE_MIMES | TIFF_IMAGE_MIMES | SVG_IMAGE_MIMES | RAW_IMAGE_MIMES
)
ALLOWED_IMAGE_MIMES = BROWSER_NATIVE_IMAGE_MIMES  # kept for backward compat
HEIC_FILE_EXTENSIONS = ('.heic', '.heif')
TIFF_FILE_EXTENSIONS = ('.tif', '.tiff')
SVG_FILE_EXTENSIONS = ('.svg',)
RAW_FILE_EXTENSIONS = (
    '.cr2', '.cr3', '.crw',
    '.nef', '.nrw',
    '.arw', '.srf', '.sr2',
    '.raf',
    '.dng',
    '.orf',
    '.rw2', '.raw',
    '.pef',
    '.srw',
    '.x3f',
    '.rwl',
    '.iiq',
    '.3fr',
    '.kdc',
    '.dcr',
    '.mrw',
)
SERVER_CONVERTIBLE_FILE_EXTENSIONS = (
    HEIC_FILE_EXTENSIONS + TIFF_FILE_EXTENSIONS
    + SVG_FILE_EXTENSIONS + RAW_FILE_EXTENSIONS
)
ALLOWED_IMAGE_FILE_EXTENSIONS = (
    '.jpg', '.jpeg', '.jpe', '.jfif',
    '.png', '.gif', '.webp', '.avif',
    '.bmp', '.dib', '.ico',
)
IMAGE_TYPE_ERROR_MESSAGE = (
    'Image must be a JPG, PNG, WebP, GIF, AVIF, BMP, ICO, HEIC/HEIF, '
    'TIFF, SVG, or camera RAW file'
)
SAC_EMAIL_SUFFIX = '@sac.on.ca'

# Register HEIC/HEIF support with Pillow if pillow-heif is installed.
try:
    from pillow_heif import register_heif_opener  # type: ignore
    register_heif_opener()
    _HEIC_SUPPORTED = True
except Exception:  # pragma: no cover - dependency missing
    _HEIC_SUPPORTED = False

try:
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - dependency missing
    Image = None  # type: ignore
    _PIL_AVAILABLE = False

# SVG -> PNG (safe pure-Python path: defusedxml + svglib + reportlab).
try:
    from defusedxml import ElementTree as _DefusedET  # type: ignore
    from svglib.svglib import svg2rlg  # type: ignore
    from reportlab.graphics import renderPM  # type: ignore
    _SVG_SUPPORTED = True
except Exception:  # pragma: no cover - dependency missing
    _DefusedET = None  # type: ignore
    svg2rlg = None  # type: ignore
    renderPM = None  # type: ignore
    _SVG_SUPPORTED = False

# Camera RAW decoding via libraw.
try:
    import rawpy  # type: ignore
    import numpy as _np  # type: ignore
    _RAW_SUPPORTED = True
except Exception:  # pragma: no cover - dependency missing
    rawpy = None  # type: ignore
    _np = None  # type: ignore
    _RAW_SUPPORTED = False


def _is_heic_upload(filename: str | None, mime: str | None) -> bool:
    if mime and mime.lower() in HEIC_IMAGE_MIMES:
        return True
    if filename and filename.lower().endswith(HEIC_FILE_EXTENSIONS):
        return True
    return False


def _needs_server_image_conversion(filename: str | None, mime: str | None) -> bool:
    if mime and mime.lower() in SERVER_CONVERTIBLE_IMAGE_MIMES:
        return True
    if filename and filename.lower().endswith(SERVER_CONVERTIBLE_FILE_EXTENSIONS):
        return True
    return False


def _is_browser_native_image(filename: str | None, mime: str | None) -> bool:
    if mime and mime.lower() in BROWSER_NATIVE_IMAGE_MIMES:
        return True
    if filename and filename.lower().endswith(ALLOWED_IMAGE_FILE_EXTENSIONS):
        return True
    return False


def _is_svg_upload(filename: str | None, mime: str | None) -> bool:
    if mime and mime.lower() in SVG_IMAGE_MIMES:
        return True
    if filename and filename.lower().endswith(SVG_FILE_EXTENSIONS):
        return True
    return False


def _is_raw_upload(filename: str | None, mime: str | None) -> bool:
    if mime and mime.lower() in RAW_IMAGE_MIMES:
        return True
    if filename and filename.lower().endswith(RAW_FILE_EXTENSIONS):
        return True
    return False


def _normalize_svg_to_png(raw_bytes: bytes) -> tuple[bytes, str, str] | None:
    """Rasterize an SVG document to a PNG, defusing any embedded scripts.

    SVG is XML and can contain <script> tags or external references; we parse
    with defusedxml first to block XXE/billion-laughs and strip script/foreign
    nodes, then rasterize with svglib + reportlab (pure Python — no Cairo).
    """
    if not _SVG_SUPPORTED:
        return None
    try:
        # Parse safely first (defusedxml blocks XXE / entity expansion).
        root = _DefusedET.fromstring(raw_bytes)
        # Strip <script> and on*= event handlers from the tree before
        # handing to svglib (defense-in-depth — svglib doesn't execute JS,
        # but the rendered PNG should never embed any active content).
        ns_strip = re.compile(r'^\{[^}]+\}')
        for elem in list(root.iter()):
            tag_local = ns_strip.sub('', elem.tag).lower() if isinstance(elem.tag, str) else ''
            if tag_local in ('script', 'foreignobject'):
                # Detach by clearing attributes and tag (we can't easily
                # remove from parent in ElementTree without traversal).
                elem.clear()
                elem.tag = 'removed'
            for attr in list(elem.attrib.keys()):
                if attr.lower().startswith('on') or attr.lower() == 'href' and (
                    elem.attrib[attr].lower().startswith('javascript:')
                ):
                    del elem.attrib[attr]
        cleaned = _DefusedET.tostring(root)
        drawing = svg2rlg(BytesIO(cleaned))
        if drawing is None:
            return None
        out = BytesIO()
        renderPM.drawToFile(drawing, out, fmt='PNG')
        return out.getvalue(), 'image/png', '.png'
    except Exception:
        logger.exception('Failed to convert SVG image to PNG')
        return None


def _normalize_raw_to_png(raw_bytes: bytes) -> tuple[bytes, str, str] | None:
    """Decode a camera RAW file (CR2/NEF/ARW/DNG/...) and re-encode as PNG."""
    if not (_RAW_SUPPORTED and _PIL_AVAILABLE):
        return None
    try:
        with rawpy.imread(BytesIO(raw_bytes)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False, output_bps=8)
        img = Image.fromarray(rgb)
        out = BytesIO()
        img.save(out, format='PNG', optimize=True, compress_level=6)
        return out.getvalue(), 'image/png', '.png'
    except Exception:
        logger.exception('Failed to convert RAW image to PNG')
        return None


def _normalize_image_to_png(raw_bytes: bytes, *, filename: str | None = None, mime: str | None = None) -> tuple[bytes, str, str] | None:
    """Decode any supported image and re-encode losslessly as PNG.

    Used for HEIC/HEIF, TIFF, SVG, camera RAW, and other formats browsers
    can't render in <img>. PNG is fully lossless, so no quality is lost
    during conversion beyond what the source format itself stored.
    Returns (png_bytes, 'image/png', '.png') or None if decoding failed.
    """
    # SVG and RAW need dedicated decoders; everything else can go through Pillow.
    if _is_svg_upload(filename, mime):
        return _normalize_svg_to_png(raw_bytes)
    if _is_raw_upload(filename, mime):
        return _normalize_raw_to_png(raw_bytes)
    if not _PIL_AVAILABLE:
        return None
    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            img.load()
            # Preserve transparency if present; otherwise keep RGB.
            if img.mode not in ('RGB', 'RGBA', 'L', 'LA', 'I', 'I;16'):
                img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')
            out = BytesIO()
            # PNG is lossless. compress_level only affects file size / CPU.
            img.save(out, format='PNG', optimize=True, compress_level=6)
            return out.getvalue(), 'image/png', '.png'
    except Exception:
        logger.exception('Failed to convert image to PNG')
        return None


# Backward-compatible alias kept for any external callers.
_normalize_heic_to_jpeg = _normalize_image_to_png


RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


def _map_error(code, message, status=400, *, detail=None):
    payload = {
        'status': 'error',
        'code': code,
        'error': message,
        'http_status': status,
    }
    if detail:
        payload['detail'] = detail
    return jsonify(payload), status


def _purge_orphan_image_data():
    """Sweep image bytes that are no longer associated with a live entry.

    Deletes / nulls:
      * `MapSubmissionImage` rows whose `submission_id` does not exist in
        `map_submissions` (broken FK references — should not normally happen,
        but defensively cleans up legacy data).
      * `MapSubmissionImage` rows whose parent submission has been rejected
        (rejected submissions are not displayed, so their image bytes serve
        no purpose).
      * `MapSubmission.image_data` blobs on rejected rows (clears legacy
        rejected entries that pre-date the on-reject purge).

    Safe to call from any read endpoint; commits its own transaction. Errors
    are logged and swallowed so a sweep failure never blocks the response.
    """
    try:
        live_ids_subquery = map_db_session.query(MapSubmission.id).subquery()
        rejected_ids_subquery = (
            map_db_session.query(MapSubmission.id)
            .filter(MapSubmission.status == 'rejected')
            .subquery()
        )

        orphan_count = (
            map_db_session.query(MapSubmissionImage)
            .filter(~MapSubmissionImage.submission_id.in_(live_ids_subquery.select()))
            .delete(synchronize_session=False)
        )
        rejected_extra_count = (
            map_db_session.query(MapSubmissionImage)
            .filter(MapSubmissionImage.submission_id.in_(rejected_ids_subquery.select()))
            .delete(synchronize_session=False)
        )
        rejected_blob_count = (
            map_db_session.query(MapSubmission)
            .filter(
                MapSubmission.status == 'rejected',
                MapSubmission.image_data.isnot(None),
            )
            .update(
                {MapSubmission.image_data: None, MapSubmission.image_size: 0},
                synchronize_session=False,
            )
        )

        if orphan_count or rejected_extra_count or rejected_blob_count:
            map_db_session.commit()
            logger.info(
                'Purged orphan map image data (orphan_extras=%d, rejected_extras=%d, rejected_blobs=%d)',
                orphan_count, rejected_extra_count, rejected_blob_count,
            )
        else:
            map_db_session.rollback()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('Orphan image sweep failed: %s', exc)
        try:
            map_db_session.rollback()
        except Exception:
            pass


@recorder_bp.app_errorhandler(RequestEntityTooLarge)
def handle_map_request_too_large(error):
    if request.path.startswith('/api/map/'):
        return _map_error(
            'MAP_IMAGE_TOO_LARGE',
            'Image must be 50 MB or smaller',
            413,
        )
    return error.get_response()


@recorder_bp.before_app_request
def _block_interschool_from_map():
    if not request.path.startswith('/api/map/'):
        return None
    if is_interschool_user():
        return _map_error(
            'MAP_INTERSCHOOL_FORBIDDEN',
            'Inter-school admin accounts cannot access the Ecological Map',
            403,
        )
    return None


def _verify_recaptcha(token):
    if not RECAPTCHA_SECRET_KEY:
        return True

    if not token:
        return False

    try:
        response = http_requests.post(
            RECAPTCHA_VERIFY_URL,
            data={
                'secret': RECAPTCHA_SECRET_KEY,
                'response': token,
            },
            timeout=10,
        )
        result = response.json()
        return result.get('success', False)
    except Exception:
        return False


def _normalize_email(value):
    return (value or '').strip().lower()


def _is_sac_email(email):
    return _normalize_email(email).endswith(SAC_EMAIL_SUFFIX)


def _get_map_approval_notify_recipients():
    """Return the list of emails to notify when a new map submission arrives.

    Resolution order (first non-empty wins):
      1. ``map_settings.approval_notify_emails`` row in the DB (managed
         from the Map admin UI by superadmins).
      2. ``MAP_APPROVAL_NOTIFY_EMAILS`` env var (comma-separated).
      3. ``DEFAULT_MAP_APPROVAL_NOTIFY_EMAILS`` constant.
    """
    raw = ''
    try:
        setting = (
            map_db_session.query(MapSetting)
            .filter(MapSetting.key == MAP_SETTING_APPROVAL_RECIPIENTS)
            .first()
        )
        if setting and (setting.value or '').strip():
            raw = setting.value
    except Exception:
        logger.exception('Failed to read approval recipients from map_settings')
        raw = ''

    if not raw.strip():
        raw = os.environ.get('MAP_APPROVAL_NOTIFY_EMAILS', '')

    if raw.strip():
        recipients = _parse_email_list(raw)
    else:
        recipients = list(DEFAULT_MAP_APPROVAL_NOTIFY_EMAILS)

    # Deduplicate while preserving order, ignoring case.
    seen = set()
    unique = []
    for email_addr in recipients:
        normalized = email_addr.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(email_addr)
    return unique


_EMAIL_SPLIT_RE = re.compile(r'[\s,;]+')
# Loose RFC-5322-ish check; we are not delivering ourselves, just keeping
# obvious garbage out of the recipients list.
_EMAIL_VALIDATE_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _parse_email_list(raw):
    """Split a free-form input ("a@b.com, c@d.com\nfoo@bar.com") into a
    cleaned list of email addresses. Whitespace, commas, semicolons, and
    newlines are all valid separators."""
    if not raw:
        return []
    parts = [p.strip() for p in _EMAIL_SPLIT_RE.split(raw) if p.strip()]
    return parts


def _try_lossless_recompress(data: bytes, mime: str | None, filename: str | None):
    """Attempt to losslessly recompress an image into smaller bytes.

    Returns ``(new_bytes, new_mime, new_filename)`` if a smaller, fully
    lossless representation was produced, otherwise ``None``. We try a
    handful of strategies and pick whichever yields the smallest output:

    * Re-save PNG with maximum DEFLATE effort (``compress_level=9``,
      ``optimize=True``). Pixel-identical, often a meaningful win for
      PNGs saved with low effort.
    * Re-encode as **lossless WebP** (``lossless=True``, ``method=6``,
      ``quality=100``). Lossless WebP frequently beats PNG by 20–40%
      for photographic content while remaining bit-exact pixel-wise.

    JPEGs are skipped (no truly lossless re-encoding gain), as are
    formats Pillow can't decode. The returned filename has its extension
    swapped to match the new format so the attachment opens correctly.
    """
    if not data or not _PIL_AVAILABLE:
        return None
    normalized_mime = (mime or '').lower()
    # Don't bother with JPEG — there's no meaningful lossless re-pack.
    if normalized_mime in ('image/jpeg', 'image/jpg'):
        return None
    try:
        with Image.open(BytesIO(data)) as img:
            img.load()
            # Pillow's WebP encoder requires RGB/RGBA; keep alpha if present.
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')

            candidates: list[tuple[bytes, str, str]] = []

            # Try optimized PNG (always pixel-identical).
            try:
                buf = BytesIO()
                img.save(buf, format='PNG', optimize=True, compress_level=9)
                candidates.append((buf.getvalue(), 'image/png', '.png'))
            except Exception:
                logger.exception('Lossless PNG re-encode failed for %s', filename)

            # Try lossless WebP (also pixel-identical when lossless=True).
            try:
                buf = BytesIO()
                img.save(buf, format='WEBP', lossless=True, quality=100, method=6)
                candidates.append((buf.getvalue(), 'image/webp', '.webp'))
            except Exception:
                logger.exception('Lossless WebP re-encode failed for %s', filename)

            if not candidates:
                return None

            best_bytes, best_mime, best_ext = min(candidates, key=lambda c: len(c[0]))
            # Only return the recompressed version if it actually saved bytes.
            if len(best_bytes) >= len(data):
                return None

            base = (filename or 'image').rsplit('.', 1)[0] or 'image'
            new_name = f'{base}{best_ext}'
            return best_bytes, best_mime, new_name
    except Exception:
        logger.exception('Lossless recompression failed for %s', filename)
        return None


def _collect_submission_image_attachments(submission, max_total_bytes: int = 20 * 1024 * 1024):
    """Return ``(attachments, image_infos)`` for emails.

    * ``attachments`` is a list of Brevo-shaped ``{"name", "content"}`` dicts
      where ``content`` is base64-encoded image bytes, ready to pass to
      :func:`send_email_via_brevo`.
    * ``image_infos`` is a parallel list of dicts shaped like::

          {
            "name": str,           # filename
            "mime": str | None,    # content-type
            "size": int,           # bytes (0 if missing)
            "attached": bool,      # True if included in attachments list
            "data_uri": str | None,# data: URI for inline <img>, if embeddable
            "note": str,           # human-readable status string
          }

      ``data_uri`` is populated only when the image looked like a real
      raster/vector image and inlining it stays within the inline budget,
      so callers can render it directly inside the HTML body.

    Attachments are skipped (and noted in ``note``) if adding them would
    push the total payload past ``max_total_bytes`` (default 20 MB) so we
    stay under Brevo's per-message limit. When a single image won't fit,
    we first try a fully-lossless recompression pass (optimized PNG /
    lossless WebP) and use the smaller version when available.
    """
    attachments: list[dict] = []
    image_infos: list[dict] = []
    total_bytes = 0
    inline_bytes = 0

    # Inline embedding budgets. Each inlined image is base64-encoded inside
    # the HTML body, which is roughly +33% over the raw size, and it lives
    # *in addition to* the binary attachment. Keep these conservative so
    # we don't blow past Brevo's overall message size limit.
    inline_total_budget = 14 * 1024 * 1024  # ~14 MB of raw bytes inlined total
    inline_per_image_budget = 5 * 1024 * 1024  # never inline images > 5 MB
    inline_image_mimes = {
        'image/png', 'image/jpeg', 'image/jpg', 'image/gif',
        'image/webp', 'image/bmp', 'image/svg+xml',
    }

    def _consider(filename, mime, data):
        """Try to attach + inline a single image. Always appends one entry
        to ``image_infos`` describing the outcome.

        If the raw image won't fit in the remaining attachment budget, we
        attempt a fully-lossless recompression (optimized PNG / lossless
        WebP) and use the smaller version when it actually fits.
        """
        nonlocal total_bytes, inline_bytes
        info = {
            'name': filename or 'image',
            'mime': mime,
            'size': len(data) if data else 0,
            'attached': False,
            'data_uri': None,
            'note': '',
        }
        if not data:
            info['note'] = 'no image data'
            image_infos.append(info)
            return

        original_size = info['size']
        recompressed_note = ''

        # If it doesn't fit as-is, try a lossless recompression pass.
        if total_bytes + original_size > max_total_bytes:
            recompressed = _try_lossless_recompress(data, mime, filename)
            if recompressed is not None:
                new_data, new_mime, new_name = recompressed
                if total_bytes + len(new_data) <= max_total_bytes:
                    saved = original_size - len(new_data)
                    recompressed_note = (
                        f' (losslessly recompressed: {original_size} → {len(new_data)} bytes, '
                        f'saved {saved})'
                    )
                    data = new_data
                    mime = new_mime
                    info['name'] = new_name
                    info['mime'] = new_mime
                    info['size'] = len(new_data)

        size = info['size']

        # Try to attach.
        if total_bytes + size > max_total_bytes:
            info['note'] = (
                f'skipped — too large to attach ({original_size} bytes, would exceed '
                f'{max_total_bytes // (1024 * 1024)} MB cap)'
                + (recompressed_note if recompressed_note else '')
            )
        else:
            try:
                encoded = base64.b64encode(data).decode('ascii')
            except Exception:
                logger.exception('Failed to base64-encode attachment %s', filename)
                info['note'] = 'failed to encode'
                image_infos.append(info)
                return
            attachments.append({'name': info['name'], 'content': encoded})
            total_bytes += size
            info['attached'] = True
            info['note'] = f'{mime or "?"}, {size} bytes' + recompressed_note

            # Try to inline-embed (only for genuine image MIME types, and
            # only if we haven't blown the inline budget).
            normalized_mime = (mime or '').lower()
            if (
                normalized_mime in inline_image_mimes
                and size <= inline_per_image_budget
                and inline_bytes + size <= inline_total_budget
            ):
                info['data_uri'] = f'data:{normalized_mime};base64,{encoded}'
                inline_bytes += size

        image_infos.append(info)

    if submission.image_data:
        primary_name = submission.image_filename or f'submission-{submission.id}.bin'
        _consider(primary_name, submission.image_mime, submission.image_data)

    try:
        extras = (
            map_db_session.query(MapSubmissionImage)
            .filter(MapSubmissionImage.submission_id == submission.id)
            .order_by(MapSubmissionImage.position.asc(), MapSubmissionImage.created_at.asc())
            .all()
        )
    except Exception:
        logger.exception('Failed to load extra images for email attachments')
        extras = []

    for idx, extra in enumerate(extras, start=1):
        extra_name = extra.image_filename or f'submission-{submission.id}-extra-{idx}.bin'
        _consider(extra_name, extra.image_mime, extra.image_data)

    return attachments, image_infos


def _render_image_descriptions_html(image_infos):
    """Render the image list as HTML for inclusion in emails.

    Each image gets a labeled card. When a ``data_uri`` is available the
    image is embedded inline so reviewers see it without opening the
    attachment; otherwise we just describe what was attached (or skipped).

    For backwards compatibility, plain strings are accepted and rendered
    as a simple bulleted list.
    """
    if not image_infos:
        return '<em style="color:#64748b;">No images.</em>'

    # Legacy: list of plain strings.
    if all(isinstance(item, str) for item in image_infos):
        items = ''.join(
            f'<li style="font-size:13px;color:#334155;">{_html_lib.escape(item)}</li>'
            for item in image_infos
        )
        return f'<ul style="margin:6px 0 0 18px; padding:0;">{items}</ul>'

    cards = []
    for info in image_infos:
        if not isinstance(info, dict):
            continue
        name = _html_lib.escape(info.get('name') or 'image')
        note = _html_lib.escape(info.get('note') or '')
        data_uri = info.get('data_uri')
        if data_uri:
            # Inline preview. Cap rendered width so wide images don't break
            # email layouts. The data URI is safe to drop into src as-is
            # because base64 is URL-safe in this context.
            preview = (
                f'<div style="margin-top:6px;">'
                f'<img src="{data_uri}" alt="{name}" '
                f'style="max-width:100%; height:auto; border:1px solid #e2e8f0; '
                f'border-radius:6px; display:block;" />'
                f'</div>'
            )
        else:
            preview = (
                '<div style="margin-top:6px; font-size:12px; color:#64748b;">'
                '(Inline preview unavailable — see attachment.)'
                '</div>'
            )
        cards.append(
            '<div style="margin:10px 0; padding:10px; border:1px solid #e2e8f0; '
            'border-radius:8px; background:#f8fafc;">'
            f'<div style="font-size:13px; color:#0f172a;">'
            f'<strong>{name}</strong> '
            f'<span style="color:#64748b;">— {note}</span>'
            f'</div>'
            f'{preview}'
            '</div>'
        )
    return ''.join(cards)


def _notify_pending_map_submission(submission, base_url=None):
    """Send a notification email to the configured reviewers about a new
    pending map submission.

    The email includes:
      * full submission metadata (title, submitter, pin, description)
      * every attached image, embedded as a base64 attachment so it
        renders/downloads without an authenticated session
      * a single-use "quick approve" link that approves the submission
        without requiring the reviewer to log in (it works once)

    Failures are logged and never raised so they cannot block the
    submission flow.
    """
    try:
        recipients = _get_map_approval_notify_recipients()
        if not recipients:
            return

        title = (submission.title or '').strip() or '(no title)'
        submitter_email = submission.email or ''
        submitter_name = (
            submission.submission_display_name
            or submission.submitted_display_name
            or submission.submitted_username
            or 'Anonymous'
        )
        text_full = (submission.text_content or '').strip()

        # Pin (if any).
        pin_label = '(no pin / "Others")'
        if submission.pin_id:
            try:
                pin = (
                    map_db_session.query(MapPin)
                    .filter(MapPin.id == submission.pin_id)
                    .first()
                )
                if pin:
                    pin_label = f'{pin.name} ({pin.x:.1f}, {pin.y:.1f})'
                else:
                    pin_label = f'(unknown pin: {submission.pin_id})'
            except Exception:
                logger.exception('Failed to look up pin %s for notification', submission.pin_id)

        submitted_at_str = ''
        if submission.submitted_at:
            try:
                submitted_at_str = submission.submitted_at.strftime('%B %d, %Y at %I:%M %p UTC')
            except Exception:
                submitted_at_str = str(submission.submitted_at)

        # Quick-approve link.
        public_base = (
            os.environ.get('MAP_PUBLIC_BASE_URL', '').strip().rstrip('/')
            or (base_url or '').strip().rstrip('/')
        )
        approval_url = None
        if submission.approval_token and public_base:
            approval_url = (
                f'{public_base}/api/map/submissions/{submission.id}'
                f'/quick-approve?token={submission.approval_token}'
            )

        # Collect images as Brevo attachments (base64).
        attachments, image_descriptions = _collect_submission_image_attachments(submission)

        # Build HTML.
        safe_title = _html_lib.escape(title)
        safe_name = _html_lib.escape(submitter_name)
        safe_email = _html_lib.escape(submitter_email)
        safe_text = (_html_lib.escape(text_full).replace('\n', '<br>')
                     if text_full else '<em>(no description)</em>')
        safe_pin = _html_lib.escape(pin_label)
        safe_submission_id = _html_lib.escape(submission.id or '')
        safe_submitted_at = _html_lib.escape(submitted_at_str)
        safe_school_id = _html_lib.escape(submission.school_id or '')
        safe_status = _html_lib.escape(submission.status or '')
        safe_submitted_by_role = _html_lib.escape(submission.submitted_role or '')
        safe_submitted_by_username = _html_lib.escape(submission.submitted_username or '(guest)')

        if image_descriptions:
            images_html = _render_image_descriptions_html(image_descriptions)
        else:
            images_html = '<em style="color:#64748b;">No images.</em>'

        if approval_url:
            safe_url = _html_lib.escape(approval_url, quote=True)
            quick_approve_html = f'''
              <div style="margin-top: 24px; padding: 16px; border:1px solid #fcd34d; background:#fffbeb; border-radius:8px;">
                <div style="font-weight:700; color:#78350f; margin-bottom:8px;">⚡ Speed approval link (single use)</div>
                <p style="margin:0 0 12px; font-size:13px; color:#78350f;">
                  Clicking this approves the submission immediately. No login required.
                  The link works <strong>once</strong> and is invalidated as soon as it is used
                  (or as soon as anyone reviews the submission).
                </p>
                <a href="{safe_url}" style="display:inline-block; background:#16a34a; color:#ffffff; text-decoration:none; padding:10px 18px; border-radius:6px; font-weight:600;">
                  Approve submission
                </a>
                <div style="margin-top:10px; font-size:11px; color:#92400e; word-break:break-all;">
                  {safe_url}
                </div>
              </div>
            '''
        else:
            quick_approve_html = (
                '<p style="margin-top:16px; font-size:13px; color:#64748b;">'
                '(Quick approval link unavailable — server could not determine its public URL.)'
                '</p>'
            )

        subject = f'[Golden Plate Map] New submission pending approval: {title}'
        html = f"""
        <div style="font-family: Arial, sans-serif; color: #0f172a; max-width: 680px;">
          <h2 style="color:#0f766e; margin-bottom:8px;">New Ecological Map submission awaiting approval</h2>
          <p style="margin:0 0 16px;">A new submission has been received and is pending review.</p>

          <table style="border-collapse: collapse; font-size: 14px; width:100%;">
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Title</strong></td><td style="padding:4px 0;">{safe_title}</td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Submitted by</strong></td><td style="padding:4px 0;">{safe_name} &lt;{safe_email}&gt;</td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Account</strong></td><td style="padding:4px 0;">@{safe_submitted_by_username} ({safe_submitted_by_role or 'guest'})</td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Pin</strong></td><td style="padding:4px 0;">{safe_pin}</td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Submitted at</strong></td><td style="padding:4px 0;">{safe_submitted_at or '—'}</td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Status</strong></td><td style="padding:4px 0;">{safe_status}</td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>Submission ID</strong></td><td style="padding:4px 0;"><code>{safe_submission_id}</code></td></tr>
            <tr><td style="padding:4px 12px 4px 0; color:#475569; vertical-align:top;"><strong>School ID</strong></td><td style="padding:4px 0;"><code>{safe_school_id}</code></td></tr>
          </table>

          <h3 style="margin-top:20px; margin-bottom:6px; font-size:14px; color:#475569;">Description</h3>
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:12px; font-size:14px; line-height:1.5; white-space:pre-wrap;">{safe_text}</div>

          <h3 style="margin-top:20px; margin-bottom:6px; font-size:14px; color:#475569;">Images attached to this email</h3>
          {images_html}

          {quick_approve_html}

          <p style="margin-top:24px; font-size:12px; color:#94a3b8;">
            You can also open the Ecological Map admin view in your browser to review/reject this submission.
          </p>
        </div>
        """.strip()

        for recipient in recipients:
            try:
                result = send_email_via_brevo(
                    recipient,
                    subject,
                    html,
                    attachments=attachments or None,
                )
                if not result.get('success'):
                    logger.warning(
                        'Map approval notification failed for %s: %s',
                        recipient,
                        result.get('error'),
                    )
            except Exception:
                logger.exception('Unexpected error sending map approval notification to %s', recipient)
    except Exception:
        logger.exception('Failed to dispatch map approval notifications')


def _generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))


def _create_map_verification_code(email):
    normalized = _normalize_email(email)
    pending_codes = (
        map_db_session.query(MapEmailVerification)
        .filter(
            func.lower(MapEmailVerification.email) == normalized,
            MapEmailVerification.purpose == MAP_VERIFICATION_PURPOSE,
            MapEmailVerification.verified_at.is_(None),
        )
        .all()
    )
    for code_record in pending_codes:
        map_db_session.delete(code_record)

    verification = MapEmailVerification(
        email=normalized,
        code=_generate_verification_code(),
        purpose=MAP_VERIFICATION_PURPOSE,
        expires_at=_map_now_utc() + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES),
        attempts=0,
    )
    map_db_session.add(verification)
    map_db_session.commit()
    return verification


def _send_map_verification_email(email, code):
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                line-height: 1.6;
                color: #1f2937;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: #0f766e;
                color: white;
                padding: 26px;
                text-align: center;
                border-radius: 8px 8px 0 0;
            }}
            .content {{
                background: #ffffff;
                padding: 28px;
                border: 1px solid #e5e7eb;
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
            .code-box {{
                background: #ecfdf5;
                border: 2px solid #0f766e;
                border-radius: 8px;
                padding: 18px;
                text-align: center;
                margin: 20px 0;
            }}
            .code {{
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 8px;
                color: #134e4a;
                font-family: 'Courier New', monospace;
            }}
            .footer {{
                text-align: center;
                color: #6b7280;
                font-size: 12px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 style="margin: 0; font-size: 24px;">Golden Plate Map</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Submission Verification</p>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p>Use this verification code to submit to the Golden Plate Map:</p>
            <div class="code-box">
                <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 14px;">Your Verification Code</p>
                <div class="code">{code}</div>
            </div>
            <p>This code will expire in <strong>{VERIFICATION_CODE_EXPIRY_MINUTES} minutes</strong>.</p>
            <p>If you did not request this code, you can ignore this message.</p>
        </div>
        <div class="footer">
            <p>This is an automated message from Golden Plate Recorder.</p>
        </div>
    </body>
    </html>
    '''
    return send_email_via_brevo(email, 'Golden Plate Map - Email Verification Code', html_content)


def _verify_map_email_code(email, code):
    normalized_email = _normalize_email(email)
    normalized_code = (code or '').strip()

    if not normalized_email:
        return {'valid': False, 'code': 'MAP_EMAIL_REQUIRED', 'error': 'Email address is required'}

    if not normalized_code:
        return {'valid': False, 'code': 'MAP_VERIFICATION_CODE_REQUIRED', 'error': 'Verification code is required'}

    verification = (
        map_db_session.query(MapEmailVerification)
        .filter(
            func.lower(MapEmailVerification.email) == normalized_email,
            MapEmailVerification.purpose == MAP_VERIFICATION_PURPOSE,
            MapEmailVerification.verified_at.is_(None),
        )
        .order_by(MapEmailVerification.created_at.desc())
        .first()
    )
    if not verification:
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_CODE_NOT_FOUND',
            'error': 'No pending verification code found. Please request a new one.',
        }

    now = _map_now_utc()
    expires_at = verification.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_CODE_EXPIRED',
            'error': 'Verification code has expired. Please request a new one.',
        }

    if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_ATTEMPTS_EXCEEDED',
            'error': 'Too many failed attempts. Please request a new code.',
        }

    if (verification.code or '').strip() != normalized_code:
        verification.attempts += 1
        map_db_session.commit()
        remaining = MAX_VERIFICATION_ATTEMPTS - verification.attempts
        if remaining > 0:
            return {
                'valid': False,
                'code': 'MAP_VERIFICATION_CODE_MISMATCH',
                'error': f'Invalid verification code. {remaining} attempts remaining.',
            }
        return {
            'valid': False,
            'code': 'MAP_VERIFICATION_ATTEMPTS_EXCEEDED',
            'error': 'Too many failed attempts. Please request a new code.',
        }

    verification.verified_at = now
    map_db_session.commit()
    return {'valid': True, 'verification_id': verification.id}


def _is_map_email_verified(email):
    normalized_email = _normalize_email(email)
    cutoff = _map_now_utc() - timedelta(minutes=MAP_EMAIL_VERIFICATION_MAX_AGE_MINUTES)
    verification = (
        map_db_session.query(MapEmailVerification)
        .filter(
            func.lower(MapEmailVerification.email) == normalized_email,
            MapEmailVerification.purpose == MAP_VERIFICATION_PURPOSE,
            MapEmailVerification.verified_at.isnot(None),
            MapEmailVerification.verified_at >= cutoff,
        )
        .first()
    )
    return verification is not None


def _current_identity():
    user = get_current_user()
    if user:
        return {
            'user_id': user.get('id'),
            'username': user.get('username') or session.get('username'),
            'display_name': user.get('name') or user.get('username'),
            'role': user.get('role') or 'user',
            'school_id': user.get('school_id') or session.get('school_id') or DEFAULT_SCHOOL_ID,
        }

    return {
        'user_id': None,
        'username': 'guest',
        'display_name': 'Guest User',
        'role': 'guest',
        'school_id': session.get('school_id') or DEFAULT_SCHOOL_ID,
    }


def _current_school_id():
    return _current_identity()['school_id']


def _serialize_submission(submission):
    images = []
    if submission.image_data:
        images.append({
            'id': 'primary',
            'filename': submission.image_filename,
            'mime': submission.image_mime,
            'size': submission.image_size,
            'url': f'/api/map/submissions/{submission.id}/image',
        })
    extras = (
        map_db_session.query(MapSubmissionImage)
        .filter(MapSubmissionImage.submission_id == submission.id)
        .order_by(MapSubmissionImage.position.asc(), MapSubmissionImage.created_at.asc())
        .all()
    )
    for extra in extras:
        images.append({
            'id': extra.id,
            'filename': extra.image_filename,
            'mime': extra.image_mime,
            'size': extra.image_size,
            'url': f'/api/map/submissions/{submission.id}/images/{extra.id}',
        })
    return {
        'id': submission.id,
        'school_id': submission.school_id,
        'email': submission.email,
        'title': submission.title or '',
        'text': submission.text_content,
        'submission_display_name': submission.submission_display_name or '',
        'pin_id': submission.pin_id,
        'image_filename': submission.image_filename,
        'image_mime': submission.image_mime,
        'image_size': submission.image_size,
        'image_url': images[0]['url'] if images else None,
        'images': images,
        'status': submission.status,
        'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
        'submitted_by': {
            'user_id': submission.submitted_user_id,
            'username': submission.submitted_username,
            'display_name': submission.submitted_display_name,
            'role': submission.submitted_role,
        },
        'reviewed_at': submission.reviewed_at.isoformat() if submission.reviewed_at else None,
        'reviewed_by': None if not submission.reviewed_username else {
            'user_id': submission.reviewed_user_id,
            'username': submission.reviewed_username,
            'display_name': submission.reviewed_display_name,
            'role': submission.reviewed_role,
        },
        'rejection_reason': submission.rejection_reason,
        'featured': bool(submission.featured),
    }


def _get_submitter_account(email):
    normalized_email = _normalize_email(email)
    return (
        map_db_session.query(MapSubmitterAccount)
        .filter(func.lower(MapSubmitterAccount.email) == normalized_email)
        .first()
    )


def _verify_submitter_password(email, password):
    account = _get_submitter_account(email)
    if not account or account.status != 'active':
        return False, None
    if not check_password_hash(account.password_hash, password or ''):
        return False, account
    account.last_used_at = _map_now_utc()
    account.updated_at = _map_now_utc()
    return True, account


def _upsert_submitter_password(email, password, school_id, submission_id):
    account = _get_submitter_account(email)
    password_hash = generate_password_hash(password)
    now = _map_now_utc()

    if account:
        account.password_hash = password_hash
        account.status = 'active'
        account.school_id = school_id
        account.updated_at = now
        account.created_from_submission_id = account.created_from_submission_id or submission_id
        return account

    account = MapSubmitterAccount(
        school_id=school_id,
        email=_normalize_email(email),
        password_hash=password_hash,
        status='active',
        created_at=now,
        updated_at=now,
        created_from_submission_id=submission_id,
    )
    map_db_session.add(account)
    return account


@recorder_bp.route('/map/submissions', methods=['GET'])
def get_approved_map_submissions():
    _purge_orphan_image_data()
    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.status == 'approved')
        .order_by(MapSubmission.submitted_at.desc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'submissions': [_serialize_submission(submission) for submission in submissions],
    }), 200


@recorder_bp.route('/map/submissions/pending', methods=['GET'])
def get_pending_map_submissions():
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    _purge_orphan_image_data()
    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.status == 'pending')
        .order_by(MapSubmission.submitted_at.desc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'submissions': [_serialize_submission(submission) for submission in submissions],
    }), 200


@recorder_bp.route('/map/submissions/<submission_id>/image', methods=['GET'])
def get_map_submission_image(submission_id):
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission or not submission.image_data:
        return _map_error('MAP_IMAGE_NOT_FOUND', 'Image not found', 404)

    if submission.status != 'approved' and not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    return send_file(
        BytesIO(submission.image_data),
        mimetype=submission.image_mime or 'application/octet-stream',
        download_name=submission.image_filename or 'map-submission-image',
    )


@recorder_bp.route('/map/submissions/<submission_id>/images/<image_id>', methods=['GET'])
def get_map_submission_extra_image(submission_id, image_id):
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission:
        return _map_error('MAP_IMAGE_NOT_FOUND', 'Image not found', 404)
    if submission.status != 'approved' and not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)
    image = (
        map_db_session.query(MapSubmissionImage)
        .filter(
            MapSubmissionImage.id == image_id,
            MapSubmissionImage.submission_id == submission_id,
        )
        .first()
    )
    if not image or not image.image_data:
        return _map_error('MAP_IMAGE_NOT_FOUND', 'Image not found', 404)
    return send_file(
        BytesIO(image.image_data),
        mimetype=image.image_mime or 'application/octet-stream',
        download_name=image.image_filename or 'map-submission-image',
    )


@recorder_bp.route('/map/send-verification-code', methods=['POST'])
def send_map_verification_code():
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get('email'))
    recaptcha_token = (data.get('recaptcha_token') or '').strip()

    if RECAPTCHA_SECRET_KEY and not _verify_recaptcha(recaptcha_token):
        return _map_error('MAP_RECAPTCHA_FAILED', 'reCAPTCHA verification failed. Please try again.', 400)

    if not email:
        return _map_error('MAP_EMAIL_REQUIRED', 'Email address is required', 400)

    if '@' not in email or '.' not in email:
        return _map_error('MAP_EMAIL_INVALID', 'Please enter a valid email address', 400)

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    try:
        verification = _create_map_verification_code(email)
        result = _send_map_verification_email(email, verification.code)
        if not result.get('success'):
            return _map_error(
                'MAP_VERIFICATION_EMAIL_SEND_FAILED',
                'Failed to send verification email. Please try again.',
                500,
                detail=result.get('error'),
            )
    except Exception as exc:
        logger.exception('Unable to send map verification email: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_VERIFICATION_CODE_CREATE_FAILED', 'Failed to send verification code. Please try again.', 500)

    return jsonify({
        'status': 'success',
        'message': 'Verification code sent to your email address.',
        'expiry_minutes': VERIFICATION_CODE_EXPIRY_MINUTES,
    }), 200


@recorder_bp.route('/map/verify-email-code', methods=['POST'])
def verify_map_email_code_endpoint():
    data = request.get_json(silent=True) or {}
    email = _normalize_email(data.get('email'))
    code = (data.get('code') or '').strip()

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    if not code.isdigit():
        return _map_error('MAP_VERIFICATION_CODE_NON_DIGIT', 'Verification code must contain only digits', 400)

    if len(code) != 6:
        return _map_error(
            'MAP_VERIFICATION_CODE_LENGTH',
            f'Verification code must be exactly 6 digits (received {len(code)})',
            400,
        )

    try:
        result = _verify_map_email_code(email, code)
    except Exception as exc:
        logger.exception('Unable to verify map email code: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_VERIFICATION_CODE_CHECK_FAILED', 'Failed to verify code. Please try again.', 500)

    if not result.get('valid'):
        return _map_error(
            result.get('code', 'MAP_VERIFICATION_CODE_INVALID'),
            result.get('error', 'Invalid verification code'),
            400,
        )

    return jsonify({
        'status': 'success',
        'message': 'Email verified successfully.',
        'verified': True,
    }), 200


@recorder_bp.route('/map/submitter-account/status', methods=['GET'])
def get_map_submitter_account_status():
    email = _normalize_email(request.args.get('email'))
    if not email:
        return jsonify({'has_password': False}), 200

    if not _is_sac_email(email):
        return jsonify({'has_password': False}), 200

    account = _get_submitter_account(email)
    last_submission = (
        map_db_session.query(MapSubmission)
        .filter(func.lower(MapSubmission.email) == email)
        .filter(MapSubmission.submission_display_name.isnot(None))
        .filter(MapSubmission.submission_display_name != '')
        .order_by(MapSubmission.submitted_at.desc())
        .first()
    )
    last_display_name = last_submission.submission_display_name if last_submission else ''
    return jsonify({
        'status': 'success',
        'has_password': bool(account and account.status == 'active'),
        'last_display_name': last_display_name or '',
    }), 200


@recorder_bp.route('/map/submissions', methods=['POST'])
def create_map_submission():
    recaptcha_token = (request.form.get('recaptcha_token') or '').strip()
    if RECAPTCHA_SECRET_KEY and not _verify_recaptcha(recaptcha_token):
        return _map_error('MAP_RECAPTCHA_FAILED', 'reCAPTCHA verification failed. Please try again.', 400)

    email = _normalize_email(request.form.get('email'))
    text_content = (request.form.get('text') or '').strip()
    title = (request.form.get('title') or '').strip()
    submission_display_name = (request.form.get('submission_display_name') or '').strip()
    pin_id_raw = (request.form.get('pin_id') or '').strip()
    pin_id = pin_id_raw if pin_id_raw else None
    auth_method = (request.form.get('auth_method') or 'email').strip().lower()
    password = request.form.get('password') or ''
    shortcut_password = request.form.get('shortcut_password') or ''
    verification_code = (request.form.get('verification_code') or '').strip()

    if not email:
        return _map_error('MAP_EMAIL_REQUIRED', 'Email address is required', 400)

    if not _is_sac_email(email):
        return _map_error('MAP_EMAIL_DOMAIN_DENIED', 'Only @sac.on.ca email addresses can submit to the map', 403)

    if not title:
        return _map_error('MAP_SUBMISSION_TITLE_REQUIRED', 'Submission title is required', 400)

    if len(title) > 200:
        return _map_error('MAP_SUBMISSION_TITLE_TOO_LONG', 'Submission title must be 200 characters or fewer', 400)

    if not text_content:
        return _map_error('MAP_SUBMISSION_TEXT_REQUIRED', 'Submission description is required', 400)

    if len(text_content) > 5000:
        return _map_error('MAP_SUBMISSION_TEXT_TOO_LONG', 'Submission description must be 5000 characters or fewer', 400)

    if len(submission_display_name) > 80:
        return _map_error('MAP_SUBMISSION_DISPLAY_NAME_TOO_LONG', 'Display name must be 80 characters or fewer', 400)

    password_verified = False
    if auth_method == 'password':
        if not password:
            return _map_error('MAP_PASSWORD_REQUIRED', 'Password is required', 400)
        password_verified, account = _verify_submitter_password(email, password)
        if not password_verified:
            return _map_error('MAP_PASSWORD_INVALID', 'Invalid map submission password', 403)
    else:
        try:
            email_verified = _is_map_email_verified(email)
            if not email_verified and verification_code:
                result = _verify_map_email_code(email, verification_code)
                email_verified = bool(result.get('valid'))
                if not email_verified:
                    return _map_error(
                        result.get('code', 'MAP_VERIFICATION_CODE_INVALID'),
                        result.get('error', 'Invalid verification code'),
                        400,
                    )
        except Exception as exc:
            logger.exception('Unable to validate map email verification: %s', exc)
            map_db_session.rollback()
            return _map_error('MAP_EMAIL_VERIFICATION_CHECK_FAILED', 'Failed to validate email verification', 500)

        if not email_verified:
            return _map_error('MAP_EMAIL_NOT_VERIFIED', 'Please verify your SAC email address before submitting', 400)

    if shortcut_password:
        if len(shortcut_password) < 6:
            return _map_error('MAP_SHORTCUT_PASSWORD_TOO_SHORT', 'Shortcut password must be at least 6 characters long', 400)
        if auth_method == 'password' and shortcut_password == password:
            shortcut_password = ''

    image_file = request.files.get('image')
    image_filename = None
    image_mime = None
    image_data = None
    image_size = None

    if image_file and image_file.filename:
        image_mime = (image_file.mimetype or '').lower()
        original_filename = image_file.filename
        image_data = image_file.read()
        image_size = len(image_data)
        if image_size > MAX_IMAGE_BYTES:
            return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)

        if _needs_server_image_conversion(original_filename, image_mime):
            converted = _normalize_image_to_png(image_data, filename=original_filename, mime=image_mime)
            if not converted:
                return _map_error('MAP_IMAGE_DECODE_FAILED', 'Could not decode image', 400)
            image_data, image_mime, new_ext = converted
            image_size = len(image_data)
            base = os.path.splitext(secure_filename(original_filename) or 'submission-image')[0] or 'submission-image'
            image_filename = f'{base}{new_ext}'
        else:
            if not _is_browser_native_image(original_filename, image_mime):
                return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', IMAGE_TYPE_ERROR_MESSAGE, 400)
            image_filename = secure_filename(original_filename) or 'submission-image'

    # Additional images uploaded as field 'images' (one or many).
    extra_uploads = request.files.getlist('images')
    extra_processed = []  # list of dicts: filename, mime, data, size
    for extra in extra_uploads:
        if not extra or not extra.filename:
            continue
        ext_mime = (extra.mimetype or '').lower()
        ext_original = extra.filename
        ext_data = extra.read()
        ext_size = len(ext_data)
        if ext_size > MAX_IMAGE_BYTES:
            return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)
        if _needs_server_image_conversion(ext_original, ext_mime):
            converted = _normalize_image_to_png(ext_data, filename=ext_original, mime=ext_mime)
            if not converted:
                return _map_error('MAP_IMAGE_DECODE_FAILED', 'Could not decode image', 400)
            ext_data, ext_mime, new_ext = converted
            ext_size = len(ext_data)
            base = os.path.splitext(secure_filename(ext_original) or 'submission-image')[0] or 'submission-image'
            ext_filename = f'{base}{new_ext}'
        else:
            if not _is_browser_native_image(ext_original, ext_mime):
                return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', IMAGE_TYPE_ERROR_MESSAGE, 400)
            ext_filename = secure_filename(ext_original) or 'submission-image'
        extra_processed.append({
            'filename': ext_filename,
            'mime': ext_mime,
            'data': ext_data,
            'size': ext_size,
        })

    # If no primary 'image' field but extras exist, promote the first extra.
    if image_data is None and extra_processed:
        first = extra_processed.pop(0)
        image_filename = first['filename']
        image_mime = first['mime']
        image_data = first['data']
        image_size = first['size']

    identity = _current_identity()

    if pin_id:
        pin = (
            map_db_session.query(MapPin)
            .filter(MapPin.id == pin_id, MapPin.school_id == identity['school_id'])
            .first()
        )
        if not pin:
            return _map_error('MAP_PIN_NOT_FOUND', 'Selected pin does not exist', 404)

    submission = MapSubmission(
        school_id=identity['school_id'],
        email=email,
        text_content=text_content,
        title=title,
        submission_display_name=submission_display_name or None,
        pin_id=pin_id,
        image_filename=image_filename,
        image_mime=image_mime,
        image_data=image_data,
        image_size=image_size,
        status='pending',
        # 256-bit URL-safe token used by the email "speed approval" link.
        # Cleared the moment it (or any normal review action) is consumed.
        approval_token=secrets.token_urlsafe(32),
        submitted_user_id=identity['user_id'],
        submitted_username=identity['username'],
        submitted_display_name=identity['display_name'],
        submitted_role=identity['role'],
        submitted_at=_map_now_utc(),
    )

    try:
        map_db_session.add(submission)
        map_db_session.flush()
        # Persist any additional gallery images.
        for index, extra in enumerate(extra_processed):
            map_db_session.add(MapSubmissionImage(
                submission_id=submission.id,
                position=index + 1,
                image_filename=extra['filename'],
                image_mime=extra['mime'],
                image_data=extra['data'],
                image_size=extra['size'],
            ))
        # Backfill: any prior submissions from the same email take on the latest display name
        if submission_display_name:
            map_db_session.query(MapSubmission).filter(
                func.lower(MapSubmission.email) == email.lower(),
                MapSubmission.id != submission.id,
            ).update(
                {'submission_display_name': submission_display_name},
                synchronize_session=False,
            )
        password_created = False
        if shortcut_password:
            _upsert_submitter_password(email, shortcut_password, identity['school_id'], submission.id)
            password_created = True
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to create map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_CREATE_FAILED', 'Could not submit map entry', 500)

    # Notify reviewers (best-effort; never fails the request).
    try:
        notify_base_url = request.host_url
    except Exception:
        notify_base_url = None
    _notify_pending_map_submission(submission, base_url=notify_base_url)

    return jsonify({
        'status': 'success',
        'message': 'Map submission received and is pending approval.',
        'submission': _serialize_submission(submission),
        'password_created': password_created,
        'password_used': password_verified,
    }), 201


@recorder_bp.route('/map/submissions/<submission_id>/approve', methods=['POST'])
def approve_map_submission(submission_id):
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    identity = _current_identity()
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id, MapSubmission.school_id == identity['school_id'])
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)

    if submission.status != 'pending':
        return _map_error('MAP_SUBMISSION_NOT_PENDING', 'Submission is not pending', 400)

    submission.status = 'approved'
    submission.reviewed_user_id = identity['user_id']
    submission.reviewed_username = identity['username']
    submission.reviewed_display_name = identity['display_name']
    submission.reviewed_role = identity['role']
    submission.reviewed_at = _map_now_utc()
    submission.rejection_reason = None
    # NOTE: deliberately keep submission.approval_token intact so that if
    # a reviewer later clicks the email link, the quick-approve handler
    # can still validate the token and show an idempotent success page
    # (instead of a confusing "no longer valid" message). The link is
    # gated by ``status == 'pending'`` so it cannot re-trigger anything.

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to approve map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_APPROVE_FAILED', 'Could not approve submission', 500)

    return jsonify({
        'status': 'success',
        'message': 'Submission approved',
        'submission': _serialize_submission(submission),
    }), 200


@recorder_bp.route('/map/submissions/<submission_id>/quick-approve', methods=['GET', 'POST'])
def quick_approve_map_submission(submission_id):
    """Single-action, login-free approval endpoint reached from the
    reviewer notification email.

    Flow:
      * **GET** — validates the token *without consuming it* and renders a
        small HTML confirmation page with a POST form ("Approve
        submission"). Necessary because many email infrastructures
        (Outlook Safe Links, Gmail link previews, antivirus scanners,
        corporate proxies, etc.) silently issue a GET to every URL in an
        email **before the human ever clicks it**.
      * **POST** — re-validates the token and, if the submission is still
        pending, atomically flips the status to ``approved``. If the
        submission is already approved with a still-matching token, the
        success page is shown again (idempotent re-click — see below).

    Why the token is *not* nulled after use:
      Some advanced email security sandboxes (notably Microsoft Defender
      for Office 365 "Safe Links Detonation") don't just GET URLs — they
      also submit forms inside the page during their pre-delivery scan.
      If we cleared the token on POST, the sandbox would consume it and
      the human's later click would always show "no longer valid", even
      though the submission *was* correctly approved.

      Instead, single-action semantics are enforced by the **status**:
      the status flip from ``pending`` → ``approved`` only happens once.
      Re-submissions of the same valid token are treated as a confirming
      no-op and return the success page, so a real reviewer always sees
      a positive confirmation regardless of who fired the POST first.

    Security model:
      * 256-bit URL-safe random token, only ever sent to the configured
        reviewer email recipients.
      * :func:`secrets.compare_digest` for constant-time comparison.
      * State transitions are gated by ``status == 'pending'`` so the
        actual approval action runs at most once.
      * If the submission has been *rejected* via another path, the
        link refuses to override that decision.
    """
    provided_token = (request.args.get('token') or request.form.get('token') or '').strip()

    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission:
        return _quick_approve_html_response(
            'Submission not found',
            'No submission matches this approval link. It may have been deleted.',
            ok=False,
        ), 404

    stored_token = submission.approval_token or ''

    if not provided_token or not stored_token or not secrets.compare_digest(provided_token, stored_token):
        return _quick_approve_html_response(
            'Approval link no longer valid',
            'This speed-approval link is invalid. Please open the Ecological Map admin '
            'view to review the submission instead.',
            ok=False,
        ), 410

    title = (submission.title or '').strip() or '(no title)'
    success_message = (
        f'\u201c{title}\u201d has been approved and is now visible on the Ecological Map.'
    )

    # If the submission was already rejected via some other path, don't
    # let the email link silently override that decision.
    if submission.status == 'rejected':
        return _quick_approve_html_response(
            'Already rejected',
            'This submission has already been rejected by a reviewer. The speed-approval '
            'link will not override that decision.',
            ok=False,
        ), 410

    # Already-approved with a matching token: idempotent success. This
    # covers re-clicks, the human-after-sandbox-detonation case, and
    # browser back/refresh.
    if submission.status == 'approved':
        return _quick_approve_html_response(
            'Submission approved ✓',
            success_message + ' (This link has already been used; no further action was needed.)',
            ok=True,
        ), 200

    # Status must now be 'pending'.

    # GET = show confirmation page (do NOT change state — link
    # scanners/previewers send GETs ahead of the human click).
    if request.method == 'GET':
        return _quick_approve_confirm_page(submission, provided_token)

    # POST = actually approve.
    submission.status = 'approved'
    submission.reviewed_user_id = None
    submission.reviewed_username = 'email-quick-approve'
    submission.reviewed_display_name = 'Email quick-approve link'
    submission.reviewed_role = 'admin'
    submission.reviewed_at = _map_now_utc()
    submission.rejection_reason = None
    # NOTE: deliberately do NOT clear submission.approval_token here.
    # See the docstring above — keeping the token lets re-clicks (e.g.
    # after a Defender Safe Links sandbox detonated the form) still
    # render the success page for the actual reviewer.

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to quick-approve map submission: %s', exc)
        map_db_session.rollback()
        return _quick_approve_html_response(
            'Server error',
            'Could not approve the submission due to a server error. Please try again from the admin view.',
            ok=False,
        ), 500

    return _quick_approve_html_response(
        'Submission approved ✓',
        success_message,
        ok=True,
    ), 200


def _quick_approve_confirm_page(submission, token: str):
    """Render the GET-side confirmation page that POSTs back to actually
    consume the token. Pure HTML, no JS — works inside any email web view."""
    from flask import Response

    title = (submission.title or '').strip() or '(no title)'
    submitter = (
        submission.submission_display_name
        or submission.submitted_display_name
        or submission.email
        or '(unknown submitter)'
    )
    safe_title = _html_lib.escape(title)
    safe_submitter = _html_lib.escape(submitter)
    safe_id = _html_lib.escape(submission.id or '')
    safe_token = _html_lib.escape(token, quote=True)
    action = _html_lib.escape(
        f'/api/map/submissions/{submission.id}/quick-approve', quote=True,
    )

    body = f"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Confirm approval</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="no-referrer">
</head>
<body style="margin:0;padding:32px 16px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;box-shadow:0 4px 14px rgba(15,23,42,0.06);overflow:hidden;">
    <div style="background:#fffbeb;border-bottom:1px solid #fcd34d;padding:20px 28px;">
      <div style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#475569;">Ecological Map</div>
      <div style="font-size:22px;font-weight:700;color:#b45309;margin-top:4px;">Confirm speed approval</div>
    </div>
    <div style="padding:24px 28px;font-size:15px;line-height:1.55;">
      <p style="margin:0 0 16px;">You are about to approve the following submission. This will publish it to the Ecological Map immediately.</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:20px;">
        <tr><td style="padding:6px 0;color:#64748b;width:120px;">Title</td><td style="padding:6px 0;font-weight:600;">{safe_title}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Submitted by</td><td style="padding:6px 0;">{safe_submitter}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Submission ID</td><td style="padding:6px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#475569;">{safe_id}</td></tr>
      </table>
      <form method="POST" action="{action}" style="margin:0;">
        <input type="hidden" name="token" value="{safe_token}">
        <button type="submit" style="display:inline-block;background:#16a34a;color:#ffffff;border:none;border-radius:8px;padding:12px 22px;font-size:15px;font-weight:600;cursor:pointer;">
          Approve submission
        </button>
      </form>
      <p style="margin:18px 0 0;font-size:12px;color:#64748b;">
        If you didn't expect this email, you can simply close this page — no action will be taken.
      </p>
    </div>
  </div>
</body>
</html>
""".strip()
    # Cache-Control: no-store prevents intermediaries from caching the
    # confirmation page (and thus the token) anywhere.
    return Response(
        body,
        mimetype='text/html',
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, private',
            'Pragma': 'no-cache',
            'X-Robots-Tag': 'noindex, nofollow',
        },
    )


def _quick_approve_html_response(heading: str, message: str, *, ok: bool):
    """Render a tiny self-contained HTML page for the quick-approve endpoint.
    No JS, no external assets — works from any email client's web view."""
    safe_heading = _html_lib.escape(heading)
    safe_message = _html_lib.escape(message)
    accent = '#16a34a' if ok else '#b91c1c'
    bg = '#f0fdf4' if ok else '#fef2f2'
    border = '#bbf7d0' if ok else '#fecaca'
    body = f"""
<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>{safe_heading}</title>
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
</head>
<body style=\"margin:0;padding:32px 16px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;\">
  <div style=\"max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;box-shadow:0 4px 14px rgba(15,23,42,0.06);overflow:hidden;\">
    <div style=\"background:{bg};border-bottom:1px solid {border};padding:20px 28px;\">
      <div style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#475569;\">Ecological Map</div>
      <div style=\"font-size:22px;font-weight:700;color:{accent};margin-top:4px;\">{safe_heading}</div>
    </div>
    <div style=\"padding:24px 28px;font-size:15px;line-height:1.55;\">
      {safe_message}
    </div>
  </div>
</body>
</html>
""".strip()
    from flask import Response
    return Response(body, mimetype='text/html')


@recorder_bp.route('/map/submissions/<submission_id>/reject', methods=['POST'])
def reject_map_submission(submission_id):
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()
    identity = _current_identity()
    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id, MapSubmission.school_id == identity['school_id'])
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)

    if submission.status != 'pending':
        return _map_error('MAP_SUBMISSION_NOT_PENDING', 'Submission is not pending', 400)

    # If a comment was supplied, send the notification email FIRST. If the
    # email fails, do not reject the submission — the submitter would otherwise
    # never learn the reason. Plain rejections (no comment) skip the email.
    email_status = None
    if reason:
        if not submission.email:
            return _map_error(
                'MAP_REJECT_NO_EMAIL',
                'Cannot send rejection comment: submitter has no email on file',
                400,
            )
        try:
            email_status = _send_rejection_email(
                to_email=submission.email,
                submission=submission,
                reason=reason,
                reviewer_display_name=identity.get('display_name') or identity.get('username') or 'Admin',
            )
        except Exception as exc:
            logger.exception('Unable to send map rejection email: %s', exc)
            email_status = {'success': False, 'error': str(exc)}
        if not email_status or not email_status.get('success'):
            detail = (email_status or {}).get('error') or 'Unknown email error'
            return _map_error(
                'MAP_REJECT_EMAIL_FAILED',
                'Submission was not rejected: notification email failed',
                502,
                detail=detail,
            )

    submission.status = 'rejected'
    submission.reviewed_user_id = identity['user_id']
    submission.reviewed_username = identity['username']
    submission.reviewed_display_name = identity['display_name']
    submission.reviewed_role = identity['role']
    submission.reviewed_at = _map_now_utc()
    submission.rejection_reason = reason or None
    # NOTE: deliberately keep submission.approval_token intact. The
    # quick-approve handler now uses ``status`` (not token nullity) for
    # single-action gating, so a reviewer who later clicks the email
    # link will see a clean "Already rejected" page instead of a
    # confusing "no longer valid" error.

    # Purge stored image bytes to reclaim disk space. We keep filename/mime
    # for the audit trail but the binary blobs are no longer needed once a
    # submission is rejected (rejected submissions are not displayed).
    submission.image_data = None
    submission.image_size = 0
    map_db_session.query(MapSubmissionImage).filter(
        MapSubmissionImage.submission_id == submission.id
    ).delete(synchronize_session=False)

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to reject map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_REJECT_FAILED', 'Could not reject submission', 500)

    response_payload = {
        'status': 'success',
        'message': 'Submission rejected',
        'submission': _serialize_submission(submission),
    }
    if email_status is not None:
        response_payload['notification_email'] = email_status
    return jsonify(response_payload), 200


def _send_deletion_email(*, to_email: str, submission, reason: str, reviewer_display_name: str) -> dict:
    """Send a formatted deletion email to the submitter via Brevo.

    Includes the full submission text and every attached image so the user
    has a complete record of what was removed.
    """
    title = (submission.title or '').strip() or 'your submission'
    safe_title = _html_lib.escape(title)
    safe_reason = _html_lib.escape(reason).replace('\n', '<br/>')
    safe_reviewer = _html_lib.escape(reviewer_display_name)
    submitted_at = ''
    if submission.submitted_at:
        try:
            submitted_at = submission.submitted_at.strftime('%B %d, %Y at %I:%M %p UTC')
        except Exception:
            submitted_at = str(submission.submitted_at)
    safe_submitted_at = _html_lib.escape(submitted_at)
    full_text = (submission.text_content or '').strip()
    safe_full_text = _html_lib.escape(full_text).replace('\n', '<br/>')

    attachments, image_descriptions = _collect_submission_image_attachments(submission)
    images_html = _render_image_descriptions_html(image_descriptions)

    body_html = (
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:18px 0 6px 0;">Your submission</div>'
        f'<div style="font-size:14px;line-height:1.55;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;padding:14px 16px;color:#334155;white-space:pre-wrap;">{safe_full_text or "<em>(no description)</em>"}</div>'
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:18px 0 6px 0;">Images (attached to this email)</div>'
        f'<div style="font-size:14px;line-height:1.55;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;padding:14px 16px;color:#334155;">{images_html}</div>'
    )

    subject = 'Your Ecological Map submission was deleted'
    html_content = f"""
<!doctype html>
<html>
  <body style=\"margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;\">
    <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9;padding:24px 0;\">
      <tr><td align=\"center\">
        <table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 14px rgba(15,23,42,0.06);\">
          <tr>
            <td style=\"background:linear-gradient(135deg,#7f1d1d,#dc2626);padding:24px 28px;color:#ffffff;\">
              <div style=\"font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.85;\">Ecological Map</div>
              <div style=\"font-size:22px;font-weight:700;margin-top:6px;\">Submission was deleted</div>
            </td>
          </tr>
          <tr>
            <td style=\"padding:24px 28px;\">
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">Hi,</p>
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">
                Your submission <strong>{safe_title}</strong> on the Ecological Map has been removed by an administrator.
              </p>
              <div style=\"background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:14px 16px;margin:16px 0;\">
                <div style=\"font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#991b1b;margin-bottom:6px;\">Reason</div>
                <div style=\"font-size:14px;line-height:1.55;color:#7f1d1d;\">{safe_reason}</div>
              </div>
              <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin:16px 0;\">
                <tr>
                  <td style=\"padding:14px 16px;font-size:13px;line-height:1.55;color:#334155;\">
                    <div><strong>Title:</strong> {safe_title}</div>
                    <div><strong>Originally submitted:</strong> {safe_submitted_at or '—'}</div>
                    <div><strong>Deleted by:</strong> {safe_reviewer}</div>
                  </td>
                </tr>
              </table>
              {body_html}
              <p style=\"margin:18px 0 6px 0;font-size:14px;line-height:1.55;\">If you believe this was a mistake, please contact a site administrator.</p>
              <p style=\"margin:0;font-size:14px;line-height:1.55;color:#475569;\">— The Ecological Map team</p>
            </td>
          </tr>
          <tr>
            <td style=\"padding:14px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;\">
              You're receiving this email because you submitted an entry to the Ecological Map.
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
"""
    return send_email_via_brevo(to_email, subject, html_content, attachments=attachments or None)


def _send_rejection_email(*, to_email: str, submission, reason: str, reviewer_display_name: str) -> dict:
    """Send a formatted rejection email to the submitter via Brevo.

    Includes the full submission text and every attached image so the user
    has a complete record of what was reviewed.
    """
    title = (submission.title or '').strip() or 'your submission'
    safe_title = _html_lib.escape(title)
    safe_reason = _html_lib.escape(reason).replace('\n', '<br/>')
    safe_reviewer = _html_lib.escape(reviewer_display_name)
    submitted_at = ''
    if submission.submitted_at:
        try:
            submitted_at = submission.submitted_at.strftime('%B %d, %Y at %I:%M %p UTC')
        except Exception:
            submitted_at = str(submission.submitted_at)
    safe_submitted_at = _html_lib.escape(submitted_at)
    full_text = (submission.text_content or '').strip()
    safe_full_text = _html_lib.escape(full_text).replace('\n', '<br/>')

    attachments, image_descriptions = _collect_submission_image_attachments(submission)
    images_html = _render_image_descriptions_html(image_descriptions)

    body_html = (
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:18px 0 6px 0;">Your submission</div>'
        f'<div style="font-size:14px;line-height:1.55;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;padding:14px 16px;color:#334155;white-space:pre-wrap;">{safe_full_text or "<em>(no description)</em>"}</div>'
        '<div style="font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:18px 0 6px 0;">Images (attached to this email)</div>'
        f'<div style="font-size:14px;line-height:1.55;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;padding:14px 16px;color:#334155;">{images_html}</div>'
    )

    subject = f'Your Ecological Map submission was not approved'
    html_content = f"""
<!doctype html>
<html>
  <body style=\"margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;\">
    <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9;padding:24px 0;\">
      <tr><td align=\"center\">
        <table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 14px rgba(15,23,42,0.06);\">
          <tr>
            <td style=\"background:linear-gradient(135deg,#0f766e,#0ea5e9);padding:24px 28px;color:#ffffff;\">
              <div style=\"font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.85;\">Ecological Map</div>
              <div style=\"font-size:22px;font-weight:700;margin-top:6px;\">Submission was not approved</div>
            </td>
          </tr>
          <tr>
            <td style=\"padding:24px 28px;\">
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">Hi,</p>
              <p style=\"margin:0 0 14px 0;font-size:15px;line-height:1.55;\">
                Thanks for contributing to the Ecological Map. After review, <strong>{safe_title}</strong> was not approved.
              </p>
              <div style=\"background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:14px 16px;margin:16px 0;\">
                <div style=\"font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#991b1b;margin-bottom:6px;\">Reviewer comment</div>
                <div style=\"font-size:14px;line-height:1.55;color:#7f1d1d;\">{safe_reason}</div>
              </div>
              <table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin:16px 0;\">
                <tr>
                  <td style=\"padding:14px 16px;font-size:13px;line-height:1.55;color:#334155;\">
                    <div><strong>Title:</strong> {safe_title}</div>
                    <div><strong>Submitted:</strong> {safe_submitted_at or '—'}</div>
                    <div><strong>Reviewed by:</strong> {safe_reviewer}</div>
                  </td>
                </tr>
              </table>
              {body_html}
              <p style=\"margin:18px 0 6px 0;font-size:14px;line-height:1.55;\">You're welcome to revise it and submit again.</p>
              <p style=\"margin:0;font-size:14px;line-height:1.55;color:#475569;\">— The Ecological Map team</p>
            </td>
          </tr>
          <tr>
            <td style=\"padding:14px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;\">
              You're receiving this email because you submitted an entry to the Ecological Map.
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
"""
    return send_email_via_brevo(to_email, subject, html_content, attachments=attachments or None)


def _serialize_pin(pin):
    return {
        'id': pin.id,
        'name': pin.name,
        'x': pin.x,
        'y': pin.y,
        'created_at': pin.created_at.isoformat() if pin.created_at else None,
        'created_by': {
            'user_id': pin.created_by_user_id,
            'username': pin.created_by_username,
            'display_name': pin.created_by_display_name,
            'email': pin.created_by_email,
        },
    }


@recorder_bp.route('/map/pins', methods=['GET'])
def list_map_pins():
    # Auto-cleanup: remove pins that have no non-rejected submissions attached.
    # Skip pins created in the last 10 minutes so a freshly created pin
    # awaiting its first submission isn't yanked out from under the submitter.
    grace_cutoff = _map_now_utc() - timedelta(minutes=10)
    try:
        empty_pin_ids = [
            row[0]
            for row in (
                map_db_session.query(MapPin.id)
                .outerjoin(
                    MapSubmission,
                    (MapSubmission.pin_id == MapPin.id)
                    & (MapSubmission.status != 'rejected'),
                )
                .filter(MapPin.created_at < grace_cutoff)
                .group_by(MapPin.id)
                .having(func.count(MapSubmission.id) == 0)
                .all()
            )
        ]
        if empty_pin_ids:
            # Detach any rejected submissions still pointing at these pins.
            map_db_session.query(MapSubmission).filter(
                MapSubmission.pin_id.in_(empty_pin_ids)
            ).update({'pin_id': None}, synchronize_session=False)
            map_db_session.query(MapPin).filter(MapPin.id.in_(empty_pin_ids)).delete(
                synchronize_session=False
            )
            map_db_session.commit()
    except Exception as exc:
        logger.exception('Empty-pin cleanup failed: %s', exc)
        map_db_session.rollback()

    pins = (
        map_db_session.query(MapPin)
        .order_by(MapPin.created_at.asc())
        .all()
    )
    return jsonify({
        'status': 'success',
        'pins': [_serialize_pin(pin) for pin in pins],
    }), 200


@recorder_bp.route('/map/pins', methods=['POST'])
def create_map_pin():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    x = data.get('x')
    y = data.get('y')
    email = _normalize_email(data.get('email'))

    if not name:
        return _map_error('MAP_PIN_NAME_REQUIRED', 'Pin name is required', 400)
    if len(name) > 80:
        return _map_error('MAP_PIN_NAME_TOO_LONG', 'Pin name must be 80 characters or fewer', 400)

    try:
        x = float(x)
        y = float(y)
    except (TypeError, ValueError):
        return _map_error('MAP_PIN_COORDS_INVALID', 'Pin coordinates must be numeric', 400)

    if not (0 <= x <= 100 and 0 <= y <= 100):
        return _map_error('MAP_PIN_COORDS_OUT_OF_RANGE', 'Pin coordinates must be within map bounds (0-100)', 400)

    user = get_current_user()
    if user:
        identity = _current_identity()
        creator_email = email or identity['username']
        creator_username = identity['username']
        creator_display = identity['display_name']
        creator_user_id = identity['user_id']
    else:
        # Guest / map submitter — must provide a verified SAC email
        if not email or not _is_sac_email(email):
            return _map_error('MAP_PIN_EMAIL_REQUIRED', 'A verified @sac.on.ca email is required to create a pin', 403)
        if not _is_map_email_verified(email):
            return _map_error('MAP_PIN_EMAIL_NOT_VERIFIED', 'Verify your SAC email before creating a pin', 403)
        creator_email = email
        creator_username = email
        creator_display = email
        creator_user_id = None

    school_id = _current_school_id()
    pin = MapPin(
        school_id=school_id,
        name=name,
        x=x,
        y=y,
        created_by_user_id=creator_user_id,
        created_by_username=creator_username,
        created_by_display_name=creator_display,
        created_by_email=creator_email,
    )
    try:
        map_db_session.add(pin)
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to create map pin: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_PIN_CREATE_FAILED', 'Could not create pin', 500)

    return jsonify({'status': 'success', 'pin': _serialize_pin(pin)}), 201


@recorder_bp.route('/map/pins/<pin_id>', methods=['DELETE'])
def delete_map_pin(pin_id):
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    pin = (
        map_db_session.query(MapPin)
        .filter(MapPin.id == pin_id)
        .first()
    )
    if not pin:
        return _map_error('MAP_PIN_NOT_FOUND', 'Pin not found', 404)

    # Detach submissions from this pin (move to "Others")
    map_db_session.query(MapSubmission).filter(
        MapSubmission.pin_id == pin_id,
    ).update({'pin_id': None}, synchronize_session=False)

    try:
        map_db_session.delete(pin)
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to delete map pin: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_PIN_DELETE_FAILED', 'Could not delete pin', 500)

    return jsonify({'status': 'success', 'message': 'Pin deleted'}), 200


@recorder_bp.route('/map/submissions/<submission_id>', methods=['DELETE'])
def delete_map_submission(submission_id):
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()

    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)

    identity = _current_identity()

    # If a comment was supplied, send the notification email FIRST. If the
    # email fails, do not delete the submission.
    email_status = None
    if reason:
        if not submission.email:
            return _map_error(
                'MAP_DELETE_NO_EMAIL',
                'Cannot send deletion comment: submitter has no email on file',
                400,
            )
        try:
            email_status = _send_deletion_email(
                to_email=submission.email,
                submission=submission,
                reason=reason,
                reviewer_display_name=identity.get('display_name') or identity.get('username') or 'Admin',
            )
        except Exception as exc:
            logger.exception('Unable to send map deletion email: %s', exc)
            email_status = {'success': False, 'error': str(exc)}
        if not email_status or not email_status.get('success'):
            detail = (email_status or {}).get('error') or 'Unknown email error'
            return _map_error(
                'MAP_DELETE_EMAIL_FAILED',
                'Submission was not deleted: notification email failed',
                502,
                detail=detail,
            )

    pin_id = submission.pin_id

    try:
        # Explicitly remove gallery rows (SQLite ignores ON DELETE CASCADE
        # unless PRAGMA foreign_keys=ON is set per-connection).
        map_db_session.query(MapSubmissionImage).filter(
            MapSubmissionImage.submission_id == submission.id
        ).delete(synchronize_session=False)
        map_db_session.delete(submission)
        map_db_session.flush()
        # If the pin no longer has any non-rejected submissions, remove it
        # (and any orphan rejected submissions still pointing at it).
        if pin_id:
            remaining = (
                map_db_session.query(MapSubmission)
                .filter(
                    MapSubmission.pin_id == pin_id,
                    MapSubmission.status != 'rejected',
                )
                .count()
            )
            if remaining == 0:
                # Detach any leftover rejected submissions so the FK doesn't
                # block the pin delete.
                map_db_session.query(MapSubmission).filter(
                    MapSubmission.pin_id == pin_id
                ).update({'pin_id': None}, synchronize_session=False)
                map_db_session.query(MapPin).filter(MapPin.id == pin_id).delete(
                    synchronize_session=False
                )
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to delete map submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_SUBMISSION_DELETE_FAILED', 'Could not delete submission', 500)

    response_payload = {'status': 'success', 'message': 'Submission deleted'}
    if email_status is not None:
        response_payload['notification_email'] = email_status
    return jsonify(response_payload), 200


@recorder_bp.route('/map/leaderboard', methods=['GET'])
def map_leaderboard():
    _purge_orphan_image_data()
    rows = (
        map_db_session.query(
            MapSubmission.email,
            MapSubmission.submission_display_name,
            func.count(MapSubmission.id).label('count'),
        )
        .filter(MapSubmission.status == 'approved')
        .group_by(MapSubmission.email, MapSubmission.submission_display_name)
        .all()
    )
    # Aggregate by email; pick most-recent display name per email
    by_email = {}
    for email, display_name, count in rows:
        bucket = by_email.setdefault(email, {'email': email, 'display_name': '', 'count': 0})
        bucket['count'] += int(count or 0)
        if display_name and not bucket['display_name']:
            bucket['display_name'] = display_name
    leaders = sorted(by_email.values(), key=lambda item: item['count'], reverse=True)
    return jsonify({'status': 'success', 'leaderboard': leaders}), 200


@recorder_bp.route('/map/featured', methods=['GET'])
def get_featured_submission():
    _purge_orphan_image_data()
    submissions = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.status == 'approved', MapSubmission.featured == 1)
        .order_by(MapSubmission.submitted_at.desc())
        .all()
    )
    payload = [_serialize_submission(s) for s in submissions]
    return jsonify({
        'status': 'success',
        'submissions': payload,
        # Keep the legacy single-submission field for backward compatibility
        # with any older client cached in the browser.
        'submission': payload[0] if payload else None,
    }), 200


@recorder_bp.route('/map/submissions/<submission_id>/feature', methods=['POST'])
def set_featured_submission(submission_id):
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    data = request.get_json(silent=True) or {}
    featured_flag = bool(data.get('featured', True))

    submission = (
        map_db_session.query(MapSubmission)
        .filter(MapSubmission.id == submission_id)
        .first()
    )
    if not submission:
        return _map_error('MAP_SUBMISSION_NOT_FOUND', 'Submission not found', 404)
    if submission.status != 'approved':
        return _map_error('MAP_FEATURE_NOT_APPROVED', 'Only approved submissions can be featured', 400)

    try:
        submission.featured = 1 if featured_flag else 0
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to update featured submission: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_FEATURE_UPDATE_FAILED', 'Could not update featured submission', 500)

    return jsonify({'status': 'success', 'submission': _serialize_submission(submission)}), 200


@recorder_bp.route('/map/convert-heic', methods=['POST'])
@recorder_bp.route('/map/convert-image', methods=['POST'])
def convert_heic_image():
    """Convert any non-browser-renderable image (HEIC/HEIF, TIFF, ...) to PNG.

    Lets browsers preview/edit formats they can't natively decode by
    round-tripping through the server.
    """
    image_file = request.files.get('image')
    if not image_file or not image_file.filename:
        return _map_error('MAP_CONVERT_FILE_REQUIRED', 'Image file is required', 400)

    if not _needs_server_image_conversion(image_file.filename, image_file.mimetype):
        return _map_error(
            'MAP_CONVERT_NOT_NEEDED',
            'File is already in a browser-renderable format',
            400,
        )

    raw = image_file.read()
    if len(raw) > MAX_IMAGE_BYTES:
        return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)

    converted = _normalize_image_to_png(raw, filename=image_file.filename, mime=image_file.mimetype)
    if not converted:
        return _map_error('MAP_IMAGE_DECODE_FAILED', 'Could not decode image', 400)
    png_bytes, mime, _ext = converted
    return send_file(BytesIO(png_bytes), mimetype=mime, max_age=0)


@recorder_bp.route('/map/settings/approval-recipients', methods=['GET'])
def get_map_approval_recipients_setting():
    """Return the current approval-notification recipient list and the
    fallback chain that produced it. Restricted to admins/superadmins so
    we don't leak email addresses publicly."""
    if not require_admin():
        return _map_error('MAP_ADMIN_REQUIRED', 'Admin access required', 403)

    setting = (
        map_db_session.query(MapSetting)
        .filter(MapSetting.key == MAP_SETTING_APPROVAL_RECIPIENTS)
        .first()
    )
    db_value = (setting.value or '').strip() if setting else ''
    db_emails = _parse_email_list(db_value) if db_value else []
    env_value = (os.environ.get('MAP_APPROVAL_NOTIFY_EMAILS', '') or '').strip()
    env_emails = _parse_email_list(env_value) if env_value else []

    if db_emails:
        source = 'database'
    elif env_emails:
        source = 'env'
    else:
        source = 'default'

    return jsonify({
        'status': 'success',
        'recipients': _get_map_approval_notify_recipients(),
        'source': source,
        'database_recipients': db_emails,
        'env_recipients': env_emails,
        'default_recipients': list(DEFAULT_MAP_APPROVAL_NOTIFY_EMAILS),
        'updated_at': setting.updated_at.isoformat() if setting and setting.updated_at else None,
        'updated_by': (
            setting.updated_by_username
            if setting and setting.updated_by_username
            else None
        ),
    }), 200


@recorder_bp.route('/map/settings/approval-recipients', methods=['PUT'])
def update_map_approval_recipients_setting():
    """Persist a new approval-notification recipient list. Superadmin only."""
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    data = request.get_json(silent=True) or {}
    raw_recipients = data.get('recipients')

    if isinstance(raw_recipients, list):
        candidates = [str(item).strip() for item in raw_recipients if str(item).strip()]
    elif isinstance(raw_recipients, str):
        candidates = _parse_email_list(raw_recipients)
    else:
        return _map_error(
            'MAP_RECIPIENTS_INVALID',
            'recipients must be a list of strings or a comma/newline-separated string',
            400,
        )

    cleaned = []
    seen = set()
    invalid = []
    for candidate in candidates:
        if not _EMAIL_VALIDATE_RE.match(candidate):
            invalid.append(candidate)
            continue
        normalized = candidate.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(candidate)

    if invalid:
        return _map_error(
            'MAP_RECIPIENTS_INVALID',
            f'Invalid email address(es): {", ".join(invalid)}',
            400,
        )

    if len(cleaned) > 50:
        return _map_error(
            'MAP_RECIPIENTS_TOO_MANY',
            'A maximum of 50 recipients is allowed',
            400,
        )

    identity = _current_identity()
    setting = (
        map_db_session.query(MapSetting)
        .filter(MapSetting.key == MAP_SETTING_APPROVAL_RECIPIENTS)
        .first()
    )
    serialized = ','.join(cleaned)
    now = _map_now_utc()

    if setting is None:
        setting = MapSetting(
            key=MAP_SETTING_APPROVAL_RECIPIENTS,
            value=serialized,
            updated_at=now,
            updated_by_user_id=identity.get('user_id'),
            updated_by_username=identity.get('username'),
        )
        map_db_session.add(setting)
    else:
        setting.value = serialized
        setting.updated_at = now
        setting.updated_by_user_id = identity.get('user_id')
        setting.updated_by_username = identity.get('username')

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to update approval recipients setting: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_RECIPIENTS_SAVE_FAILED', 'Could not save recipients', 500)

    return jsonify({
        'status': 'success',
        'recipients': _get_map_approval_notify_recipients(),
        'source': 'database' if cleaned else (
            'env' if (os.environ.get('MAP_APPROVAL_NOTIFY_EMAILS') or '').strip() else 'default'
        ),
        'database_recipients': cleaned,
        'updated_at': setting.updated_at.isoformat() if setting.updated_at else None,
        'updated_by': setting.updated_by_username,
    }), 200


@recorder_bp.route('/map/background', methods=['GET'])
def get_map_background():
    background = (
        map_db_session.query(MapBackground)
        .order_by(MapBackground.uploaded_at.desc())
        .first()
    )
    if not background:
        return _map_error('MAP_BACKGROUND_NOT_FOUND', 'No background uploaded', 404)

    return send_file(
        BytesIO(background.image_data),
        mimetype=background.image_mime or 'application/octet-stream',
        download_name=background.image_filename or 'map-background',
    )


@recorder_bp.route('/map/background/info', methods=['GET'])
def get_map_background_info():
    background = (
        map_db_session.query(MapBackground)
        .order_by(MapBackground.uploaded_at.desc())
        .first()
    )
    if not background:
        return jsonify({'status': 'success', 'has_background': False}), 200

    return jsonify({
        'status': 'success',
        'has_background': True,
        'image_url': '/api/map/background',
        'image_mime': background.image_mime,
        'image_size': background.image_size,
        'uploaded_at': background.uploaded_at.isoformat() if background.uploaded_at else None,
    }), 200


@recorder_bp.route('/map/background', methods=['POST'])
def upload_map_background():
    if not require_superadmin():
        return _map_error('MAP_SUPERADMIN_REQUIRED', 'Super admin access required', 403)

    image_file = request.files.get('image')
    if not image_file or not image_file.filename:
        return _map_error('MAP_BACKGROUND_IMAGE_REQUIRED', 'Image file is required', 400)

    image_mime = (image_file.mimetype or '').lower()
    original_filename = image_file.filename
    image_data = image_file.read()
    image_size = len(image_data)
    if image_size > MAX_IMAGE_BYTES:
        return _map_error('MAP_IMAGE_TOO_LARGE', 'Image must be 50 MB or smaller', 413)

    if _is_heic_upload(original_filename, image_mime):
        converted = _normalize_heic_to_jpeg(image_data)
        if not converted:
            return _map_error('MAP_IMAGE_HEIC_DECODE_FAILED', 'Could not decode HEIC image', 400)
        image_data, image_mime, new_ext = converted
        image_size = len(image_data)
        base = os.path.splitext(secure_filename(original_filename) or 'map-background')[0] or 'map-background'
        stored_filename = f'{base}{new_ext}'
    else:
        if image_mime not in ALLOWED_IMAGE_MIMES:
            return _map_error('MAP_IMAGE_TYPE_UNSUPPORTED', 'Image must be a JPG, PNG, WebP, GIF, or HEIC file', 400)
        stored_filename = secure_filename(original_filename) or 'map-background'

    identity = _current_identity()
    school_id = identity['school_id']
    background = (
        map_db_session.query(MapBackground)
        .filter(MapBackground.school_id == school_id)
        .first()
    )
    if background:
        background.image_data = image_data
        background.image_mime = image_mime
        background.image_filename = stored_filename
        background.image_size = image_size
        background.uploaded_at = _map_now_utc()
        background.uploaded_by_user_id = identity['user_id']
        background.uploaded_by_username = identity['username']
    else:
        background = MapBackground(
            school_id=school_id,
            image_data=image_data,
            image_mime=image_mime,
            image_filename=stored_filename,
            image_size=image_size,
            uploaded_at=_map_now_utc(),
            uploaded_by_user_id=identity['user_id'],
            uploaded_by_username=identity['username'],
        )
        map_db_session.add(background)

    try:
        map_db_session.commit()
    except Exception as exc:
        logger.exception('Unable to save map background: %s', exc)
        map_db_session.rollback()
        return _map_error('MAP_BACKGROUND_SAVE_FAILED', 'Could not save background image', 500)

    return jsonify({
        'status': 'success',
        'message': 'Background image saved',
        'image_url': '/api/map/background',
        'image_size': image_size,
    }), 200


__all__ = []