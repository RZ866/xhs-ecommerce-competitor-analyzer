"""Bounded anonymous image reads sharing the account request budget and cooldown."""
import base64,hashlib,urllib.request,urllib.error
from urllib.parse import urlsplit
from .transport import NoRedirect,Unavailable

def allowed(url):
    p=urlsplit(url);host=p.hostname or ''
    return p.scheme=='https' and not p.username and not p.password and p.port in (None,443) and any(host==h or host.endswith('.'+h) for h in ('xhscdn.com','xiaohongshu.com'))

def image_request(url):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(urllib.request.Request(url,headers={'User-Agent':'XHS-Public-Research/2.0 (+anonymous; no cookies)'}),timeout=20) as response:return response.status,response.read(5*1024*1024+1)
    except urllib.error.HTTPError as exc:return exc.code,b''
    except (OSError,urllib.error.URLError):raise Unavailable('media_network') from None

def fetch_cover(note,transport,fetch=image_request):
    url=note.get('cover')
    if not url or not allowed(url):return None
    resource='media:'+url;cached=transport.cache.get(resource)
    if cached:data=cached['data']
    else:
        if transport.blocked or transport.requests>=transport.budget:return None
        transport.pace();transport.requests+=1
        status,blob=fetch(url)
        transport.events.append({'url':url.split('?')[0],'status':status,'kind':'image'})
        # Persist the received bytes before interpreting the content.
        transport.cache.raw(url,status,base64.b64encode(blob).decode())
        if status in (401,403,429):transport.stop('rate_limited' if status==429 else 'restricted')
        if status!=200 or len(blob)>5*1024*1024:return None
        ext='jpg' if blob.startswith(b'\xff\xd8\xff') else 'png' if blob.startswith(b'\x89PNG\r\n\x1a\n') else 'webp' if blob[:4]==b'RIFF' and blob[8:12]==b'WEBP' else None
        if not ext:return None
        data={'content':base64.b64encode(blob).decode(),'extension':ext};transport.cache.put(resource,data)
    path=transport.cache.root/'media'/(hashlib.sha256(url.encode()).hexdigest()+'.'+data['extension']);path.parent.mkdir(exist_ok=True)
    path.write_bytes(base64.b64decode(data['content']))
    return {'note_id':note['note_id'],'local_path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'public_url':note['url']}
