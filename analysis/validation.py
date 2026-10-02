import math
from .models import Claim

FORBIDDEN=('TIKHUB_API_KEY','probe','endpoint selection','PowerShell','请运行 Python','schema calibration','请配置 Cookie','请登录小红书')
def validate(result):
    known={e['evidence_id'] for e in result['evidence']}
    notes={n['note_id'] for n in result['notes']}
    if len(notes)!=len(result['notes']):raise ValueError('duplicate_notes')
    if result['coverage']['analyzed_notes']!=len(notes):raise ValueError('coverage')
    def visit(value):
        if isinstance(value,dict):
            if 'claim' in value:
                Claim(**{k:value[k] for k in ('claim','claim_type','confidence','evidence_ids')})
                if not set(value['evidence_ids'])<=known:raise ValueError('unresolved_evidence')
                if any(word in value['claim'] for word in ('保证爆款','必爆','保证转化','利润最高','销量最高')):raise ValueError('unsupported_guarantee')
            for v in value.values():visit(v)
        elif isinstance(value,list):
            for v in value:visit(v)
        elif isinstance(value,float) and not math.isfinite(value):raise ValueError('non_finite')
    visit(result)
    return result

def finalize(result,payload):
    """Host semantic conclusions may supplement, never mutate observed data."""
    import hashlib,json
    digest=hashlib.sha256(json.dumps(result['notes'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if payload.get('data_digest')!=digest:raise ValueError('stale_analysis')
    if not payload.get('sections'):raise ValueError('empty_semantic_analysis')
    from .account import hypotheses
    from .models import claim
    notes={n['note_id']:n for n in result['notes']}
    for item in payload.get('product_mentions',[]):
        name=item.get('name');ids=item.get('evidence_ids',[])
        if not isinstance(name,str) or not 2<=len(name)<=60 or not ids:raise ValueError('product_mention')
        for identity in ids:
            n=notes.get(identity)
            if not n or name not in ((n.get('title') or '')+'\n'+(n.get('description') or '')):raise ValueError('product_not_observed')
        if any(p['name']==name for p in result['products']):continue
        result['products'].append({'product_id':'mention-'+hashlib.sha256(name.encode()).hexdigest()[:12],'name':name,'evidence_ids':list(dict.fromkeys(ids)),'kind':'public_text_mention','price':None,'url':None})
        result['sections']['产品出现频率'].append(claim(f'公开文本出现“{name}”：{len(set(ids))} 篇；产品身份仍需核验，非销量或利润排名',ids,confidence=.6))
    if payload.get('product_mentions'):result['hypotheses']=hypotheses(result['products'],result['notes'])
    allowed=set(result['sections'])-{'账号基本盘','发布频率','高表现笔记'}
    for section,claims in payload.get('sections',{}).items():
        if section not in allowed or not isinstance(claims,list):raise ValueError('section')
        for c in claims:
            if c.get('claim_type') not in ('ANALYSIS','INFERENCE'):raise ValueError('semantic_fact')
            if c.get('confidence',1)>.8:raise ValueError('overconfidence')
            if section=='封面 DNA':
                inspected=set(payload.get('inspected_images',[]))
                available={v['note_id'] for v in result.get('visual_evidence',[])}
                if not set(c.get('evidence_ids',[]))<=inspected.intersection(available):raise ValueError('unseen_image')
        result['sections'][section]=claims
    if 'hypotheses' in payload:
        expected={'产品研究方向':3,'内容模型':5,'原创标题结构':10,'封面结构':5,'原创测试选题':30}
        for key,size in expected.items():
            items=payload['hypotheses'].get(key,[])
            if len(items)!=size or any(c.get('claim_type')!='INFERENCE' or c.get('confidence',1)>.5 for c in items):raise ValueError('hypothesis_format')
        from .models import HYPOTHESIS
        result['hypotheses']={**payload['hypotheses'],'label':HYPOTHESIS}
    result['analysis_method']='公开数据统计与宿主语义分析'
    if result['coverage'].get('restricted') or result['coverage'].get('old_data_reused'):
        for claims in result['sections'].values():
            for c in claims:
                if c['claim_type']!='FACT':c['confidence']=min(c['confidence'],.4)
    return validate(result)
