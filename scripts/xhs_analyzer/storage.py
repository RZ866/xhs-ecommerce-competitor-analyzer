import hashlib
import json
import os
import re
import time
from pathlib import Path

def redact(value):
    secrets = [os.environ.get(k) for k in ('TIKHUB_API_KEY', 'AI_API_KEY') if os.environ.get(k)]
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'cookie|authorization|api.?key|access.?token|password|secret', k, re.I) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'(?i)([?&](?:xsec_token|token|api_key|key)=)[^&\s]+', r'\1[REDACTED]', value)
    return value

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

class SnapshotStore:
    def __init__(self, root, ttl=86400, namespace='tikhub'):
        self.root = Path(root)
        self.ttl = ttl
        self.namespace = namespace

    def key(self, endpoint, params):
        return digest([self.namespace, endpoint, params])

    def get(self, endpoint, params):
        cache = self.root / 'cache' / (self.key(endpoint, params) + '.json')
        if cache.exists():
            try:
                value = read(cache)
                snapshot = self.root / value['snapshot']
                if time.time() - value['saved_at'] < self.ttl and snapshot.exists():
                    return read(snapshot)['response'], value['snapshot']
            except (ValueError, KeyError, OSError):
                pass
        return None

    def save(self, endpoint, params, response, status=200, cache=True):
        key = self.key(endpoint, params)
        name = f'raw/{time.time_ns()}-{key[:12]}.json'
        dump(self.root / name, {'endpoint': endpoint, 'parameters': params, 'status': status,
                               'captured_at': time.time(), 'provider': self.namespace,
                               'response': response, 'redaction': 'credentials only'})
        if cache:
            dump(self.root / 'cache' / (key + '.json'), {'snapshot': name, 'saved_at': time.time()})
        return name

    def invalidate(self, endpoint, params):
        cache = self.root / 'cache' / (self.key(endpoint, params) + '.json')
        cache.unlink(missing_ok=True)

def field_inventory(value, prefix='$'):
    output = [{'path': prefix, 'type': type(value).__name__}]
    if isinstance(value, dict):
        for key, child in value.items():
            output.extend(field_inventory(child, prefix + '.' + key))
    elif isinstance(value, list):
        seen = set()
        for child in value[:20]:
            for item in field_inventory(child, prefix + '[]'):
                tag = (item['path'], item['type'])
                if tag not in seen:
                    output.append(item)
                    seen.add(tag)
    return output
