import time,urllib.request,urllib.error
from urllib.parse import urljoin,urlsplit
from .urls import safe,parse
from .cache import read,write

class Unavailable(Exception):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def request(url,timeout=25):
    # Explicitly disables proxy environment and cookie persistence. No browser access.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    req=urllib.request.Request(url,headers={'User-Agent':'XHS-Public-Research/2.0 (+anonymous; no cookies)','Accept':'text/html'})
    try:response=opener.open(req,timeout=timeout)
    except urllib.error.HTTPError as exc:response=exc
    except (urllib.error.URLError,OSError,TimeoutError):raise Unavailable('network') from None
    with response:
        blob=response.read(8*1024*1024+1)
        if len(blob)>8*1024*1024:raise Unavailable('size')
        return response.status,blob.decode('utf-8',errors='replace'),response.headers.get('Location','')

class PublicTransport:
    def __init__(self,cache,budget=26,interval=3,fetch=request,clock=time.time,sleep=time.sleep):
        self.cache=cache;self.budget=budget;self.interval=max(3,interval);self.fetch=fetch;self.clock=clock;self.sleep=sleep
        self.requests=0;self.blocked=cache.cooldown();self.last=0;self.events=[]
        try:self.last=read(cache.root/'last-request.json')['at']
        except (OSError,ValueError,KeyError):pass
    def pace(self):
        self.sleep(max(0,self.interval-(self.clock()-self.last)))
        self.last=self.clock();write(self.cache.root/'last-request.json',{'at':self.last})
    def stop(self,reason):
        self.blocked=reason;self.cache.cooldown(reason);raise Unavailable(reason)
    def one(self,url):
        safe(url)
        if self.blocked:raise Unavailable(self.blocked)
        if self.requests>=self.budget:raise Unavailable('budget')
        self.pace();self.requests+=1
        try:status,body,location=self.fetch(url)
        except Unavailable as exc:
            self.events.append({'url':url.split('?')[0],'status':None,'reason':exc.reason});raise
        self.cache.raw(url,status,body,location)
        self.events.append({'url':url.split('?')[0],'status':status})
        if status in (401,403,429):self.stop('rate_limited' if status==429 else 'restricted')
        target=urljoin(url,location) if location else ''
        if target and any(s in urlsplit(target).path.lower() for s in ('login','captcha','verify','security')):self.stop('login_wall')
        lower=body.lower()
        if 'window.__initial_state__' not in lower and any(s in lower for s in ('验证码','访问频繁','请登录','扫码登录','captcha','rate limited','anti-bot','needs cookie')):self.stop('restricted')
        return status,body,target
    def page(self,url,resource):
        cached=self.cache.get(resource)
        if cached:return cached['data']['body'],cached['fetched_at'],'cached'
        try:
            status,body,target=self.one(url)
            if 300<=status<400:self.stop('restricted')
            if status>=400:raise Unavailable('unavailable')
            stamp=self.clock();self.cache.put(resource,{'body':body},stamp)
            return body,stamp,'new'
        except Unavailable:
            old=self.cache.get(resource,stale=True)
            if old:return old['data']['body'],old['fetched_at'],'stale'
            raise
    def expand(self,ref):
        cached=self.cache.get('short:'+ref.public_url,stale=True)
        if cached:return parse(cached['data'])
        url=ref.url;seen=set()
        for _ in range(6):
            if url in seen:raise Unavailable('redirect_loop')
            seen.add(url)
            current=parse(url)
            if current.route!='SHORT_LINK':
                self.cache.put('short:'+ref.public_url,current.url);return current
            status,body,target=self.one(url)
            if status not in (301,302,303,307,308) or not target:raise Unavailable('short_unavailable')
            safe(target);url=target
        raise Unavailable('redirect_limit')
