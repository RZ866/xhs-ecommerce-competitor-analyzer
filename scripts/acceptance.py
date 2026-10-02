"""Offline user-contract acceptance, explicitly NOT a WorkBuddy UI test."""
import sys,tempfile,json
from pathlib import Path
from html.parser import HTMLParser
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.analyze import run
from analysis.validation import FORBIDDEN,validate
from tests.fixtures.public_pages import URL,fetcher

class Standalone(HTMLParser):
    def __init__(self):super().__init__();self.dependencies=[];self.evidence_links=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','link','iframe','img') and (a.get('src') or a.get('href')):self.dependencies.append(a)
        if tag=='a' and a.get('href','').startswith('https://www.xiaohongshu.com/'):self.evidence_links+=1

def check():
    cases={'normal':fetcher(),'missing':fetcher(missing=True),'partial':fetcher(failure=500),'restricted':fetcher(failure=403),'rate_limit':fetcher(failure=429),'login':lambda u:(302,'','/login'),'no_products':fetcher(product=False)}
    with tempfile.TemporaryDirectory() as tmp:
        for name,fetch in cases.items():
            output=Path(tmp)/name
            response=run(URL,output,output/'.state',fetch=fetch,dev=True);validate(response['result'])
            for filename in ('report.html','report.md','analysis.json','notes.csv'):
                assert (output/filename).is_file(),filename
                text=(output/filename).read_text(encoding='utf-8-sig')
                for word in FORBIDDEN:assert word.lower() not in text.lower(),(name,filename,word)
            parser=Standalone();parser.feed((output/'report.html').read_text(encoding='utf-8'));assert not parser.dependencies
            if response['result']['notes']:assert parser.evidence_links
            if name in ('login','restricted','rate_limit'):assert response['result']['coverage']['requests']<=2
            print('PASS '+name)
    print('PASS offline user-contract acceptance; WorkBuddy desktop acceptance not performed')

if __name__=='__main__':check()
