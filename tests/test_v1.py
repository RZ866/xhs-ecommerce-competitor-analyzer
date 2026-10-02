import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from html.parser import HTMLParser
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from xhs_analyzer.models import Account, Note, Product, Comment, Claim, make_model
from xhs_analyzer.providers import TikHubProvider, FixtureClient, identity, number, validate_contract
from xhs_analyzer.storage import SnapshotStore, read, dump, redact, field_inventory, digest
from xhs_analyzer.transport import TikHubClient, ProviderError, ENDPOINTS
from xhs_analyzer.analysis import rank_notes, validate_ai, build_result, HYPOTHESIS_COUNTS
from xhs_analyzer.pipeline import collect
from xhs_analyzer.mock import fixture_analysis
from xhs_analyzer.report import render, csv_value, all_claims
from xhs_analyzer.ai import remote_analysis
from xhs_analyzer.images import fetch_cover
from analyze import main

AID = '000000000000000000000001'
URL = 'https://www.xiaohongshu.com/user/profile/'+AID

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = SnapshotStore(self.root/'data',namespace='synthetic-fixture')
        self.contract = read(ROOT/'tests/fixtures/contract.json')
        self.client = FixtureClient(ROOT/'tests/fixtures',self.store)
        self.provider = TikHubProvider(self.client,self.contract,True)
    def tearDown(self):
        self.tmp.cleanup()
    def dataset(self,**kwargs):
        return collect(self.provider,URL,self.root/'report',**kwargs)

class AdapterTests(Base):
    def test_account(self):
        a=self.provider.account(AID)
        self.assertEqual(a.followers,12345)
        self.assertIn('MOCK',a.nickname)
        self.assertTrue((self.store.root/self.provider.evidence[0].snapshot).exists())
    def test_notes_pagination_and_limit(self):
        notes=self.provider.notes(AID,100)
        self.assertEqual(len(notes),100)
        self.assertEqual(len({n.note_id for n in notes}),100)
        self.assertEqual(self.client.calls,5)
    def test_comments_paginate_truncate(self):
        note=self.provider.notes(AID,1)[0]
        comments=self.provider.comments(note.note_id,100)
        self.assertEqual(len(comments),100)
        self.assertTrue(all(c.note_id==note.note_id for c in comments))
    def test_products(self):
        self.assertEqual(len(self.provider.products(AID)),3)
    def test_missing_optional_fields_stay_none(self):
        self.contract['endpoints']['notes']['fields'].pop('likes')
        self.assertIsNone(self.provider.notes(AID,1)[0].likes)
    def test_unknown_required_field_drops_row(self):
        self.contract['endpoints']['notes']['fields']['note_id']='nonexistent'
        self.assertEqual(self.provider.notes(AID,100),[])
        self.assertTrue(self.provider.warnings)
    def test_schema_drift(self):
        self.contract['endpoints']['notes']['items_path']='missing'
        self.assertEqual(self.provider.notes(AID,100),[])
    def test_cache(self):
        self.provider.account(AID); self.provider.account(AID)
        self.assertEqual(self.client.calls,1)
    def test_live_rejects_mock_contract(self):
        with self.assertRaises(ValueError): TikHubProvider(self.client,self.contract)
    def test_counts(self):
        self.assertEqual(number('1.2万'),12000)
        self.assertEqual(number('1,234'),1234)
        with self.assertRaises(ValueError): number('点赞很多')
    def test_identity_validation(self):
        self.assertEqual(identity(URL+'?xsec_token=ignored'),AID)
        for url in ['https://evil.test/user/profile/'+AID,'http://www.xiaohongshu.com/user/profile/'+AID,'https://www.xiaohongshu.com.evil.test/user/profile/'+AID,'https://xhslink.com/a/b','https://user:pass@www.xiaohongshu.com/user/profile/'+AID]:
            with self.assertRaises(ValueError): identity(url)
    def test_repeated_cursor_terminates(self):
        original=self.client.get
        def get(kind,params):
            payload,snapshot=original(kind,params)
            payload['more']=True;payload['cursor']='1'
            return payload,snapshot
        self.client.get=get
        self.assertLessEqual(len(self.provider.notes(AID,100)),40)
        self.assertTrue(self.provider.warnings)
    def test_identity_mismatch(self):
        with self.assertRaises(ValueError): self.provider.account('f'*24)
    def test_second_page_failure_keeps_first_page(self):
        original=self.client.get
        def get(kind,params):
            if params.get('cursor'):raise ProviderError('page unavailable')
            return original(kind,params)
        self.client.get=get
        self.assertEqual(len(self.provider.notes(AID,100)),20)
        self.assertTrue(self.provider.warnings)
    def test_cache_expiration(self):
        self.provider.account(AID)
        self.store.ttl=0
        self.provider.account(AID)
        self.assertEqual(self.client.calls,2)
    def test_upstream_failure_not_cached(self):
        original=self.client.get
        def get(kind,params):
            payload,snapshot=original(kind,params)
            payload['ok']=False
            return payload,snapshot
        self.client.get=get
        with self.assertRaises(ProviderError):self.provider.account(AID)
        self.assertIsNone(self.store.get('account',{'user_id':AID}))

class SchemaTests(unittest.TestCase):
    def test_skill_metadata(self):
        from validate_skill import validate
        self.assertTrue(validate(ROOT))
    def test_valid_note(self):
        self.assertIsNone(make_model(Note,{'note_id':'n','account_id':'a'}).likes)
    def test_invalid_fields(self):
        for patch_data in [{'likes':-1},{'likes':True},{'likes':1.1},{'likes':'3'},{'url':'javascript:alert(1)'},{'product_ids':'p'},{'unknown':3}]:
            with self.assertRaises((TypeError,ValueError)): make_model(Note,{'note_id':'n','account_id':'a',**patch_data})
    def test_claim_validation(self):
        for kind,conf,ids in [('OPINION',.5,['n']),('FACT',float('nan'),['n']),('FACT',2,['n']),('FACT',.5,[])]:
            with self.assertRaises(ValueError): Claim('claim',kind,conf,ids)
    def test_price(self):
        for price in [-1,float('inf'),True]:
            with self.assertRaises(ValueError): make_model(Product,{'product_id':'p','price':price})

class ScoreTests(unittest.TestCase):
    def test_known_baseline(self):
        notes=[Note(str(i),'a',likes=v) for i,v in enumerate([10,20,30])]
        baseline,top=rank_notes(notes)
        self.assertEqual(baseline['median'],20)
        self.assertEqual(top[0]['note_id'],'2')
        self.assertAlmostEqual(top[0]['index'],147.62,places=2)
    def test_zero_baseline(self):
        b,t=rank_notes([Note('1','a',likes=0),Note('2','a',likes=0)])
        self.assertEqual(t[0]['index'],100)
    def test_missing_not_zero(self):
        notes=[Note(str(i),'a',likes=10) for i in range(4)]+[Note('x','a')]
        b,t=rank_notes(notes)
        self.assertEqual(b['excluded'],1)
        self.assertNotIn('x',[r['note_id'] for r in t])
    def test_all_missing(self):
        b,t=rank_notes([Note('x','a')]);self.assertEqual(t,[])
    def test_limit(self):
        self.assertEqual(len(rank_notes([Note(str(i),'a',likes=i) for i in range(100)],20)[1]),20)

class TransportTests(Base):
    @patch.dict(os.environ,{'TIKHUB_API_KEY':'test-only-secret-not-real'})
    def test_retry_then_cache(self):
        calls=[];sleeps=[]
        def request(*args):
            calls.append(args)
            return (429,{}) if len(calls)<3 else (200,{'code':200,'data':{}})
        client=TikHubClient(self.store,request=request,sleep=sleeps.append,clock=lambda:0)
        client.get('account',{'user_id':AID});client.get('account',{'user_id':AID})
        self.assertEqual(len(calls),3)
        self.assertTrue(sleeps)
        self.assertEqual(len(list((self.store.root/'raw').glob('*.json'))),3)
        self.assertNotIn('test-only-secret-not-real',''.join(p.read_text() for p in (self.store.root/'raw').glob('*.json')))
    @patch.dict(os.environ,{'TIKHUB_API_KEY':'test-only-secret-not-real'})
    def test_403_not_retried(self):
        client=TikHubClient(self.store,request=lambda *a:(403,{}),sleep=lambda _:None)
        with self.assertRaises(ProviderError):client.get('account',{})
        self.assertEqual(client.calls,1)
    @patch.dict(os.environ,{'TIKHUB_API_KEY':'test-only-secret-not-real'})
    def test_timeout_limited(self):
        def fail(*a): raise ProviderError('network')
        client=TikHubClient(self.store,request=fail,sleep=lambda _:None)
        with self.assertRaises(ProviderError):client.get('account',{})
        self.assertEqual(client.calls,3)
    @patch.dict(os.environ,{'TIKHUB_API_KEY':'test-only-secret-not-real'})
    def test_budget(self):
        client=TikHubClient(self.store,request=lambda *a:(500,{}),sleep=lambda _:None,max_calls=1)
        with self.assertRaises(ProviderError):client.get('account',{})
        self.assertEqual(client.calls,1)
    def test_degradation(self):
        def fail(*a):raise ProviderError('broken')
        self.provider.comments=fail;self.provider.products=fail
        data=self.dataset(notes_limit=10,deep_notes=3,comment_notes=2)
        self.assertEqual(len(data['notes']),10)
        self.assertEqual(data['comments'],[])
        self.assertTrue(data['warnings'])
    def test_total_failure_still_report(self):
        def fail(*a):raise ProviderError('broken')
        for key in ('account','notes','products','comments'):setattr(self.provider,key,fail)
        data=self.dataset()
        path=render(build_result(data),self.root/'report')
        self.assertTrue(path.exists())
        self.assertEqual(read(self.root/'report/report.json')['metadata']['ai_status'],'pending')

class AnalysisReportTests(Base):
    def test_full_chain_defaults(self):
        data=self.dataset()
        self.assertEqual([len(data[k]) for k in ('notes','top_notes','comments','products')],[100,20,1000,3])
        ai=validate_ai(fixture_analysis(data),data)
        self.assertEqual({k:len(v) for k,v in ai['hypotheses'].items()},HYPOTHESIS_COUNTS)
        path=render(build_result(data,ai),self.root/'report',data)
        page=path.read_text(encoding='utf-8')
        self.assertIn('内容 × 商品矩阵',page)
        self.assertIn('合成 MOCK 示例',page)
        self.assertIn('内部研究指标',page)
        class Inspector(HTMLParser):
            def __init__(self):super().__init__();self.ids=set();self.refs=[];self.external=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if 'id' in attrs:self.ids.add(attrs['id'])
                if attrs.get('href','').startswith('#'):self.refs.append(attrs['href'][1:])
                if tag in ('script','link','img') and any(attrs.get(k,'').startswith(('http','//')) for k in ('src','href')):self.external.append(attrs)
        parser=Inspector();parser.feed(page)
        self.assertTrue(set(parser.refs)<=parser.ids)
        self.assertEqual(parser.external,[])
        for file in ['report.md','report.json','notes.csv','products.csv','comments.csv','claims.csv']:
            self.assertTrue((self.root/'report'/file).exists())
        known={e['evidence_id'] for e in data['evidence']}
        for claim in all_claims(read(self.root/'report/report.json')):
            self.assertTrue(set(claim['evidence_ids'])<=known)
    def test_unknown_evidence_rejected(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);ai['positioning']['evidence_ids']=['fake']
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_wrong_dataset_rejected(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);ai['dataset_digest']='wrong'
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_visual_without_image_rejected(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);ai['note_analyses'][0]['visual']=ai['positioning']
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_unfounded_need_rejected(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);ai['needs']=[ai['positioning']]
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_deterministic_promise_rejected(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);ai['positioning']['claim']='保证成功'
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_synthetic_cannot_be_live(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);data['synthetic']=False
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_html_escaping(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        data['account']['nickname']='<script>alert(1)</script>'
        page=render(build_result(data),self.root/'report').read_text(encoding='utf-8')
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('&lt;script&gt;',page)
    def test_csv_formula_injection(self):
        self.assertTrue(csv_value('=HYPERLINK("bad")').startswith("'"))
    def test_boss_is_condensed(self):
        data=self.dataset(mode='boss',notes_limit=10,deep_notes=3)
        render(build_result(data,fixture_analysis(data)),self.root/'report',data)
        result=read(self.root/'report/report.json')
        self.assertNotIn('notes',result);self.assertNotIn('ai',result)
    def test_remote_model_mocked_transport(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data)
        with patch.dict(os.environ,{'AI_BASE_URL':'https://model.example/v1','AI_API_KEY':'fake','AI_MODEL':'mock'}),patch('xhs_analyzer.ai.request_json',return_value=(200,{'choices':[{'message':{'content':json.dumps(ai)}}]})):
            self.assertEqual(remote_analysis(data)['source'],'remote-model')
    def test_cli_mock(self):
        self.assertEqual(main(['run',URL,'--provider','mock','--notes-limit','10','--deep-notes','3','--out',str(self.root/'cli'),'--cache-dir',str(self.root/'cache')]),0)
    def test_cover_private_host_rejected(self):
        with self.assertRaises(ValueError):fetch_cover('https://127.0.0.1/a.png',self.root,'n')
    def test_cover_bytes_and_visual_evidence(self):
        import io
        try:from PIL import Image
        except ImportError:self.skipTest('Optional Pillow not installed')
        buf=io.BytesIO();Image.new('RGB',(120,160),'green').save(buf,format='PNG')
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return buf.getvalue()
        with patch('xhs_analyzer.images.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=Response()
            image=fetch_cover('https://sns-img.xhscdn.com/test.png',self.root,'n')
        self.assertTrue((self.root/image['path']).exists())
        self.assertEqual((image['width'],image['height']),(120,160))
        self.assertTrue(image['data_url'].startswith('data:image/png;base64,'))
    def test_analysis_missing_item_rejected(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        ai=fixture_analysis(data);ai['note_analyses'].pop()
        with self.assertRaises(ValueError):validate_ai(ai,data)
    def test_finalize(self):
        data=self.dataset(notes_limit=10,deep_notes=3)
        dump(self.root/'report/analysis.json',fixture_analysis(data))
        self.assertEqual(main(['finalize','--out',str(self.root/'report')]),0)

class ContractTests(Base):
    def test_validate_only_observed_paths(self):
        endpoints={}
        for kind in ('account','notes'):
            payload,_=self.client.get(kind,{'user_id':AID})
            # Synthetic data simulates a live transport solely for validation unit tests.
            name='samples/'+kind+'.json'
            dump(self.root/name,{'provider':'tikhub','status':200,'endpoint':ENDPOINTS[kind],'response':payload})
            endpoints[kind]={**self.contract['endpoints'][kind],'sample':name}
        draft={'provenance':'observed-live-response','endpoints':endpoints}
        certified=validate_contract(copy.deepcopy(draft),self.root)
        self.assertTrue(certified['validated'])
        TikHubProvider(self.client,certified)
        certified['endpoints']['account']['fields']['nickname']='changed'
        with self.assertRaises(ValueError):TikHubProvider(self.client,certified)
        draft['endpoints']['account']['fields']['nickname']='never.observed'
        with self.assertRaises(ValueError):validate_contract(draft,self.root)
    @patch.dict(os.environ,{'TIKHUB_API_KEY':'test-secret-value'})
    def test_redaction(self):
        value=redact({'Authorization':'Bearer test-secret-value','message':'test-secret-value','cookie':'abc'})
        self.assertNotIn('test-secret-value',json.dumps(value))
        self.assertEqual(value['cookie'],'[REDACTED]')
    def test_inventory(self):
        self.assertIn({'path':'$.data[].id','type':'str'},field_inventory({'data':[{'id':'x'}]}))

if __name__=='__main__': unittest.main()
