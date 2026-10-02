import base64
import hashlib
import io
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from .transport import NoRedirect

def fetch_cover(url, output, note_id):
    """Only public XHS CDN hosts, no redirects, credentials, cookies or executable image formats."""
    parsed = urlsplit(url or '')
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or not any(host == d or host.endswith('.' + d) for d in ('xhscdn.com', 'xhsimg.com')):
        raise ValueError('Image host outside public XHS CDN allowlist')
    try:
        from PIL import Image
    except ImportError:
        raise ValueError('Install Pillow for cover verification') from None
    request = urllib.request.Request(url, headers={'Accept': 'image/*'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
        blob = response.read(5 * 1024 * 1024 + 1)
    if len(blob) > 5 * 1024 * 1024:
        raise ValueError('Image too large')
    Image.MAX_IMAGE_PIXELS = 20_000_000
    with Image.open(io.BytesIO(blob)) as image:
        kind, size = image.format, image.size
        if kind not in {'JPEG', 'PNG', 'WEBP'} or size[0] * size[1] > 20_000_000:
            raise ValueError('Unsupported image')
        image.verify()
    mime = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}[kind]
    name = 'images/' + hashlib.sha256(blob).hexdigest() + '.' + kind.lower()
    target = Path(output) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    return {'note_id': note_id, 'evidence_id': 'image:' + note_id, 'path': name, 'width': size[0], 'height': size[1],
            'data_url': 'data:' + mime + ';base64,' + base64.b64encode(blob).decode()}
