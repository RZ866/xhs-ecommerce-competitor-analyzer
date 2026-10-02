import time
from dataclasses import asdict
from .models import Account, Evidence, MISSING
from .providers import identity
from .storage import dump, digest
from .analysis import rank_notes
from .images import fetch_cover

def collect(provider, url, output, notes_limit=100, deep_notes=20, comment_notes=10, comments_per_note=100,
            mode='deep', images=False):
    account_id = identity(url)
    warnings = []
    def stage(name, action, fallback):
        try:
            return action()
        except Exception as exc:
            # Never print provider bodies, URLs containing tokens, headers or exception strings.
            warnings.append(f'{name}: {MISSING}（{type(exc).__name__}；该阶段已降级）')
            return fallback
    account = stage('账号资料', lambda: provider.account(account_id), Account(account_id, f'https://www.xiaohongshu.com/user/profile/{account_id}'))
    notes = stage('笔记', lambda: provider.notes(account_id, notes_limit), [])
    if any(n.published_at is None for n in notes):
        warnings.append('部分笔记无发布时间；无法确认样本是账号最近笔记，按数据源返回顺序采样。')
    else:
        notes.sort(key=lambda n: n.published_at, reverse=True)
    # Enrich available notes before computing the single final baseline/ranking.
    # List responses may omit bodies; details are optional and limited to the provisional deep set.
    _, provisional = rank_notes(notes, deep_notes)
    deep_ids = {r['note_id'] for r in provisional}
    notes = [stage('笔记详情', lambda n=n: provider.detail(n), n) if n.note_id in deep_ids else n for n in notes]
    baseline, top = rank_notes(notes, deep_notes)
    # The top may change when detail metrics differ: a second bounded pass fills newly selected bodies.
    new_ids = {r['note_id'] for r in top} - deep_ids
    notes = [stage('笔记详情', lambda n=n: provider.detail(n), n) if n.note_id in new_ids else n for n in notes]
    baseline, top = rank_notes(notes, deep_notes)
    products = stage('公开商品', lambda: provider.products(account_id), [])
    _, comment_rank = rank_notes(notes, comment_notes)
    comments = []
    for row in comment_rank:
        comments.extend(stage('公开评论', lambda row=row: provider.comments(row['note_id'], comments_per_note), []))
    covers = []
    if images:
        for note in notes:
            if note.note_id not in {r['note_id'] for r in top} or not note.cover_url:
                continue
            cover = stage('封面图片', lambda n=note: fetch_cover(n.cover_url, output, n.note_id), None)
            if cover:
                covers.append(cover)
                provider.evidence.append(Evidence(cover['evidence_id'], 'image', note.note_id, note.cover_url,
                                                  cover['path'], f"已读取图片 {cover['width']} × {cover['height']}", provider.synthetic))
    if not products:
        warnings.append('公开商品：' + MISSING + '；不能确认在售SKU、销量、GMV或利润。')
    if not comments:
        warnings.append('公开评论：' + MISSING + '；消费者需求地图不可据此补造。')
    if not covers:
        warnings.append('封面视觉：未获取到可分析图片；不从标题推断画面。')
    evidence = list({e.evidence_id: asdict(e) for e in provider.evidence}.values())
    dataset = {'account': asdict(account), 'notes': [asdict(n) for n in notes], 'products': [asdict(p) for p in products],
               'comments': [asdict(c) for c in comments], 'evidence': evidence, 'baseline': baseline, 'top_notes': top,
               'warnings': warnings + provider.warnings, 'synthetic': provider.synthetic, 'created_at': time.time(),
               'mode': mode, 'images': covers,
               'parameters': {'notes_limit': notes_limit, 'deep_notes': deep_notes, 'comment_notes': comment_notes,
                              'comments_per_note': comments_per_note},
               'sampling': '数据提供方返回的公开样本；无完整历史/曝光/订单数据；评论存在排序与可见性偏差。'}
    dataset['dataset_digest'] = digest({k: v for k, v in dataset.items() if k not in {'created_at', 'images', 'evidence', 'warnings'}})
    dump(str(output) + '/dataset.json', dataset)
    return dataset
