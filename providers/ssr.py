"""Read JSON state only; never evaluate page JavaScript."""
import json,re

def state(html):
    match=re.search(r'window\.__INITIAL_STATE__\s*=\s*',html)
    if not match:raise ValueError('state_absent')
    text=html[match.end():];depth=0;quoted=False;escape=False;end=None
    for i,c in enumerate(text):
        if quoted:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in '[{':depth+=1
        elif c in ']}':
            depth-=1
            if depth==0:end=i+1;break
    if end is None:raise ValueError('state_invalid')
    # Tokenize strings so literal words inside titles remain unchanged.
    parts=re.split(r'("(?:\\.|[^"\\])*")',text[:end])
    for i in range(0,len(parts),2):parts[i]=re.sub(r'\b(?:undefined|NaN)\b','null',parts[i])
    result=json.loads(''.join(parts))
    if not isinstance(result,dict):raise ValueError('state_type')
    return result

def count(value):
    if type(value) is int:return value if value>=0 else None
    if isinstance(value,str) and re.fullmatch(r'\d[\d,]*',value.strip()):return int(value.replace(',',''))
    # Rounded display counts (e.g. 1.2万) are not exact integers.
    return None

def text(value):return value if isinstance(value,str) and value else None

def flatten(value):
    if isinstance(value,list):
        for item in value:yield from flatten(item)
    elif isinstance(value,dict):yield value
