"""Explicit synthetic scenario and authored analysis fixture; never used on real data."""
from .analysis import HYPOTHESIS_LABEL

SCENES = ['租房厨房', '通勤午餐', '周末备餐', '宿舍桌面', '小户型冰箱']
PAINS = ['空间不够', '清洗麻烦', '拿取费时', '容易串味', '尺寸不合']
MODELS = ['场景问题→操作演示→边界说明', '两种方案对比→使用条件→取舍', '真实流程→分步记录→复盘', '常见误区→原因解释→替代方法', '用户提问→实测回应→使用提醒']
PRODUCTS = ['可叠放保鲜盒', '分隔午餐盒', '抽屉收纳盘']

def c(text, ids, kind='ANALYSIS', confidence=.65, tag=None):
    value = {'claim': text, 'claim_type': kind, 'confidence': confidence, 'evidence_ids': ids}
    if tag:
        value['tag'] = tag
    return value

def fixture_analysis(dataset):
    if not dataset['synthetic']:
        raise ValueError('Mock analysis requires synthetic data')
    evid = {e['evidence_id'] for e in dataset['evidence']}
    notes = {n['note_id']: n for n in dataset['notes']}
    top = dataset['top_notes']
    if not top:
        raise ValueError('Mock analysis requires available note evidence')
    rows = []
    for item in top:
        note = notes[item['note_id']]
        i = int(note['note_id'][-6:])
        j = i % 5
        ids = ['note:' + note['note_id']]
        rows.append({'note_id': note['note_id'],
                     'content_model': c(MODELS[j], ids, tag=MODELS[j]),
                     'title_structure': c('以具体使用情境提出选择问题，让读者预判内容用途。', ids),
                     'body_structure': c('先描述限制，再展示使用过程，最后说明不适合的情形。', ids),
                     'scenes': c(SCENES[j], ids, tag=SCENES[j]),
                     'pain_points': c(PAINS[j], ids, tag=PAINS[j]),
                     'selling_points': c('文中强调便于分类与取放；这属于内容表达，尚非产品性能验证。', ids, tag='分类与取放'),
                     'visual': None})
    first_ids = ['note:' + r['note_id'] for r in top[:3]]
    needs = []
    for j, pain in enumerate(PAINS):
        selected = [comment for comment in dataset['comments'] if pain in (comment['text'] or '')]
        if selected:
            needs.append(c(f'评论样本出现“{pain}”相关表达，可进一步测试这一使用阻碍；不能外推为全市场需求。',
                           ['comment:' + x['comment_id'] for x in selected[:5]], tag=pain))
    hypotheses = {}
    def h(text, ids=first_ids):
        return {**c(text, ids, 'INFERENCE', .4), 'label': HYPOTHESIS_LABEL}
    hypotheses['products'] = [h(f'围绕{PRODUCTS[j]}测试“{PAINS[j]}”的解决方式：先比较用户提问与收藏反馈，再验证实际使用体验；不预估销量。',
                                ['product:mock-p' + str(j), first_ids[j % len(first_ids)]]) for j in range(3)]
    hypotheses['content_models'] = [h(f'测试模型：{model}；同一商品固定主题，只改变叙事顺序，比较账号自身互动。') for model in MODELS]
    title_structures = ['[场景]里，[商品]怎么放才顺手？', '选[商品]前，先量这[数字]个位置', '[方案A]和[方案B]，我会按[条件]来选', '[痛点]反复出现，先检查[使用步骤]', '[人群]的[场景]整理：从[小区域]开始', '用了[时长]后，[商品]最想改的是哪一点', '别只看[外观]：[商品]还要检查[参数]', '[预算]以内，先解决[具体问题]', '你问的[顾虑]，这次用[操作]验证', '同样的[空间]，换个[摆放方式]会怎样']
    hypotheses['titles'] = [h('原创标题结构：' + title) for title in title_structures]
    covers = ['左右分屏呈现两种摆放方式，标注相同尺寸与条件', '俯拍完整使用场景，用一处箭头指向关键障碍', '商品特写搭配尺寸标尺，文字只保留一个选择问题', '三帧连续动作说明取放步骤，统一背景与拍摄距离', '用户问题作为短标题，下方放对应验证过程画面']
    hypotheses['covers'] = [h('封面测试结构：' + cover + '；当前未获取竞品图片，此为文本证据启发的创意假设。') for cover in covers]
    angles = ['尺寸测量清单', '清洗流程记录', '满载与空载取放对比', '不同摆放方向实测', '一周使用后问题复盘', '不适合人群说明']
    hypotheses['topics'] = [h(f'{scene}的{PRODUCTS[j % 3]}：用“{angle}”检验{PAINS[j]}是否改善；记录失败条件。',
                               ['note:' + next((r['note_id'] for r in rows if r['scenes']['tag'] == scene), top[0]['note_id'])])
                             for j, scene in enumerate(SCENES) for angle in angles]
    return {'dataset_digest': dataset['dataset_digest'], 'source': 'synthetic-fixture',
            'positioning': c('样本内容围绕有限空间的日常收纳，用场景演示解释商品选择与使用取舍。', first_ids),
            'note_analyses': rows, 'needs': needs, 'matrix': [], 'hypotheses': hypotheses}
