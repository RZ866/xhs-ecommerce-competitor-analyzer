from dataclasses import asdict
from collections import Counter
import statistics
from .models import Claim, AnalysisResult, MISSING

METRICS = ('likes', 'saves', 'comments', 'shares')
HYPOTHESIS_COUNTS = {'products': 3, 'content_models': 5, 'titles': 10, 'covers': 5, 'topics': 30}
HYPOTHESIS_LABEL = '基于竞品公开数据形成的测试假设'

def rank_notes(notes, limit=20):
    """Choose a comparable common subset; never impute missing interactions as zero."""
    if not notes:
        return {'status': MISSING, 'metrics': [], 'eligible': 0, 'excluded': 0}, []
    metrics = [key for key in METRICS if sum(getattr(n, key) is not None for n in notes) / len(notes) >= .8]
    if not metrics:
        return {'status': MISSING, 'metrics': [], 'eligible': 0, 'excluded': len(notes)}, []
    eligible = [n for n in notes if all(getattr(n, key) is not None for key in metrics)]
    scores = {n.note_id: sum(getattr(n, key) for key in metrics) for n in eligible}
    median = statistics.median(scores.values()) if scores else 0
    ranked = sorted(eligible, key=lambda n: (-scores[n.note_id], n.note_id))[:limit]
    baseline = {'label': '相对互动指数（内部研究指标）', 'metrics': metrics,
                'median': median, 'eligible': len(eligible), 'excluded': len(notes) - len(eligible),
                'formula': '100 × (可比互动总量 + 1) / (账号样本可比互动总量中位数 + 1)',
                'limits': '仅比较本次账号样本；未校正发布时长、曝光或投流；不代表成交、利润或官方爆款认定。'}
    return baseline, [{'note_id': n.note_id, 'title': n.title, 'score': scores[n.note_id],
                       'index': round(100 * (scores[n.note_id] + 1) / (median + 1), 2),
                       'evidence_ids': ['note:' + n.note_id]} for n in ranked]

def validate_ai(payload, dataset, require_complete=True):
    allowed = {e['evidence_id']: e for e in dataset['evidence']}
    note_ids = {n['note_id'] for n in dataset['notes']}
    product_ids = {p['product_id'] for p in dataset['products']}
    top_ids = {n['note_id'] for n in dataset['top_notes']}
    image_evidence = {e['entity_id'] for e in dataset['evidence'] if e['kind'] == 'image'}
    if payload.get('dataset_digest') != dataset['dataset_digest']:
        raise ValueError('AI analysis belongs to a different dataset')
    if payload.get('source') not in {'agent', 'remote-model', 'synthetic-fixture'}:
        raise ValueError('AI source required')
    if payload.get('source') == 'synthetic-fixture' and not dataset['synthetic']:
        raise ValueError('Synthetic analysis cannot be used for live data')

    def check(value):
        if isinstance(value, dict):
            if 'claim' in value:
                claim = Claim(**{key: value[key] for key in ('claim', 'claim_type', 'confidence', 'evidence_ids')})
                if any(e not in allowed for e in claim.evidence_ids):
                    raise ValueError('Unknown evidence ID')
                if any(term in claim.claim for term in ('保证成功', '利润最高', '必爆', '必然成交')):
                    raise ValueError('Unsupported deterministic commercial assertion')
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(payload)
    if 'claim' not in payload.get('positioning', {}):
        raise ValueError('Positioning needs a supported claim')
    required_note_fields = ('content_model', 'title_structure', 'body_structure', 'scenes', 'pain_points', 'selling_points')
    covered = set()
    for row in payload.get('note_analyses', []):
        if row['note_id'] not in top_ids or row['note_id'] in covered:
            raise ValueError('Unexpected or duplicate analyzed note')
        covered.add(row['note_id'])
        for key in required_note_fields:
            if not isinstance(row.get(key), dict) or 'claim' not in row[key]:
                raise ValueError(f'Missing note analysis {key}')
            if not any(allowed[e]['entity_id'] == row['note_id'] and allowed[e]['kind'] == 'note' for e in row[key]['evidence_ids']):
                raise ValueError('Note analysis must cite the analyzed note')
        visual = row.get('visual')
        if visual and visual.get('claim'):
            if row['note_id'] not in image_evidence or not any(allowed[e]['kind'] == 'image' and allowed[e]['entity_id'] == row['note_id'] for e in visual['evidence_ids']):
                raise ValueError('Visual claim requires an accessible image evidence')
    if require_complete and covered != top_ids:
        raise ValueError('Analyze all selected deep notes')
    for row in payload.get('needs', []):
        if row.get('claim_type') not in ('ANALYSIS', 'INFERENCE') or 'claim' not in row:
            raise ValueError('Needs require typed analysis claims')
        if not any(allowed[e]['kind'] == 'comment' for e in row['evidence_ids']):
            raise ValueError('Consumer need must cite a public comment')
    for row in payload.get('matrix', []):
        if row.get('note_id') not in note_ids or row.get('product_id') not in product_ids or 'claim' not in row:
            raise ValueError('Matrix must reference known notes and products')
        if not any(allowed[e]['entity_id'] == row['note_id'] for e in row['evidence_ids']) or not any(allowed[e]['entity_id'] == row['product_id'] for e in row['evidence_ids']):
            raise ValueError('Matrix needs note and product evidence')
        if row['claim_type'] != 'INFERENCE':
            raise ValueError('AI-associated product links must be INFERENCE; explicit links are added separately')
    for category, count in HYPOTHESIS_COUNTS.items():
        values = payload.get('hypotheses', {}).get(category, [])
        if require_complete and len(values) != count:
            raise ValueError(f'{category} must have {count} hypotheses')
        if len({v.get('claim') for v in values}) != len(values):
            raise ValueError('Duplicate hypotheses')
        if any(v.get('claim_type') != 'INFERENCE' or v.get('label') != HYPOTHESIS_LABEL for v in values):
            raise ValueError('All tests must be labeled hypotheses')
    return payload

def build_result(dataset, ai=None, ai_warning=None):
    evidence = dataset['evidence']
    claims = []
    note_evidence = [e['evidence_id'] for e in evidence if e['kind'] == 'note']
    if note_evidence:
        claims.append(asdict(Claim(f"本次获取 {len(dataset['notes'])} 篇公开笔记；可比较样本 {dataset['baseline']['eligible']} 篇。", 'FACT', 1.0, note_evidence)))
    for row in dataset['top_notes'][:3]:
        claims.append(asdict(Claim(f"笔记「{row['title'] or row['note_id']}」相对互动指数 {row['index']}（内部研究指标）。", 'ANALYSIS', .85, row['evidence_ids'])))
    products = {p['product_id'] for p in dataset['products']}
    matrix = []
    for note in dataset['notes']:
        for pid in note['product_ids']:
            if pid in products:
                matrix.append({'note_id': note['note_id'], 'product_id': pid,
                    **asdict(Claim('数据源明确关联的内容与商品；不代表购买或成交。', 'FACT', 1.0,
                                  ['note:' + note['note_id'], 'product:' + pid]))})
    warnings = list(dataset['warnings'])
    if ai_warning:
        warnings.append(ai_warning)
    if ai:
        validate_ai(ai, dataset)
        claims.append(ai['positioning'])
        matrix.extend(ai.get('matrix', []))
    else:
        warnings.append('AI 分析未完成；未生成定位、需求或测试假设。请按 analysis-request.md 完成分析后 finalize。')
    return AnalysisResult(account=dataset['account'], notes=dataset['notes'], products=dataset['products'],
                          comments=dataset['comments'], evidence=evidence, baseline=dataset['baseline'],
                          top_notes=dataset['top_notes'], claims=claims, ai=ai or {}, matrix=matrix,
                          needs=ai.get('needs', []) if ai else [], hypotheses=ai.get('hypotheses', {}) if ai else {},
                          warnings=list(dict.fromkeys(warnings)),
                          metadata={'synthetic': dataset['synthetic'], 'dataset_digest': dataset['dataset_digest'],
                                    'ai_status': 'complete' if ai else 'pending', 'mode': dataset['mode'],
                                    'created_at': dataset['created_at'], 'parameters': dataset['parameters'],
                                    'ai_source': ai.get('source') if ai else None})
