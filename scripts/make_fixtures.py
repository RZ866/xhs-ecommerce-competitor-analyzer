"""Build our own synthetic fixtures. These are NOT TikHub response examples."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from xhs_analyzer.storage import dump
from xhs_analyzer.mock import SCENES, PAINS, PRODUCTS, MODELS

def generate(folder):
    aid = '000000000000000000000001'
    notes = []
    comments, details = {}, {}
    for i in range(105):
        nid = f'{i:024x}'
        # IDs remain valid URL entities; last digits used by analysis are decimal-safe below.
        nid = '100000000000000000' + f'{i:06d}'
        j = i % 5
        note = {'id': nid, 'author': aid, 'title': f'{SCENES[j]}如何处理{PAINS[j]}？第{i+1}次使用记录',
                'text': f'{SCENES[j]}常遇到{PAINS[j]}。这次试用{PRODUCTS[i%3]}，按“{MODELS[j]}”记录。先描述限制，再演示分类和取放过程，最后说明不适用情况。',
                'time': 1790800000 - i * 86400, 'metrics': {'likes': (i+1)*7, 'saves': (i%13)*11, 'comments': 120, 'shares': i%17},
                'link': 'https://www.xiaohongshu.com/explore/' + nid, 'product_refs': ['mock-p' + str(i%3)]}
        notes.append(note)
        details[nid] = {'ok': True, 'data': note}
        all_comments = [{'id': f'mock-c{i}-{k}', 'text': f'{PAINS[k%5]}一直困扰我，在{SCENES[j]}这样用会不会更难清洗？', 'likes': k%9} for k in range(120)]
        comments[nid] = [{'ok': True, 'data': all_comments[:60], 'more': True, 'cursor': '1'}, {'ok': True, 'data': all_comments[60:], 'more': False, 'cursor': ''}]
    raw = {'_fixture_notice': 'SYNTHETIC ONLY; not captured from TikHub',
           'account': {'ok': True, 'data': {'id': aid, 'name': '日常收纳实验室 · MOCK', 'bio': '合成演示账号：记录小空间收纳与日常使用实验。', 'followers': 12345}},
           'notes': [{'ok': True, 'data': notes[i:i+20], 'more': i+20<len(notes), 'cursor': str(i//20+1)} for i in range(0,len(notes),20)],
           'products': {'ok': True, 'data': [{'id': 'mock-p'+str(j), 'name': p, 'price': 29.9+j*10, 'currency': 'CNY'} for j,p in enumerate(PRODUCTS)], 'more': False},
           'comments': comments, 'detail': details}
    note_fields = {'note_id': 'id', 'account_id': 'author', 'title': 'title', 'body': 'text', 'published_at': 'time',
                   **{key: 'metrics.'+key for key in ('likes','saves','comments','shares')}, 'url': 'link', 'product_ids': 'product_refs'}
    def config(fields, pagination=False):
        result = {'items_path':'data','fields':fields,'success_path':'ok','success_value':True}
        if pagination:
            result['pagination'] = {'has_more_path':'more','next_params':{'cursor':'cursor'}}
        return result
    contract = {'provenance':'synthetic-fixture','validated':False,'endpoints':{
        'account': config({'account_id':'id','nickname':'name','bio':'bio','followers':'followers'}),
        'notes':config(note_fields,True), 'detail': config(note_fields),
        'comments':config({'comment_id':'id','text':'text','likes':'likes'},True),
        'products':config({'product_id':'id','name':'name','price':'price','currency':'currency'})}}
    contract['endpoints']['products']['pagination'] = {'has_more_path':'more','page_parameter':'page'}
    dump(Path(folder)/'raw.json',raw)
    dump(Path(folder)/'contract.json',contract)

if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[1]/'tests'/'fixtures')
    print('Synthetic fixtures generated (not real API samples).')
