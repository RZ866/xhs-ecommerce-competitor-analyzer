import csv,json,html
from pathlib import Path
from .models import MISSING,NO_DATA,HYPOTHESIS
from .validation import validate

def esc(value):return html.escape(str(value if value is not None else MISSING),quote=True)
def csv_safe(v):
    if v is None:return ''
    v=str(v)
    return "'"+v if v.startswith(('=','+','-','@','\t','\r')) else v

def render(result,output):
    validate(result);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    evidence={e['evidence_id']:e for e in result['evidence']};labels={'FACT':'【事实】','ANALYSIS':'【分析】','INFERENCE':'【推断】'}
    def card_claim(c):
        links=''
        for identity in c['evidence_ids']:
            e=evidence[identity];url=e['public_url']
            if not url.startswith('https://www.xiaohongshu.com/'):continue
            links+=f'<p><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(identity)}</a> · {esc(e.get("excerpt",""))}<br><small>{esc(json.dumps(e.get("fields",{}),ensure_ascii=False))}</small></p>'
        return f'<div class="claim"><span class="badge">{labels[c["claim_type"]]}</span> {esc(c["claim"])} <small class="muted">置信度 {c["confidence"]:.0%}</small><details><summary>查看证据</summary>{links}</details></div>'
    def cards(claims):return ''.join(card_claim(c) for c in claims) if claims else f'<p class="muted">{MISSING}</p>'
    cov=result['coverage'];sections=result['sections'];hyp=result['hypotheses'];account=result['account']
    body='<section class="card"><div class="grid">'
    for label,value in [('账号',account.get('nickname')),('粉丝',account.get('followers')),('公开产品提及',len(result['products']) if result['products'] else None)]:body+='<div>'+label+'<div class="metric">'+esc(value)+'</div></div>'
    body+='</div></section><section class="card"><h2>本次数据覆盖</h2><div class="grid">'
    for label,key in [('目标笔记','target_notes'),('实际取得','acquired_notes'),('成功解析','parsed_notes'),('分析样本','analyzed_notes')]:body+=f'<div>{label}<div class="metric">{esc(cov.get(key))}</div></div>'
    body+='</div><p>'+esc(cov.get('summary'))+'</p><p class="muted">资料最近取得时间：'+esc(cov.get('data_updated_at'))+'；报告生成时间：'+esc(cov.get('updated_at'))+'<br>'+esc(result['analysis_method'])+'</p></section>'
    if cov.get('test_data'):body+='<p class="warning">演示数据报告：全部样本为合成测试数据，不是真实账号结论。</p>'
    if result['status']=='insufficient':body+=f'<section class="card warning">{NO_DATA}</section>'
    body+='<nav><a href="#boss">老板先看</a><a href="#top">TOP 内容</a><a href="#research">研究矩阵</a><a href="#ideas">测试假设</a></nav>'
    body+='<section class="card" id="boss"><h2>老板先看这一页</h2><div class="grid">'
    for title,key in [('账号在做什么','一句话定位'),('主要公开产品','产品出现频率'),('主要内容打法','内容类型'),('高表现共同结构','高表现内容共同特征')]:body+=f'<div><h3>{title}</h3>{cards(sections[key][:3])}</div>'
    body+='</div><h3>今天优先测试的 10 个选题</h3><p>'+HYPOTHESIS+'</p>'+cards(hyp.get('原创测试选题',[])[:10])+'</section>'
    body+='<section class="card" id="top"><h2>TOP 内容</h2><p>'+esc(result['statistics']['notice'])+'</p><div class="grid">'
    notes={n['note_id']:n for n in result['notes']}
    for label,key,value in [('相对高表现','relative_top','score'),('可见绝对互动','absolute_top','absolute')]:
        body+='<div><h3>'+label+'</h3><div class="scroll"><table><tr><th>笔记</th><th>数值</th><th>证据</th></tr>'
        for row in result['statistics'][key]:
            n=notes[row['note_id']];body+=f'<tr><td>{esc(n.get("title"))}</td><td>{row[value]:.2f}</td><td><a href="{esc(n["url"])}" rel="noopener noreferrer" target="_blank">原文</a></td></tr>'
        body+='</table></div></div>'
    body+='</div></section><div class="grid" id="research">'
    for title,claims in sections.items():
        if title in ('一句话定位','高表现笔记'):continue
        body+=f'<section class="card"><h2>{esc(title)}</h2>'
        if title=='封面 DNA':body+=cards(claims) if claims else '<p class="muted">未完成公开封面视觉核验；不根据标题猜测视觉特征。</p>'
        elif title=='消费者需求地图':body+='<p>'+esc(result['comments_notice'])+'</p>'+cards(claims)
        else:
            body+=cards(claims[:20])
            if len(claims)>20:body+='<details><summary>查看更多</summary>'+cards(claims[20:])+'</details>'
        if title=='内容类型分布' and claims:
            maximum=max(c.get('count',0) for c in claims) or 1
            for c in claims:
                if c.get('count'):body+=f'<small>{esc(c.get("label"))} · {c["count"]}</small><div class="bar" style="width:{100*c["count"]/maximum:.1f}%"></div>'
        if title=='发布频率' and result['statistics'].get('timeline'):
            timeline=result['statistics']['timeline'];maximum=max(timeline.values())
            body+='<details><summary>查看有日期样本的分布</summary>'
            for day,number in timeline.items():body+=f'<small>{esc(day)} · {number}篇</small><div class="bar" style="width:{100*number/maximum:.1f}%"></div>'
            body+='</details>'
        if title=='内容 × 产品' and result['statistics'].get('content_product_matrix'):
            body+='<div class="scroll"><table><tr><th>内容类型</th><th>公开产品提及</th><th>篇数</th><th>相对指数中位数</th></tr>'
            for row in result['statistics']['content_product_matrix']:body+=f'<tr><td>{esc(row["category"])}</td><td>{esc(row["product"])}</td><td>{row["note_count"]}</td><td>{esc(round(row["median_score"],2) if row["median_score"] is not None else None)}</td></tr>'
            body+='</table></div>'
        body+='</section>'
    body+='</div><section class="card" id="ideas"><h2>可测试方向</h2><p>'+HYPOTHESIS+'；不保证互动、销量或转化。</p>'
    for name,items in hyp.items():
        if name!='label':body+='<details><summary>'+esc(name)+f'（{len(items)}）</summary>'+cards(items)+'</details>'
    if not hyp:body+='<p>产品证据不足，暂不生成产品测试假设。</p>'
    body+='</section>'
    template=(Path(__file__).resolve().parents[1]/'templates/dashboard.html').read_text(encoding='utf-8')
    (output/'report.html').write_text(template.replace('__TITLE__',esc(result['title'])).replace('__BODY__',body),encoding='utf-8')
    md=['# '+result['title'],'','## 本次数据覆盖',cov.get('summary',''),f'目标 {cov["target_notes"]}；实际取得 {cov["acquired_notes"]}；成功解析 {cov["parsed_notes"]}；分析 {cov["analyzed_notes"]}。',result['statistics']['notice']]
    if cov.get('test_data'):md+=['**合成测试数据，非真实账号结论。**']
    if result['status']=='insufficient':md+=[NO_DATA]
    md+=['','## 老板先看这一页']
    for key in ['一句话定位','产品出现频率','内容类型','高表现内容共同特征']:
        md+=['### '+key]+[labels[c['claim_type']]+c['claim'] for c in sections[key][:3]]
    for key,items in sections.items():
        md+=['','## '+key]
        if not items:md+=[MISSING]
        for c in items:md+=[labels[c['claim_type']]+c['claim']+' '+ ' '.join(f'[证据 {i}]({evidence[i]["public_url"]})' for i in c['evidence_ids'])]
    md+=['',result['comments_notice'],'','## '+HYPOTHESIS]
    for key,items in hyp.items():
        if key!='label':md+=['### '+key]+[labels[c['claim_type']]+c['claim'] for c in items]
    (output/'report.md').write_text('\n\n'.join(md),encoding='utf-8')
    (output/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    for filename,rows,fields in [('notes.csv',result['notes'],['note_id','account_id','url','title','description','publish_time','likes','collects','comments_count','shares']),('products.csv',result['products'],['product_id','name','kind','price','url','evidence_ids'])]:
        dest=output/filename
        if filename=='products.csv' and not rows:
            if dest.exists():dest.unlink()
            continue
        with dest.open('w',encoding='utf-8-sig',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader()
            for row in rows:writer.writerow({k:csv_safe(row.get(k)) for k in fields})
    return output/'report.html'
