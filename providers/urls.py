import re
from dataclasses import dataclass
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

HOSTS={'www.xiaohongshu.com','xiaohongshu.com','xhslink.cn','www.xhslink.cn','xhslink.com','www.xhslink.com'}
@dataclass
class Reference:
    route:str
    entity_id:str|None
    url:str
    public_url:str

def safe(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.username or p.password or p.port not in (None,443):raise ValueError('unsafe_url')
    return p

def parse(url):
    p=safe(url)
    if p.hostname.endswith(('xhslink.cn','xhslink.com')):return Reference('SHORT_LINK',None,url,urlunsplit((p.scheme,p.netloc,p.path,'','')))
    match=re.fullmatch(r'/(user/profile|explore|discovery/item)/([a-fA-F0-9]{24})/?',p.path)
    if not match:raise ValueError('unsupported_url')
    route='ACCOUNT_ANALYSIS' if match[1]=='user/profile' else 'NOTE_ANALYSIS'
    public='https://www.xiaohongshu.com/'+('user/profile/' if route=='ACCOUNT_ANALYSIS' else 'explore/')+match[2].lower()
    query=urlencode([(k,v) for k,v in parse_qsl(p.query) if k in {'xsec_token','xsec_source'}])
    return Reference(route,match[2].lower(),public+('?' +query if query else ''),public)

def extract(text):
    urls=re.findall(r'https://[^\s<>"\u3000]+',text)
    refs=[]
    for url in urls:
        try:ref=parse(url.rstrip('，。；！）)]}'))
        except ValueError:continue
        if ref.public_url not in {r.public_url for r in refs}:refs.append(ref)
    if len(refs)!=1:raise ValueError('one_link_required')
    return refs[0]
