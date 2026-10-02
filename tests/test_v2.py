import unittest,tempfile,json,sys,hashlib
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from providers.urls import parse,extract
from providers.ssr import state,count
from providers.cache import Cache,RunLock
from providers.transport import PublicTransport,Unavailable
from providers.anonymous import AnonymousPublicProvider
from analysis.models import Note,Claim
from analysis.scoring import score
from analysis.report import render,csv_safe
from analysis.validation import validate,finalize,FORBIDDEN
from providers.media import fetch_cover,allowed
from scripts.analyze import run
from tests.fixtures.public_pages import *

class V2Tests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def execute(self,**kwargs):return run(URL,self.root/'report',self.root/'state',fetch=fetcher(**kwargs),dev=True)
    def test_profile_route(self):self.assertEqual(parse(URL).route,'ACCOUNT_ANALYSIS')
    def test_note_route(self):self.assertEqual(parse(URL.replace('user/profile','explore')).route,'NOTE_ANALYSIS')
    def test_natural_url(self):self.assertEqual(extract('拆解这个账号：'+URL+'。').entity_id,ACCOUNT)
    def test_unsafe_urls(self):
        for url in ['http://www.xiaohongshu.com/user/profile/'+ACCOUNT,'https://localhost/','https://www.xiaohongshu.com.evil.com/','https://a@www.xiaohongshu.com/','https://www.xiaohongshu.com:444/']:
            with self.subTest(url=url),self.assertRaises(ValueError):parse(url)
    def test_multiple_urls(self):
        with self.assertRaises(ValueError):extract(URL+' '+URL[:-1]+'2')
    def test_tokens_private(self):
        ref=parse(URL+'?xsec_token=synthetic&other=discard');self.assertNotIn('token',ref.public_url);self.assertNotIn('other',ref.url)
    def test_short_redirect(self):
        transport=PublicTransport(Cache(self.root),fetch=lambda u:(302,'',URL),sleep=lambda _:None)
        self.assertEqual(transport.expand(parse('https://xhslink.cn/test')).entity_id,ACCOUNT)
        self.assertEqual(transport.requests,1)
        transport.expand(parse('https://xhslink.cn/test'));self.assertEqual(transport.requests,1)
    def test_short_external_denied(self):
        transport=PublicTransport(Cache(self.root),fetch=lambda u:(302,'','https://evil.com/'),sleep=lambda _:None)
        with self.assertRaises(ValueError):transport.expand(parse('https://xhslink.cn/test'))
    def test_short_loop(self):
        transport=PublicTransport(Cache(self.root),fetch=lambda u:(302,'',u),sleep=lambda _:None)
        with self.assertRaises(Unavailable):transport.expand(parse('https://xhslink.cn/test'))
        self.assertEqual(transport.requests,1)
    def test_safe_state(self):self.assertEqual(state('window.__INITIAL_STATE__={"a":undefined,"b":"NaN } undefined"};evil()'),{'a':None,'b':'NaN } undefined'})
    def test_state_not_executed(self):
        with self.assertRaises(ValueError):state('window.__INITIAL_STATE__={"a":evil()}')
    def test_count_null(self):
        for value in [None,True,-1,'1.2万','100+','unknown',2.5]:self.assertIsNone(count(value))
    def test_count_zero(self):self.assertEqual(count('0'),0)
    def test_schema_negative(self):
        with self.assertRaises(ValueError):Note('n','a',URL,likes=-1)
    def test_schema_boolean(self):
        with self.assertRaises(ValueError):Note('n','a',URL,likes=True)
    def test_claim_type(self):
        with self.assertRaises(ValueError):Claim('x','GUESS',.5,['n'])
    def test_claim_missing_evidence(self):
        with self.assertRaises(ValueError):Claim('x','FACT',.5,[])
    def test_claim_nan(self):
        with self.assertRaises(ValueError):Claim('x','FACT',float('nan'),['n'])
    def test_score_weights(self):
        data=score([{'note_id':'a','likes':0},{'note_id':'b','likes':10}]);self.assertEqual(data['baseline']['likes'],5);self.assertEqual(data['rows'][0]['weights'],{'likes':1.0});self.assertEqual(data['relative_top'][0]['note_id'],'b')
    def test_score_missing(self):self.assertIsNone(score([{'note_id':'a'}])['rows'][0]['score'])
    def test_score_zero_baseline(self):self.assertEqual(score([{'note_id':'a','likes':0}])['rows'][0]['score'],1)
    def test_score_dynamic(self):self.assertAlmostEqual(score([{'note_id':'a','likes':1,'comments_count':2}])['rows'][0]['weights']['likes'],2/3)
    def test_cache_expiry(self):
        c=Cache(self.root,ttl=10,clock=lambda:100);c.put('x',{'ok':1},stamp=80);self.assertIsNone(c.get('x'));self.assertEqual(c.get('x',stale=True)['data'],{'ok':1})
    def test_cache_corruption(self):
        c=Cache(self.root);c.put('x',{});next((self.root/'entries').iterdir()).write_text('broken');self.assertIsNone(c.get('x'))
    def test_lock(self):
        with RunLock(self.root):
            with self.assertRaises(FileExistsError):
                with RunLock(self.root):pass
        self.assertFalse((self.root/'active.lock').exists())
    def test_restrictions_stop(self):
        for status in [403,429]:
            with self.subTest(status=status):
                t=PublicTransport(Cache(self.root/str(status)),fetch=lambda u:(status,'',''),sleep=lambda _:None)
                for _ in range(2):
                    with self.assertRaises(Unavailable):t.one(URL)
                self.assertEqual(t.requests,1)
    def test_login_wall(self):
        t=PublicTransport(Cache(self.root),fetch=lambda u:(302,'','/login'),sleep=lambda _:None)
        with self.assertRaises(Unavailable):t.one(URL)
        self.assertEqual(t.blocked,'login_wall')
    def test_cooldown_persists(self):
        c=Cache(self.root);c.cooldown('restricted');t=PublicTransport(c,fetch=lambda u:self.fail('request'))
        with self.assertRaises(Unavailable):t.one(URL)
        self.assertEqual(t.requests,0)
    def test_request_budget(self):
        t=PublicTransport(Cache(self.root),budget=0,fetch=lambda u:self.fail('request'))
        with self.assertRaises(Unavailable):t.one(URL)
    def test_adapter_missing(self):
        p=AnonymousPublicProvider(PublicTransport(Cache(self.root),fetch=fetcher(missing=True),sleep=lambda _:None));ref=parse(URL)
        self.assertIsNone(p.account(ref).followers);self.assertIsNone(p.notes(ref,1)[0].likes)
    def test_author_mismatch(self):
        p=AnonymousPublicProvider(None)
        with self.assertRaises(ValueError):p.normalize({'noteId':'n','user':{'userId':'other'}},ACCOUNT,1)
    def test_integration_normal(self):
        r=self.execute()['result'];self.assertEqual(len(r['notes']),24);self.assertEqual(len(r['hypotheses']['原创测试选题']),30);self.assertEqual(r['coverage']['requests'],21);validate(r)
    def test_integration_missing(self):
        r=self.execute(missing=True)['result'];self.assertEqual(r['statistics']['relative_top'],[]);self.assertIsNone(r['account']['followers'])
    def test_integration_partial_failure(self):
        r=self.execute(failure=500)['result'];self.assertEqual(len(r['notes']),24);self.assertEqual(r['products'],[])
    def test_integration_rate_limit(self):
        r=self.execute(failure=429)['result'];self.assertEqual(r['coverage']['requests'],2);self.assertEqual(len(r['notes']),24);self.assertTrue(r['coverage']['rate_limited'])
    def test_integration_login(self):
        r=run(URL,self.root/'r',self.root/'s',fetch=lambda u:(302,'','/login'))['result'];self.assertEqual(r['coverage']['requests'],1);self.assertEqual(r['notes'],[]);self.assertEqual(r['status'],'insufficient')
    def test_no_products(self):
        r=self.execute(product=False)['result'];self.assertEqual(r['products'],[]);self.assertFalse((self.root/'report/products.csv').exists());self.assertEqual(r['hypotheses'],{})
    def test_no_comments(self):self.assertIn('未获取到评论正文',self.execute()['result']['comments_notice'])
    def test_cache_rerun(self):
        self.execute();r=self.execute()['result'];self.assertEqual(r['coverage']['requests'],0)
    def test_deep_target(self):
        r=run('深度拆解 '+URL,self.root/'r',self.root/'s',fetch=fetcher(60),dev=True)['result'];self.assertEqual(r['coverage']['target_notes'],100);self.assertEqual(len(r['notes']),60);self.assertEqual(r['coverage']['requests'],41)
    def test_evidence_rejected(self):
        r=self.execute()['result'];r['sections']['标题 DNA'][0]['evidence_ids']=['invented']
        with self.assertRaises(ValueError):validate(r)
    def test_semantic_fact_rejected(self):
        r=self.execute()['result'];digest=hashlib.sha256(json.dumps(r['notes'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        with self.assertRaises(ValueError):finalize(r,{'data_digest':digest,'sections':{'标题 DNA':[{'claim_type':'FACT'}]}})
    def test_semantic_stale(self):
        with self.assertRaises(ValueError):finalize(self.execute()['result'],{'data_digest':'old'})
    def test_html_self_contained(self):
        self.execute();html=(self.root/'report/report.html').read_text(encoding='utf-8');self.assertIn('<style>',html);self.assertNotIn('<script src=',html);self.assertNotIn('<link ',html);self.assertNotIn('__BODY__',html);self.assertIn('查看证据',html)
    def test_html_escaping(self):
        r=self.execute()['result'];r['title']='<script>alert(1)</script>';render(r,self.root/'safe');self.assertIn('&lt;script&gt;', (self.root/'safe/report.html').read_text(encoding='utf-8'))
    def test_csv_injection(self):self.assertEqual(csv_safe('=1+1'),"'=1+1")
    def test_user_outputs_acceptance(self):
        self.execute()
        for name in ['report.html','report.md']:
            content=(self.root/'report'/name).read_text(encoding='utf-8')
            for term in FORBIDDEN:self.assertNotIn(term,content)
    def test_user_numbers_not_facts(self):
        r=run('粉丝2767 '+URL,self.root/'r',self.root/'s',fetch=fetcher(missing=True),dev=True)['result'];self.assertIsNone(r['account']['followers']);self.assertNotIn('2767',json.dumps(r,ensure_ascii=False))
    def test_note_not_account(self):
        r=run(URL.replace('user/profile','explore'),self.root/'r',self.root/'s',fetch=lambda u:self.fail('network'));self.assertEqual(r['status'],'unsupported')
    def test_media_hosts(self):
        self.assertTrue(allowed('https://sns-webpic-qc.xhscdn.com/a'))
        for url in ['https://xhscdn.com.evil.com/a','http://xhscdn.com/a','https://localhost/a']:self.assertFalse(allowed(url))
    def test_media_binary_cache(self):
        t=PublicTransport(Cache(self.root),sleep=lambda _:None);note={'note_id':'n','cover':'https://xhscdn.com/a','url':URL};blob=b'\x89PNG\r\n\x1a\nsynthetic'
        image=fetch_cover(note,t,fetch=lambda u:(200,blob));self.assertTrue(Path(image['local_path']).is_file());self.assertEqual(t.requests,1)
        fetch_cover(note,t,fetch=lambda u:self.fail('repeat'));self.assertEqual(t.requests,1)
    def test_media_svg_rejected(self):
        t=PublicTransport(Cache(self.root),sleep=lambda _:None);self.assertIsNone(fetch_cover({'note_id':'n','cover':'https://xhscdn.com/a','url':URL},t,lambda u:(200,b'<svg/>')))
    def test_media_stop_after_block(self):
        t=PublicTransport(Cache(self.root),sleep=lambda _:None);t.blocked='restricted'
        self.assertIsNone(fetch_cover({'cover':'https://xhscdn.com/a'},t,lambda u:self.fail('network')))
    def test_media_restriction_shared(self):
        t=PublicTransport(Cache(self.root),sleep=lambda _:None)
        with self.assertRaises(Unavailable):fetch_cover({'cover':'https://xhscdn.com/a'},t,lambda u:(429,b''))
        with self.assertRaises(Unavailable):t.one(URL)
        self.assertEqual(t.requests,1)
    def test_raw_before_failure(self):
        r=run(URL,self.root/'r',self.root/'s',fetch=lambda u:(200,'not parseable',''))
        self.assertEqual(len(list((self.root/'s/raw').iterdir())),1);self.assertEqual(r['status'],'insufficient')
    def test_semantic_valid(self):
        r=self.execute()['result'];digest=hashlib.sha256(json.dumps(r['notes'],ensure_ascii=False,sort_keys=True).encode()).hexdigest();identity=r['notes'][0]['note_id']
        result=finalize(r,{'data_digest':digest,'sections':{'标题 DNA':[{'claim':'标题呈现时间与疑问线索','claim_type':'ANALYSIS','confidence':.6,'evidence_ids':[identity]}]}})
        self.assertIn('宿主语义',result['analysis_method'])
    def test_semantic_product_not_observed(self):
        r=self.execute()['result'];digest=hashlib.sha256(json.dumps(r['notes'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        with self.assertRaises(ValueError):finalize(r,{'data_digest':digest,'sections':{'标题 DNA':[]},'product_mentions':[{'name':'虚构产品','evidence_ids':[r['notes'][0]['note_id']]}]})
    def test_cover_requires_inspection(self):
        r=self.execute()['result'];digest=hashlib.sha256(json.dumps(r['notes'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        with self.assertRaises(ValueError):finalize(r,{'data_digest':digest,'sections':{'封面 DNA':[{'claim':'封面大字','claim_type':'ANALYSIS','confidence':.6,'evidence_ids':[r['notes'][0]['note_id']]}]}})
    def test_stale_cache_on_restriction(self):
        c=Cache(self.root,ttl=1,clock=lambda:100);c.put('account',{'body':'old'},stamp=1)
        t=PublicTransport(c,fetch=lambda u:(403,'',''),sleep=lambda _:None);self.assertEqual(t.page(URL,'account'),('old',1,'stale'));self.assertEqual(t.requests,1)
    def test_one_note_network_failure_preserves_others(self):
        base=fetcher(size=3);calls=[]
        def fetch(url):
            calls.append(url)
            if len(calls)==2:raise Unavailable('network')
            return base(url)
        r=run(URL,self.root/'r',self.root/'s',fetch=fetch,dev=True)['result'];self.assertEqual(len(r['notes']),3);self.assertEqual(sum(bool(n['description']) for n in r['notes']),2)
    def test_skill_frontmatter(self):
        content=(ROOT/'SKILL.md').read_text(encoding='utf-8');self.assertTrue(content.startswith('---\nname: xhs-ecommerce-competitor-analyzer\ndescription:'));self.assertNotIn('[TODO:',content)
    def test_schema_account_count(self):
        from analysis.models import Account
        with self.assertRaises(ValueError):Account('a',URL,followers=-1)

if __name__=='__main__':unittest.main()
