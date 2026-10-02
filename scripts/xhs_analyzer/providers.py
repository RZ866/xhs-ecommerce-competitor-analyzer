from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit
import re
from .models import Account, Note, Product, Comment, Evidence, make_model
from .storage import read, dump, digest, field_inventory
from .transport import ProviderError, ENDPOINTS

def identity(url):
    p = urlsplit(url)
    match = re.fullmatch(r'/user/profile/([a-fA-F0-9]{24})/?', p.path)
    if p.scheme != 'https' or p.hostname not in {'www.xiaohongshu.com', 'xiaohongshu.com'} or p.username or p.password or p.port not in (None, 443) or not match:
        raise ValueError('请提供 https://www.xiaohongshu.com/user/profile/ 后跟24位用户ID的公开主页 URL；不自动展开短链')
    return match.group(1).lower()

def at(obj, path):
    if path in ('', '$'):
        return obj
    current = obj
    for part in path.removeprefix('$.').split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current

def number(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError('boolean is not a count')
    if isinstance(value, str):
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*([万亿wWkK]?)\s*', value.replace(',', ''))
        if not match:
            raise ValueError('unrecognized numeric format')
        return float(match.group(1)) * {'': 1, '万': 10000, '亿': 100000000, 'w': 10000, 'k': 1000}[match.group(2).lower()]
    return float(value)

def mapped(item, config):
    output = {}
    for field, spec in config.get('fields', {}).items():
        if isinstance(spec, str):
            spec = {'path': spec}
        value = at(item, spec['path'])
        if value is not None:
            if 'item_path' in spec:
                if not isinstance(value, list):
                    raise ValueError('Expected array for item_path')
                value = [at(element, spec['item_path']) for element in value]
            if field == 'published_at' and spec.get('format') == 'iso8601':
                from datetime import datetime
                dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    raise ValueError('Timestamp lacks timezone')
                value = int(dt.timestamp())
            if field in {'likes', 'saves', 'comments', 'shares', 'followers', 'published_at', 'price'}:
                value = number(value)
                if value is None:
                    continue
                value = value * spec.get('scale', 1)
                if field != 'price':
                    if value != int(value):
                        raise ValueError('non-integral count/timestamp')
                    value = int(value)
            elif field.endswith('_id'):
                value = str(value)
            output[field] = value
    return output

class DataProvider(ABC):
    synthetic = False
    warnings: list[str]
    evidence: list[Evidence]
    @abstractmethod
    def account(self, account_id): ...
    @abstractmethod
    def notes(self, account_id, limit): ...
    @abstractmethod
    def products(self, account_id): ...
    @abstractmethod
    def comments(self, note_id, limit): ...
    @abstractmethod
    def detail(self, note): ...

class TikHubProvider(DataProvider):
    """Normalize ONLY an explicitly reviewed, snapshot-backed field contract."""
    def __init__(self, client, contract, synthetic=False):
        self.client, self.contract, self.synthetic = client, contract, synthetic
        self.warnings, self.evidence = [], []
        if not synthetic:
            if contract.get('provenance') != 'observed-live-response' or not contract.get('validated'):
                raise ValueError('Real responses must be inspected and a field contract validated before using TikHubProvider')
            unsigned = {k: v for k, v in contract.items() if k != 'contract_digest'}
            if digest(unsigned) != contract.get('contract_digest'):
                raise ValueError('Contract changed since validation; validate again')

    def _get(self, kind, params):
        payload, snapshot = self.client.get(kind, params)
        config = self.contract['endpoints'][kind]
        if at(payload, config['success_path']) != config['success_value']:
            self.client.store.invalidate(kind if self.synthetic else ENDPOINTS[kind], params)
            raise ProviderError(f'{kind}: upstream unsuccessful or schema changed')
        return payload, snapshot, config

    def _convert(self, cls, item, config, context, snapshot, kind):
        values = mapped(item, config)
        for key, value in context.items():
            if values.get(key) is not None and values[key] != value:
                raise ValueError('response identity mismatch')
            values[key] = value
        obj = make_model(cls, values)
        entity_id = getattr(obj, {'account': 'account_id', 'notes': 'note_id', 'detail': 'note_id', 'products': 'product_id', 'comments': 'comment_id'}[kind])
        evidence_kind = {'account': 'account', 'notes': 'note', 'detail': 'note', 'products': 'product', 'comments': 'comment'}[kind]
        source_url = getattr(obj, 'url', None)
        if isinstance(obj, Comment):
            source_url = f'https://www.xiaohongshu.com/explore/{obj.note_id}'
        excerpt = getattr(obj, 'body', None) or getattr(obj, 'text', None) or getattr(obj, 'bio', None) or getattr(obj, 'name', None) or getattr(obj, 'title', None) or ''
        evidence_id = evidence_kind + ':' + entity_id + (':detail' if kind == 'detail' else '')
        self.evidence.append(Evidence(evidence_id, evidence_kind, entity_id, source_url, snapshot, str(excerpt), self.synthetic))
        return obj

    def account(self, account_id):
        payload, snapshot, config = self._get('account', {'user_id': account_id})
        item = at(payload, config['items_path'])
        if not isinstance(item, dict):
            raise ProviderError('account: expected observed object path')
        return self._convert(Account, item, config, {'account_id': account_id, 'url': f'https://www.xiaohongshu.com/user/profile/{account_id}'}, snapshot, 'account')

    def _pages(self, kind, cls, params, context, limit):
        if kind not in self.contract['endpoints']:
            self.warnings.append(f'{kind}: 未获取到公开数据（没有经过真实响应验证的字段映射）')
            return []
        output, seen_ids, cursors = [], set(), set()
        for _ in range(100):
            try:
                payload, snapshot, config = self._get(kind, params)
                items = at(payload, config['items_path'])
                if not isinstance(items, list):
                    raise ProviderError(f'{kind}: list schema changed')
                for item in items:
                    try:
                        obj = self._convert(cls, item, config, context, snapshot, kind)
                        item_id = getattr(obj, {'notes': 'note_id', 'comments': 'comment_id', 'products': 'product_id'}[kind])
                        if item_id not in seen_ids:
                            output.append(obj)
                            seen_ids.add(item_id)
                    except (ValueError, TypeError, KeyError):
                        self.warnings.append(f'{kind}: skipped invalid record; see {snapshot}')
                    if len(output) >= limit:
                        return output
                pagination = config.get('pagination')
                if not pagination:
                    self.warnings.append(f'{kind}: 未验证分页字段，仅使用已获取页')
                    break
                more = at(payload, pagination['has_more_path'])
                if type(more) not in (bool, int) or more not in (True, False, 0, 1):
                    raise ProviderError(f'{kind}: pagination state missing or invalid')
                if not more:
                    break
                if not items:
                    raise ProviderError(f'{kind}: empty page with has_more')
                next_params = {param: at(payload, path) for param, path in pagination.get('next_params', {}).items()}
                if pagination.get('page_parameter'):
                    key = pagination['page_parameter']
                    next_params[key] = int(params.get(key, 1)) + 1
                if not next_params or any(value in (None, '') for value in next_params.values()):
                    raise ProviderError(f'{kind}: next cursor missing')
                fingerprint = digest(next_params)
                if fingerprint in cursors:
                    raise ProviderError(f'{kind}: repeated cursor; pagination stopped')
                cursors.add(fingerprint)
                params = {**params, **next_params}
            except (ProviderError, ValueError, KeyError, TypeError):
                self.warnings.append(f'{kind}: 部分接口失败或字段变化；保留已获取数据')
                break
        else:
            self.warnings.append(f'{kind}: page limit reached')
        return output

    def notes(self, account_id, limit):
        return self._pages('notes', Note, {'user_id': account_id}, {'account_id': account_id}, limit)

    def products(self, account_id):
        return self._pages('products', Product, {'user_id': account_id, 'page': 1}, {}, 100)

    def comments(self, note_id, limit):
        return self._pages('comments', Comment, {'note_id': note_id}, {'note_id': note_id}, limit)

    def detail(self, note):
        if 'detail' not in self.contract['endpoints']:
            return note
        payload, snapshot, config = self._get('detail', {'note_id': note.note_id})
        result = self._convert(Note, at(payload, config['items_path']), config,
                               {'note_id': note.note_id, 'account_id': note.account_id}, snapshot, 'detail')
        values = asdict(note)
        # Keep one list-snapshot metric basis; detail endpoints may be measured at another time.
        values.update({k: v for k, v in asdict(result).items() if v is not None and v != [] and k not in {'likes','saves','comments','shares'}})
        return make_model(Note, values)

class FixtureClient:
    def __init__(self, folder, store):
        self.folder, self.store, self.calls = Path(folder), store, 0

    def get(self, kind, params):
        cache = self.store.get(kind, params)
        if cache:
            return cache
        self.calls += 1
        all_data = read(self.folder / 'raw.json')
        if kind == 'notes':
            page = int(params.get('cursor', 0))
            payload = all_data['notes'][page]
        elif kind == 'comments':
            payload = all_data['comments'][params['note_id']][int(params.get('cursor', 0))]
        elif kind == 'detail':
            payload = all_data['detail'][params['note_id']]
        else:
            payload = all_data[kind]
        name = self.store.save(kind, params, payload)
        return payload, name

def validate_contract(draft, samples_root):
    """Do not infer field semantics. Verify human/agent-selected paths against captured data."""
    if draft.get('provenance') != 'observed-live-response':
        raise ValueError('Only captured real responses can certify a live contract')
    if not {'account', 'notes'} <= set(draft['endpoints']):
        raise ValueError('account and notes mappings are required')
    for kind, config in draft['endpoints'].items():
        if kind not in ENDPOINTS:
            raise ValueError('Endpoint outside public read allowlist')
        sample_path = (Path(samples_root) / config['sample']).resolve()
        if not sample_path.is_relative_to(Path(samples_root).resolve()):
            raise ValueError('snapshot path must stay inside snapshot root')
        record = read(sample_path)
        if record.get('provider') != 'tikhub' or record.get('endpoint') != ENDPOINTS[kind] or record.get('status') != 200:
            raise ValueError('Sample provenance/endpoint/status mismatch')
        payload = record['response']
        if at(payload, config['success_path']) != config['success_value']:
            raise ValueError('Sample was not a successful upstream result')
        items = at(payload, config['items_path'])
        items = items if isinstance(items, list) else [items]
        if not items or not all(isinstance(i, dict) for i in items):
            raise ValueError('A nonempty real sample is required for mapping')
        required_id = {'account':'account_id','notes':'note_id','detail':'note_id','products':'product_id','comments':'comment_id'}[kind]
        if required_id not in config['fields']:
            raise ValueError(f'{kind}: map the observed primary ID')
        cls = {'account':Account,'notes':Note,'detail':Note,'products':Product,'comments':Comment}[kind]
        from dataclasses import fields
        if set(config['fields']) - {f.name for f in fields(cls)}:
            raise ValueError('Unrecognized normalized field')
        for target, spec in config['fields'].items():
            path = spec if isinstance(spec, str) else spec['path']
            if not any(at(item, path) is not None for item in items):
                raise ValueError(f'{kind}.{target} is not observed; omit unavailable field')
        for item in items:
            values = mapped(item,config)
            if cls == Account:
                values.setdefault('url','https://www.xiaohongshu.com/user/profile/'+str(values.get('account_id','')))
            elif cls == Note:
                values.setdefault('account_id','sample-context')
            elif cls == Comment:
                values.setdefault('note_id','sample-context')
            make_model(cls,values)
        pagination = config.get('pagination')
        if pagination:
            for path in [pagination['has_more_path'], *pagination.get('next_params', {}).values()]:
                if at(payload, path) is None:
                    raise ValueError('Pagination path not observed')
        config['sample_sha256'] = digest(record)
    draft['validated'] = True
    draft.pop('contract_digest', None)
    draft['contract_digest'] = digest(draft)
    return draft
