from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
from typing import Literal
from urllib.parse import urlsplit
import math

MISSING = '未获取到公开数据'
TYPES = {'FACT', 'ANALYSIS', 'INFERENCE'}

def safe_url(value):
    if not isinstance(value, str):
        return None
    p = urlsplit(value)
    return value if p.scheme == 'https' and p.hostname and not p.username and not p.password else None

@dataclass
class Account:
    account_id: str
    url: str
    nickname: str | None = None
    bio: str | None = None
    followers: int | None = None

@dataclass
class Note:
    note_id: str
    account_id: str
    title: str | None = None
    body: str | None = None
    published_at: int | None = None
    likes: int | None = None
    saves: int | None = None
    comments: int | None = None
    shares: int | None = None
    url: str | None = None
    cover_url: str | None = None
    product_ids: list[str] = field(default_factory=list)

@dataclass
class Product:
    product_id: str
    name: str | None = None
    price: float | None = None
    currency: str | None = None
    url: str | None = None

@dataclass
class Comment:
    comment_id: str
    note_id: str
    text: str | None = None
    likes: int | None = None

@dataclass
class Evidence:
    evidence_id: str
    kind: str
    entity_id: str
    source_url: str | None
    snapshot: str
    excerpt: str
    synthetic: bool = False

@dataclass
class Claim:
    claim: str
    claim_type: Literal['FACT', 'ANALYSIS', 'INFERENCE']
    confidence: float
    evidence_ids: list[str]

    def __post_init__(self):
        if self.claim_type not in TYPES or not isinstance(self.claim, str) or not self.claim.strip():
            raise ValueError('Invalid claim/type')
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError('confidence must be 0..1')
        if not isinstance(self.evidence_ids, list) or not self.evidence_ids or not all(isinstance(x, str) for x in self.evidence_ids):
            raise ValueError('Every claim needs evidence_ids')

@dataclass
class AnalysisResult:
    account: dict
    notes: list[dict]
    products: list[dict]
    comments: list[dict]
    evidence: list[dict]
    baseline: dict
    top_notes: list[dict]
    claims: list[dict]
    ai: dict
    matrix: list[dict]
    needs: list[dict]
    hypotheses: dict
    warnings: list[str]
    metadata: dict

def make_model(cls, data):
    names = {f.name for f in fields(cls)}
    if set(data) - names:
        raise ValueError(f'Unknown {cls.__name__} fields')
    obj = cls(**data)
    for key, value in asdict(obj).items():
        if value is None:
            continue
        if key.endswith('_ids'):
            if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
                raise ValueError(f'Invalid {key}')
        elif key in {'likes', 'saves', 'comments', 'shares', 'followers', 'published_at'}:
            if type(value) is not int or value < 0:
                raise ValueError(f'Invalid {key}')
        elif key == 'price':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid price')
        elif not isinstance(value, str):
            raise ValueError(f'Invalid {key}')
        elif key.endswith('_id') and not value:
            raise ValueError(f'Empty {key}')
        elif key.endswith('url') and not safe_url(value):
            raise ValueError(f'Invalid URL: {key}')
    return obj
