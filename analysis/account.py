import re,hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from .models import claim,MISSING,COMMENT_NOTICE,HYPOTHESIS
from .scoring import score

CATEGORIES={'测评':['测评','实测','体验'],'对比':['对比','相比','区别'],'教程':['教程','步骤','怎么','如何'],'清单':['清单','合集'],'开箱':['开箱'],'案例':['案例','改造'],'价格':['价格','元','预算'],'场景':['通勤','厨房','卧室','办公室','旅行'],'痛点':['难清洗','杂乱','费时','不方便','收纳难']}
LEXICONS={'高频场景':['通勤','厨房','卧室','办公室','旅行','租房','宿舍','露营'],
 '高频痛点':['难清洗','杂乱','费时','不方便','收纳难','占空间','噪音'],
 '高频卖点':['便携','省空间','易清洗','耐用','轻便','防水','可折叠']}
DIMENSIONS=['账号基本盘','一句话定位','内容类型','发布频率','内容类型分布','高表现笔记','标题 DNA','封面 DNA','正文结构','开头 Hook','CTA','高频场景','高频痛点','高频卖点','产品出现频率','内容 × 产品','内容 × 场景','痛点 × 产品','高表现内容共同特征','内容演化趋势','消费者需求地图']

def grouping(notes,terms):
    return {term:[n['note_id'] for n in notes if term in ((n.get('title') or '')+' '+(n.get('description') or ''))] for term in terms}

def hypotheses(products,notes):
    if not products:return {}
    product=products[0];p=product['name'];ids=product['evidence_ids'];make=lambda t:claim(t,ids,'INFERENCE',.3)
    angles=['使用前先确认的条件','一次完整使用过程','与现有方案的差异','清洁维护成本','不同场景的适用边界']
    titles=[f'{p}：{{场景}}里先确认的{{数字}}件事',f'我会怎样验证{p}的{{卖点}}',f'{p}适合谁？先看{{使用条件}}',f'把{p}放进{{场景}}，记录{{观察指标}}',f'{p}与{{替代方案}}，只比较{{同一指标}}',f'选{p}前，把{{隐性成本}}算进去',f'{p}的一次完整体验：从{{起点}}到{{终点}}',f'关于{p}的{{疑问}}，用{{测试方法}}回答',f'预算{{金额}}时，怎样判断{p}是否适合',f'{p}使用后{{时长}}：哪些变化值得记录']
    return {'label':HYPOTHESIS,'产品研究方向':[make(f'研究{p}的{a}') for a in ['场景适配边界','替代方案差异','维护与使用成本']],
      '内容模型':[make(f'{p}｜{a}：展示过程、观察指标与局限') for a in angles],
      '原创标题结构':[make(t) for t in titles],
      '封面结构':[make(f'{p}：{v}；这是待拍摄设计，不是对竞品封面的观察') for v in ['产品主体＋一个待验证问题','真实场景全景＋使用位置','相同条件下的双栏对照','操作步骤三格图','细节特写＋适用边界说明']],
      '原创测试选题':[make(f'{p}｜{a}：重点记录{b}') for a in angles for b in ['准备时间','操作步骤','实际占用空间','使用限制','清洁过程','替代方案差异']]}

class AccountAnalyzer:
    def analyze(self,account,notes,coverage):
        ids=[n['note_id'] for n in notes];evidence=[]
        for n in notes:evidence.append({'evidence_id':n['note_id'],'entity_id':n['note_id'],'kind':'note','public_url':n['url'],'excerpt':((n.get('title') or '')+' '+(n.get('description') or ''))[:1200],'fields':{k:n.get(k) for k in ['likes','collects','comments_count','shares','publish_time']},'fetched_at':n.get('fetched_at'),'origin':'PUBLIC_PAGE'})
        if account and any(account.get(k) is not None for k in ['nickname','bio','followers']):evidence.append({'evidence_id':account['account_id'],'entity_id':account['account_id'],'kind':'account','public_url':account['url'],'excerpt':account.get('bio') or account.get('nickname') or '', 'fields':{k:account.get(k) for k in ['nickname','followers','follows','likes_collects']},'fetched_at':account.get('fetched_at'),'origin':'PUBLIC_PAGE'})
        sections={k:[] for k in DIMENSIONS};stats=score(notes);types={}
        for n in notes:
            content=(n.get('title') or '')+' '+(n.get('description') or '')
            types[n['note_id']]=[k for k,words in CATEGORIES.items() if any(w in content for w in words)] or ['其他文本']
        distribution={k:[i for i,v in types.items() if k in v] for k in set(t for v in types.values() for t in v)}
        for k,found in sorted(distribution.items(),key=lambda x:-len(x[1])):sections['内容类型'].append(claim(f'文本包含“{k}”相关线索的笔记 {len(found)} 篇（多标签规则初分，非人工确证）',found,confidence=.5,label=k,count=len(found)))
        sections['内容类型分布']=sections['内容类型']
        for label,words in LEXICONS.items():
            for word,found in grouping(notes,words).items():
                if found:sections[label].append(claim(f'笔记文本出现“{word}” {len(found)} 篇；反映作者表达，不等同消费者反馈',found,confidence=.65,label=word,count=len(found)))
        products=[];mentions=defaultdict(list)
        # Conservative explicit labels only. Never infer a shop catalogue from arbitrary nouns.
        for n in notes:
            for name in re.findall(r'(?:产品|商品|品名)[：:]\s*([^\n，。；;！!？?]{2,30})',(n.get('title') or '')+'\n'+(n.get('description') or '')):mentions[name.strip()].append(n['note_id'])
        for name,found in sorted(mentions.items(),key=lambda x:-len(set(x[1]))):
            found=list(dict.fromkeys(found));pid='mention-'+hashlib.sha256(name.encode()).hexdigest()[:12]
            products.append({'product_id':pid,'name':name,'evidence_ids':found,'kind':'public_text_mention','price':None,'url':None})
            sections['产品出现频率'].append(claim(f'公开文本明确标注“{name}”的笔记 {len(found)} 篇；非销量或利润排名',found,confidence=.8,label=name,count=len(found)))
        for p in products:
            for category,found in distribution.items():
                intersect=[i for i in found if i in p['evidence_ids']]
                if intersect:sections['内容 × 产品'].append(claim(f'{category} × {p["name"]}：{len(intersect)} 篇',intersect,confidence=.5))
            for pain in sections['高频痛点']:
                intersect=[i for i in pain['evidence_ids'] if i in p['evidence_ids']]
                if intersect:sections['痛点 × 产品'].append(claim(f'{pain["label"]} × {p["name"]}：{len(intersect)} 篇文本共现',intersect,confidence=.5))
        stats['content_product_matrix']=[]
        score_byid={r['note_id']:r['score'] for r in stats['rows']}
        from statistics import median
        for p in products:
            for category,found in distribution.items():
                intersect=[i for i in found if i in p['evidence_ids']]
                values=[score_byid[i] for i in intersect if score_byid.get(i) is not None]
                if intersect:stats['content_product_matrix'].append({'category':category,'product':p['name'],'note_count':len(intersect),'median_score':median(values) if values else None,'evidence_ids':intersect})
        for scene in sections['高频场景']:
            for category,found in distribution.items():
                intersect=[i for i in found if i in scene['evidence_ids']]
                if intersect:sections['内容 × 场景'].append(claim(f'{category} × {scene["label"]}：{len(intersect)} 篇',intersect,confidence=.5))
        if products and distribution:
            main=max(distribution,key=lambda k:len(distribution[k]))
            sections['一句话定位']=[claim(f'通过【{main}相关内容】，向【目标消费者未核实】介绍【{products[0]["name"]}】；销售关系未获取到公开数据',products[0]['evidence_ids'],'INFERENCE',.35)]
        for key in ['nickname','followers','follows','likes_collects']:
            if account and account.get(key) is not None and any(e['evidence_id']==account['account_id'] for e in evidence):sections['账号基本盘'].append(claim(f'{dict(nickname="账号名称",followers="粉丝",follows="关注",likes_collects="获赞与收藏")[key]}：{account[key]}',[account['account_id']],'FACT',.95))
        for row in stats['relative_top']:
            sections['高表现笔记'].append(claim(f'样本内相对表现指数 {row["score"]:.2f}；可用指标 {len(row["metrics"])} 项',[row['note_id']],confidence=.6))
        for name,pattern in {'数字':r'\d','疑问':r'[？?]|如何|怎么','对比':r'对比|区别|相比','价格':r'\d+元|预算','时间':r'小时|分钟|天|周','结果':r'效果|改善|完成'}.items():
            found=[n['note_id'] for n in notes if re.search(pattern,n.get('title') or '')]
            if found:sections['标题 DNA'].append(claim(f'标题包含{name}线索：{len(found)} 篇',found,confidence=.7))
        for n in notes:
            body=n.get('description')
            if body:
                sections['正文结构'].append(claim(f'正文可见 {len(body)} 字、{len(body.splitlines())} 行',[n['note_id']],confidence=.9))
                sections['开头 Hook'].append(claim('开头表达待结合上下文核验：“'+body.splitlines()[0][:60]+'”',[n['note_id']],'ANALYSIS',.5))
                if any(w in body for w in ['收藏','关注','评论','点击']):sections['CTA'].append(claim('正文包含互动或行动提示；不能据此判断转化',[n['note_id']],confidence=.7))
        dated=[n for n in notes if n.get('publish_time') and 946684800000<n['publish_time']<4102444800000]
        if len(dated)>=3:
            dates=[datetime.fromtimestamp(n['publish_time']/1000,timezone.utc).date() for n in dated];span=(max(dates)-min(dates)).days+1
            sections['发布频率']=[claim(f'有日期样本 {len(dated)} 篇，跨 {span} 天，样本密度 {len(dated)/span:.2f} 篇/天；非完整发文频率',[n['note_id'] for n in dated],confidence=.6)]
            stats['timeline']=dict(sorted(Counter(str(d) for d in dates).items()))
        if len(dated)>=10:
            ordered=sorted(dated,key=lambda n:n['publish_time']);half=len(ordered)//2
            for label,subset in [('较早半段',ordered[:half]),('较晚半段',ordered[half:])]:
                counts=Counter(t for n in subset for t in types[n['note_id']]);top=counts.most_common(1)[0]
                sections['内容演化趋势'].append(claim(f'{label}样本最常见文本线索：{top[0]}（{top[1]} 篇）；不足以证明策略变化',[n['note_id'] for n in subset],confidence=.45))
        high={r['note_id'] for r in stats['relative_top'][:10]}
        for category,found in distribution.items():
            shared=[i for i in found if i in high]
            if len(shared)>=2:sections['高表现内容共同特征'].append(claim(f'相对表现前 {len(high)} 篇中，{len(shared)} 篇包含{category}线索；不是因果结论',shared,confidence=.5))
        sections['消费者需求地图']=[claim('待验证需求：'+p['label']+'；来源为作者文本，不是评论反馈',p['evidence_ids'],'INFERENCE',.3) for p in sections['高频痛点']]
        return {'version':'2.0.0','title':(account.get('nickname') if account else None or '公开账号')+'｜小红书电商对标账号拆解报告' if account and account.get('nickname') else '公开账号｜小红书电商对标账号拆解报告',
          'coverage':coverage,'account':account or {},'notes':notes,'products':products,'evidence':evidence,'statistics':stats,'sections':sections,'hypotheses':hypotheses(products,notes),
          'status':'partial' if notes else 'insufficient','analysis_method':'可核验文本规则与统计；尚未经宿主语义分析','comments_notice':COMMENT_NOTICE,'user_context':{}}

class NoteAnalyzer:
    def analyze(self,*args):return {'status':'unsupported','message':'单篇笔记拆解暂未支持，请提供账号主页链接。'}
