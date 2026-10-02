from dataclasses import asdict
import re
from urllib.parse import urlencode
from .base import DataProvider
from .urls import extract
from .ssr import state,count,text,flatten
from .transport import Unavailable
from analysis.models import Account,Note

class AnonymousPublicProvider(DataProvider):
    def __init__(self,transport):
        self.transport=transport;self.pages={};self.tokens={};self.acquired=0;self.invalid=0;self.failures=[];self.sources=[]
    def resolve(self,value):
        ref=extract(value)
        return self.transport.expand(ref) if ref.route=='SHORT_LINK' else ref
    def profile(self,ref):
        if ref.entity_id not in self.pages:
            body,stamp,source=self.transport.page(ref.url,'account:'+ref.entity_id)
            self.sources.append(source)
            self.pages[ref.entity_id]=(state(body).get('user',{}),stamp)
        return self.pages[ref.entity_id]
    def account(self,ref):
        user,stamp=self.profile(ref);data=user.get('userPageData') or {};basic=data.get('basicInfo') or {}
        interactions={x.get('type'):count(x.get('count')) for x in data.get('interactions',[]) if isinstance(x,dict)}
        return Account(ref.entity_id,ref.public_url,text(basic.get('nickname')),text(basic.get('desc')),text(basic.get('images')),interactions.get('fans'),interactions.get('follows'),interactions.get('interaction'),None,stamp)
    def normalize(self,data,ref_id,stamp,note_id=None):
        user=data.get('user') or {};identity=text(data.get('noteId')) or note_id
        if user.get('userId') and user['userId']!=ref_id:raise ValueError('author_mismatch')
        if not isinstance(identity,str) or not re.fullmatch('[a-fA-F0-9]{24}',identity):raise ValueError('identity')
        metrics=data.get('interactInfo') or {};cover=data.get('cover') or {}
        images=[x.get('urlDefault') for x in data.get('imageList',[]) if isinstance(x,dict) and text(x.get('urlDefault'))]
        return Note(identity,ref_id,'https://www.xiaohongshu.com/explore/'+identity,
            text(data.get('title')) or text(data.get('displayTitle')),text(data.get('desc')),count(data.get('time')),text(data.get('type')),
            text(cover.get('urlDefault')) or (images[0] if images else None),images,
            count(metrics.get('likedCount')),count(metrics.get('collectedCount')),count(metrics.get('commentCount')),count(metrics.get('shareCount')),
            text(user.get('nickname')) or text(user.get('nickName')),stamp,
            {k:v for k,v in metrics.items() if k in ('likedCount','collectedCount','commentCount','shareCount')})
    def notes(self,ref,limit):
        user,stamp=self.profile(ref);result=[];seen=set()
        for item in flatten(user.get('notes',[])):
            if len(result)>=limit:break
            identity=item.get('id') or (item.get('noteCard') or {}).get('noteId')
            if identity in seen:continue
            if identity:seen.add(identity)
            self.acquired+=1
            try:
                note=self.normalize(item.get('noteCard') or {},ref.entity_id,stamp,identity)
                self.tokens[note.note_id]=text(item.get('xsecToken'));result.append(note)
            except (ValueError,TypeError,AttributeError):self.invalid+=1
        return result
    def detail(self,note):
        url=note.url
        if self.tokens.get(note.note_id):url+='?'+urlencode({'xsec_token':self.tokens[note.note_id],'xsec_source':'pc_user'})
        body,stamp,source=self.transport.page(url,'note:'+note.note_id);self.sources.append(source)
        data=state(body).get('note',{}).get('noteDetailMap',{}).get(note.note_id,{}).get('note')
        if not isinstance(data,dict):raise Unavailable('detail_absent')
        detail=self.normalize(data,note.account_id,stamp,note.note_id)
        if detail.note_id!=note.note_id:raise ValueError('identity_mismatch')
        merged=asdict(note)
        for key,value in asdict(detail).items():
            if value is not None and value!=[] and value!={}:merged[key]=value
        return Note(**merged)
    def products(self,ref):return []
    def comments(self,ref):return []
