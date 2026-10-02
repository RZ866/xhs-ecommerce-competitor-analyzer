import hashlib,json,time,os
from pathlib import Path

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');temporary.replace(path)
def key(value):return hashlib.sha256(value.encode()).hexdigest()

class Cache:
    def __init__(self,root,ttl=259200,clock=time.time):
        self.root=Path(root);self.ttl=ttl;self.clock=clock;self.hits=0;self.stale_hits=0
    def get(self,resource,stale=False):
        path=self.root/'entries'/(key(resource)+'.json')
        try:
            item=read(path)
            expired=self.clock()-item['fetched_at']>self.ttl
            if expired and not stale:return None
            self.hits+=1;self.stale_hits+=int(expired)
            return item
        except (OSError,ValueError,KeyError):return None
    def put(self,resource,data,stamp=None):
        write(self.root/'entries'/(key(resource)+'.json'),{'fetched_at':self.clock() if stamp is None else stamp,'data':data})
    def raw(self,url,status,body,location=''):
        # No auth headers or response cookies are retained. Query links remain local-only.
        path=self.root/'raw'/(str(time.time_ns())+'-'+key(url)[:10]+'.json')
        write(path,{'url':url,'status':status,'body':body,'location':location,'fetched_at':self.clock()})
        return path
    def cooldown(self,reason=None):
        path=self.root/'cooldown.json'
        if reason:write(path,{'until':self.clock()+86400,'reason':reason});return reason
        try:
            value=read(path)
            return value['reason'] if value['until']>self.clock() else None
        except (OSError,ValueError,KeyError):return None

class RunLock:
    def __init__(self,root):self.path=Path(root)/'active.lock';self.fd=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(self.fd,str(os.getpid()).encode());return self
    def __exit__(self,*args):
        if self.fd is not None:os.close(self.fd);self.path.unlink(missing_ok=True)
