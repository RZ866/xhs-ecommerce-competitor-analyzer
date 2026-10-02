import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from .storage import SnapshotStore

ENDPOINTS = {
    'account': '/api/v1/xiaohongshu/app_v2/get_user_info',
    'notes': '/api/v1/xiaohongshu/app_v2/get_user_posted_notes',
    'comments': '/api/v1/xiaohongshu/app_v2/get_note_comments',
    'products': '/api/v1/xiaohongshu/web_v2/fetch_product_list',
    'detail': '/api/v1/xiaohongshu/app_v2/get_image_note_detail',
}

class ProviderError(Exception):
    """Safe message only; never includes request headers or server text."""

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def request_json(url, headers, timeout, body=None):
    request = urllib.request.Request(url, data=body, headers=headers)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(16 * 1024 * 1024 + 1)
            if len(payload) > 16 * 1024 * 1024:
                raise ProviderError('response too large')
            return response.status, json.loads(payload)
    except urllib.error.HTTPError as exc:
        return exc.code, {'transport_error': 'HTTP failure'}
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError('network timeout or connection failure') from None
    except (ValueError, UnicodeError):
        raise ProviderError('invalid JSON response') from None

class TikHubClient:
    def __init__(self, store, timeout=30, retries=2, interval=1.0, request=request_json,
                 sleep=time.sleep, clock=time.monotonic, max_calls=200):
        self.store = store
        self.timeout, self.retries, self.interval = timeout, retries, interval
        self.request, self.sleep, self.clock = request, sleep, clock
        self.last_call, self.calls, self.max_calls = None, 0, max_calls

    def get(self, kind, params):
        endpoint = ENDPOINTS[kind]
        cached = self.store.get(endpoint, params)
        if cached:
            return cached
        key = os.environ.get('TIKHUB_API_KEY')
        if not key:
            raise ProviderError('TIKHUB_API_KEY is not configured')
        for attempt in range(self.retries + 1):
            if self.calls >= self.max_calls:
                raise ProviderError('API call budget exhausted')
            if self.last_call is not None:
                self.sleep(max(0, self.interval - (self.clock() - self.last_call)))
            self.last_call = self.clock()
            self.calls += 1
            try:
                status, payload = self.request('https://api.tikhub.io' + endpoint + '?' + urllib.parse.urlencode(params),
                                               {'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}, self.timeout)
            except ProviderError:
                self.store.save(endpoint, params, {'transport_error': 'network or decoding failure'}, 0, False)
                if attempt < self.retries:
                    self.sleep(min(2 ** attempt, 8))
                    continue
                raise
            # Preserve failures too, never cache them. Provider business errors are not retried.
            code = payload.get('code') if isinstance(payload, dict) else None
            ok = status == 200 and code in (None, 0, 200, '0', '200')
            snapshot = self.store.save(endpoint, params, payload, status, cache=ok)
            if ok:
                return payload, snapshot
            if (status == 429 or status >= 500) and attempt < self.retries:
                self.sleep(min(2 ** attempt, 8))
                continue
            raise ProviderError(f'{kind}: HTTP {status}; unsuccessful response saved')
        raise ProviderError('retry limit reached')
