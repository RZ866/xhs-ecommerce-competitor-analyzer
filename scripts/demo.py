"""Developer-only synthetic end-to-end example."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.analyze import run
from tests.fixtures.public_pages import URL,fetcher

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dev',action='store_true',required=True);p.add_argument('--output',default='reports/demo');a=p.parse_args()
    result=run(URL,a.output,Path(a.output)/'.state',fetch=fetcher(),dev=True)
    print('合成演示报告已生成；不是真实账号分析。')
