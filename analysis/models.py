from dataclasses import dataclass,field,asdict
import math

MISSING='未获取到公开数据'
NO_DATA='当前匿名公开访问未能取得足够数据，本次无法完成可靠拆解。'
COMMENT_NOTICE='匿名公开模式下未获取到评论正文，因此本模块不做确定性消费者需求结论。'
HYPOTHESIS='基于竞品公开数据形成的测试假设'

@dataclass
class Account:
    account_id:str
    url:str
    nickname:str|None=None
    bio:str|None=None
    avatar:str|None=None
    followers:int|None=None
    follows:int|None=None
    likes_collects:int|None=None
    note_count:int|None=None
    fetched_at:float|None=None
    def __post_init__(self):
        if not self.account_id:raise ValueError('identity')
        for key in ('followers','follows','likes_collects','note_count'):
            value=getattr(self,key)
            if value is not None and (type(value) is not int or value<0):raise ValueError('count')

@dataclass
class Note:
    note_id:str
    account_id:str
    url:str
    title:str|None=None
    description:str|None=None
    publish_time:int|None=None
    type:str|None=None
    cover:str|None=None
    images:list=field(default_factory=list)
    likes:int|None=None
    collects:int|None=None
    comments_count:int|None=None
    shares:int|None=None
    author:str|None=None
    fetched_at:float|None=None
    source_fields:dict=field(default_factory=dict)

    def __post_init__(self):
        if not self.note_id or not self.account_id:raise ValueError('identity')
        for key in ('likes','collects','comments_count','shares','publish_time'):
            value=getattr(self,key)
            if value is not None and (type(value) is not int or value<0):raise ValueError('count')

@dataclass
class Product:
    product_id:str
    name:str
    evidence_ids:list
    kind:str='public_text_mention'
    price:float|None=None
    url:str|None=None

@dataclass
class Comment:
    comment_id:str
    note_id:str
    text:str

@dataclass
class Evidence:
    evidence_id:str
    entity_id:str
    kind:str
    public_url:str
    excerpt:str
    fields:dict
    fetched_at:float
    origin:str='PUBLIC_PAGE'

@dataclass
class Claim:
    claim:str
    claim_type:str
    confidence:float
    evidence_ids:list
    def __post_init__(self):
        if self.claim_type not in {'FACT','ANALYSIS','INFERENCE'}:raise ValueError('claim_type')
        if not self.claim or not isinstance(self.claim,str):raise ValueError('claim')
        if type(self.confidence) not in (float,int) or not math.isfinite(self.confidence) or not 0<=self.confidence<=1:raise ValueError('confidence')
        if not self.evidence_ids or not all(isinstance(x,str) for x in self.evidence_ids):raise ValueError('evidence')

@dataclass
class AnalysisResult:
    version:str
    title:str
    coverage:dict
    account:dict
    notes:list
    products:list
    evidence:list
    statistics:dict
    sections:dict
    hypotheses:dict
    status:str
    user_context:dict=field(default_factory=dict)

def claim(text,ids,kind='ANALYSIS',confidence=.6,**extra):
    return {**asdict(Claim(text,kind,confidence,list(dict.fromkeys(ids)))),**extra}
