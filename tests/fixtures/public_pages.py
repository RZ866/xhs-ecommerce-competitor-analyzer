"""Synthetic source-shaped fixtures, NOT a real account or claimed live response."""
import json
ACCOUNT='000000000000000000000001'
URL='https://www.xiaohongshu.com/user/profile/'+ACCOUNT
def page(data):return '<html><script>window.__INITIAL_STATE__='+json.dumps(data,ensure_ascii=False)+'</script></html>'
def profile(size=24,missing=False,product=True):
    cards=[]
    for i in range(size):
        identity=f'{i+100:024x}'
        cards.append({'id':identity,'noteCard':{'displayTitle':f'厨房收纳实测 {i+1} 天：怎么减少杂乱？','type':'normal','user':{'userId':ACCOUNT},'interactInfo':{} if missing else {'likedCount':str((i+1)*10)}}})
    return page({'user':{'userPageData':{'basicInfo':{'nickname':'合成演示账号','desc':'合成数据，仅用于验证'},'interactions':[] if missing else [{'type':'fans','count':'120'}]},'notes':[cards]}})
def detail(identity,missing=False,product=True):
    data={'noteId':identity,'title':'厨房收纳对比实测','desc':('产品：折叠收纳盒\n' if product else '')+'厨房杂乱怎么办？\n步骤一：整理；步骤二：对比。\n便携省空间，收藏这份清单。','time':1700000000000+int(identity,16)*86400000,'user':{'userId':ACCOUNT,'nickname':'合成演示账号'},'interactInfo':{} if missing else {'likedCount':str(int(identity,16)),'collectedCount':'20','commentCount':'0'}}
    return page({'note':{'noteDetailMap':{identity:{'note':data}}}})
def fetcher(size=24,missing=False,product=True,failure=None):
    def fetch(url):
        if '/user/profile/' in url:return 200,profile(size,missing,product),''
        if failure:return failure,'限制',''
        return 200,detail(url.split('/')[-1].split('?')[0],missing,product),''
    return fetch
