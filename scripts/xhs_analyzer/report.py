import csv
import html
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from .models import MISSING, safe_url
from .storage import dump, redact
from .analysis import HYPOTHESIS_LABEL

LABELS = {'FACT': '事实', 'ANALYSIS': '分析', 'INFERENCE': '推断'}
def esc(value):
    return html.escape(str(MISSING if value is None else value), quote=True)

def anchor(eid):
    import hashlib
    return 'ev-' + hashlib.sha256(eid.encode()).hexdigest()[:18]

def links(ids):
    return '<span class="evidence-links">证据：' + ' '.join(f'<a href="#{anchor(i)}">{esc(i)}</a>' for i in ids) + '</span>'

def claim_html(item):
    return f'<div class="claim"><span class="badge {esc(item["claim_type"])}">【{LABELS[item["claim_type"]]}】</span>{esc(item["claim"])}<span class="muted"> · 把握 {item["confidence"]:.0%}</span>{links(item["evidence_ids"])}</div>'

def section(title, body, id=''):
    return f'<section id="{esc(id)}"><h2>{esc(title)}</h2>{body}</section>'

def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + esc(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table></div>'

def csv_value(value):
    value = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else (MISSING if value is None else str(value))
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value

def write_csv(path, rows, default_fields):
    headers = list(dict.fromkeys(key for row in rows for key in row)) or default_fields
    with Path(path).open('w', encoding='utf-8-sig', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=headers)
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in headers} for row in rows)

def all_claims(value):
    result = []
    if isinstance(value, dict):
        if 'claim' in value:
            result.append(value)
        for child in value.values():
            result.extend(all_claims(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(all_claims(child))
    return result

def render(result, output, dataset=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = redact(asdict(result))
    known = {e['evidence_id'] for e in data['evidence']}
    for item in all_claims(data):
        if not item.get('evidence_ids') or not set(item['evidence_ids']) <= known:
            raise ValueError('Report rejected: unsupported evidence reference')
    boss = data['metadata']['mode'] == 'boss'
    ai = data['ai']
    body = '<div class="notice">' + ('<strong>合成 MOCK 示例：不是实际账号数据，不能作为商业决策依据。</strong><br>' if data['metadata']['synthetic'] else '') + '样本范围：本次公开数据；缺失不等于 0。相对互动指数为内部研究指标。置信度为分析者主观把握。' + '</div>'
    body += '<nav><a href="#overview">概况</a><a href="#top">TOP内容</a><a href="#matrix">内容×商品</a><a href="#needs">需求地图</a><a href="#tests">测试假设</a><a href="#evidence">证据</a></nav>'
    metrics = [('公开笔记', len(data['notes'])), ('可比样本', data['baseline']['eligible']), ('公开商品', len(data['products']) if data['products'] else None), ('获取评论', len(data['comments']) if data['comments'] else None)]
    body += '<div class="grid">' + ''.join(f'<div class="card"><div class="muted">{esc(k)}</div><div class="metric">{esc(v)}</div></div>' for k, v in metrics) + '</div>'
    profile = f'<p><strong>{esc(data["account"].get("nickname"))}</strong> · 粉丝 {esc(data["account"].get("followers"))}</p><p>{esc(data["account"].get("bio"))}</p>'
    profile += links([e['evidence_id'] for e in data['evidence'] if e['kind'] == 'account'])
    profile += claim_html(ai['positioning']) if ai.get('positioning') else '<p>' + MISSING + '（AI 定位待完成）</p>'
    body += section('账号概况 · 一句话定位', profile, 'overview')
    product_counts = Counter(row['product_id'] for row in data['matrix'] if row['claim_type'] == 'FACT')
    body += section('主要商品 · 按公开关联内容数量排列', table(['商品', '公开价格 / 原币种', '关联笔记数', '证据'],
        [[esc(p['name']), esc(p['price']) + ' / ' + esc(p['currency']), str(product_counts[p['product_id']]), links(['product:' + p['product_id']])] for p in sorted(data['products'], key=lambda p: -product_counts[p['product_id']])[:10]]) if data['products'] else '<p>' + MISSING + '</p>')
    body += '<div class="two">'
    for field, title in [('content_model', '高表现内容模型'), ('scenes', '高频场景'), ('pain_points', '高频痛点'), ('selling_points', '公开内容卖点表达')]:
        groups = defaultdict(list)
        for row in ai.get('note_analyses', []):
            c = row[field]
            groups[c.get('tag', c['claim'])].append(c)
        content = ''
        for tag, values in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:5]:
            ids = list(dict.fromkeys(i for v in values for i in v['evidence_ids']))
            c = dict(values[0], claim=f'{tag} · 在深度分析样本中出现 {len(values)} 篇', claim_type='ANALYSIS', evidence_ids=ids)
            content += claim_html(c)
        body += section(title, content or '<p>AI 分析待完成 / ' + MISSING + '</p>')
    body += '</div>'
    maximum = max([r['index'] for r in data['top_notes']] or [1]) or 1
    top_rows = data['top_notes'][:5] if boss else data['top_notes']
    body += section('TOP 内容 · 账号自身相对互动表现', '<p class="muted">' + esc(data['baseline'].get('formula', MISSING)) + '；可比字段：' + esc(' / '.join(data['baseline']['metrics'])) + '</p>' +
        table(['笔记', '互动总量', '相对互动指数（内部研究指标）', '证据'],
              [[esc(r['title']), str(r['score']), f'<strong>{r["index"]}</strong><div class="bar"><i style="width:{100*r["index"]/maximum:.2f}%"></i></div>', links(r['evidence_ids'])] for r in top_rows]), 'top')
    # A real cross-tab, plus expandable edge-level provenance.
    product_names = {p['product_id']: p['name'] or p['product_id'] for p in data['products']}
    note_models = {r['note_id']: r['content_model'].get('tag', r['content_model']['claim']) for r in ai.get('note_analyses', [])}
    cells = defaultdict(list)
    for row in data['matrix']:
        cells[(note_models.get(row['note_id'], '未分类内容'), row['product_id'])].append(row)
    models = list(dict.fromkeys(k[0] for k in cells))
    matrix_body = table(['内容模型'] + list(product_names.values()), [[esc(model)] +
        [(str(len({r['note_id'] for r in cells[(model, pid)]})) + links(list(dict.fromkeys(e for r in cells[(model, pid)] for e in r['evidence_ids'])))) if cells[(model, pid)] else '—' for pid in product_names] for model in models]) if cells else '<p>' + MISSING + '</p>'
    matrix_body += '<p class="muted">格内为关联笔记数量，含明确关联和推断关联；不是销量。详情区分关联类型。</p><details><summary>查看关联判断</summary>' + ''.join(claim_html(r) for r in data['matrix']) + '</details>'
    body += section('内容 × 商品矩阵', matrix_body, 'matrix')
    body += section('消费者需求地图 · 公开评论信号', ''.join(claim_html(n) for n in data['needs']) or '<p>' + MISSING + '</p>', 'needs')
    names = {'products': '3 个商品测试方向', 'content_models': '5 种内容模型', 'titles': '10 个原创标题结构', 'covers': '5 种封面结构', 'topics': '30 个原创测试选题'}
    test_body = '<p class="notice">' + HYPOTHESIS_LABEL + ' · 不保证成功；逐项小规模验证。</p>'
    if boss:
        test_body += ''.join(claim_html(v) for v in data['hypotheses'].get('products', []))
        test_body += '<p class="muted">Boss 模式仅展示核心测试方向；完整创作实验清单位于 analysis-result.json 或 deep 报告。</p>'
    else:
        for i, (key, title) in enumerate(names.items()):
            test_body += f'<button data-tab="tab-{key}" class="{"active" if i == 0 else ""}">{title}</button>'
        for i, key in enumerate(names):
            test_body += f'<div class="panel" id="tab-{key}" {"hidden" if i else ""}>' + ''.join('<div class="hypothesis">' + claim_html(v) + '</div>' for v in data['hypotheses'].get(key, [])) + '</div>'
    body += section('可测试方向', test_body, 'tests')
    if not boss:
        details = ''
        images = {im['note_id']: im for im in (dataset or {}).get('images', [])}
        for row in ai.get('note_analyses', []):
            details += '<details><summary>' + esc(row['note_id']) + ' · 标题 / 正文 / 场景 / 痛点 / 卖点 / 封面</summary>'
            if row['note_id'] in images:
                details += '<img alt="已获取的笔记封面" src="' + esc(images[row['note_id']]['data_url']) + '">'
            details += ''.join(claim_html(row[k]) for k in ('content_model', 'title_structure', 'body_structure', 'scenes', 'pain_points', 'selling_points'))
            details += claim_html(row['visual']) if row.get('visual') else '<p>封面视觉：' + MISSING + '</p>'
            details += '</details>'
        body += section('逐篇深度分析', details or '<p>AI 分析待完成</p>')
    body += section('数据覆盖与限制', '<details><summary>查看缺失与失败记录 (' + str(len(data['warnings'])) + ')</summary>' + ''.join('<p>' + esc(w) + '</p>' for w in data['warnings']) + '</details>')
    source = '<input id="evidence-search" placeholder="搜索证据 ID 或原文" aria-label="搜索证据">'
    entities = {}
    for kind, rows, idkey in [('note', data['notes'], 'note_id'), ('product', data['products'], 'product_id'), ('comment', data['comments'], 'comment_id')]:
        entities.update({(kind, row[idkey]): row for row in rows})
    entities[('account', data['account']['account_id'])] = data['account']
    for e in data['evidence']:
        url = safe_url(e['source_url'])
        source += f'<details class="source" id="{anchor(e["evidence_id"])}"><summary>{esc(e["evidence_id"])}{" · 合成" if e["synthetic"] else ""}</summary><p>{esc(e["excerpt"])}</p><p class="muted">本地快照：{esc(e["snapshot"])}</p>'
        if url and not e['synthetic']:
            source += f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">查看公开来源</a>'
        source += '<pre>' + esc(json.dumps(entities.get((e['kind'], e['entity_id']), {}), ensure_ascii=False, indent=2)) + '</pre></details>'
    body += section('证据浏览器 · 原始摘录与字段', source, 'evidence')
    template = (Path(__file__).resolve().parents[2] / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
    page = template.replace('@@BODY@@', body).replace('@@ACCOUNT@@', esc(data['account'].get('nickname'))).replace('@@STATUS@@', 'MOCK / 合成演示' if data['metadata']['synthetic'] else ('AI 待完成' if not ai else '公开数据研究'))
    (output / 'report.html').write_text(page, encoding='utf-8')
    dump(output / 'analysis-result.json', data)
    public_data = data if not boss else {k: data[k] for k in ('account', 'claims', 'baseline', 'matrix', 'needs', 'warnings', 'metadata')}
    if boss:
        public_data.update(top_notes=top_rows, hypotheses={'products': data['hypotheses'].get('products', [])})
    dump(output / 'report.json', public_data)
    selected_claims = all_claims(public_data)
    md = ['# 小红书电商竞品拆解', '', '**合成 MOCK 示例，不是实际账号数据。**' if data['metadata']['synthetic'] else '公开数据研究。', '', '相对互动指数为内部研究指标；互动不等于成交。', '']
    md += [f'- 【{LABELS[c["claim_type"]]}】{c["claim"]}（把握 {c["confidence"]:.0%}；证据：{", ".join(c["evidence_ids"])}）' for c in selected_claims]
    md += ['', '## 数据限制', *['- ' + w for w in data['warnings']], '', '## 证据', *['- ' + e['evidence_id'] + '：' + (e['excerpt'] or MISSING) + '；快照 ' + e['snapshot'] for e in data['evidence']]]
    (output / 'report.md').write_text('\n'.join(md), encoding='utf-8')
    write_csv(output / 'claims.csv', selected_claims, ['claim', 'claim_type', 'confidence', 'evidence_ids'])
    write_csv(output / 'top-notes.csv', top_rows, ['note_id', 'index'])
    if not boss:
        for key in ('notes', 'products', 'comments', 'matrix', 'needs'):
            write_csv(output / (key + '.csv'), data[key], ['status'])
    return output / 'report.html'
