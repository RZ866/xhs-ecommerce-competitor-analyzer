"""Developer-only report of the captured real restriction, no network request."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.analyze import run
from analysis.report import render

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dev',action='store_true',required=True);p.add_argument('--output',default='reports/real-smoke');a=p.parse_args()
    observed=json.loads((ROOT/'references/real-smoke.json').read_text(encoding='utf-8'))
    response=run(observed['url'],a.output,Path(a.output)/'.state',fetch=lambda u:(observed['status'],'',observed['location']))
    result=response['result'];result['coverage'].update(requests=observed['requests'],elapsed_seconds=observed['elapsed_seconds'],new_live_requests=0,observed_at=observed['observed_at'])
    result['coverage']['summary']='本次真实匿名访问遇到登录墙，已停止；实际取得0篇笔记。本报告由当次真实访问记录离线生成，生成报告时未再次请求平台。'
    render(result,a.output)
    print('已生成真实访问受限记录报告；未新增网络请求。')
