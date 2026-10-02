from statistics import median

WEIGHTS={'likes':.4,'collects':.4,'comments_count':.2}
def score(notes):
    baseline={k:median([n[k] for n in notes if n.get(k) is not None]) if any(n.get(k) is not None for n in notes) else None for k in WEIGHTS}
    rows=[]
    for note in notes:
        weights={k:w for k,w in WEIGHTS.items() if note.get(k) is not None and baseline[k] is not None}
        total=sum(weights.values());weights={k:w/total for k,w in weights.items()} if total else {}
        multiples={k:(note[k]+1)/(baseline[k]+1) for k in weights}
        available=[note[k] for k in ('likes','collects','comments_count','shares') if note.get(k) is not None]
        rows.append({'note_id':note['note_id'],'score':sum(weights[k]*multiples[k] for k in weights) if weights else None,
                     'weights':weights,'multiples':multiples,'absolute':sum(available) if available else None,'metrics':list(weights)})
    return {'baseline':baseline,'rows':rows,'relative_top':sorted([r for r in rows if r['score'] is not None],key=lambda r:r['score'],reverse=True)[:20],
            'absolute_top':sorted([r for r in rows if r['absolute'] is not None],key=lambda r:r['absolute'],reverse=True)[:20],
            'notice':'内部研究指标，并非小红书官方指标。使用（计数+1）/（样本中位数+1）平滑零值；缺失项重分配权重。不同可用指标组合仅供探索性比较；互动不代表成交。'}
