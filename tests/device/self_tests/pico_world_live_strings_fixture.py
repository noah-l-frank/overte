"""New exact immutable extent/resource counters; no Source/Owner/SDK."""
import gc,sys
from adapters.normal_ui import NativeUIError
from adapters.pico4.world_live_strings import WorldLiveStrings1,nodes,CAPACITY,DEPTH
from adapters.pico4.lifecycle_namespace_bill import canonical_size

def old(value):
    if type(value) is bytes:return len(value)+256
    if type(value) is tuple:return 64+8*len(value)+sum(old(v) for v in value)
    return 4*canonical_size(value,16777216)+256*nodes(value)

def pure_live_strings(_artifacts):
    cases=[]
    v={'a':None,'b':True,'c':3,'d':1.25,'unicode':'Grüße 🌍 漢字'}
    assert WorldLiveStrings1().size(v)==old(v);cases.append('no-alias-old-exact-charge')
    text=('raw-payload-🌍'*128).encode().decode();value=[text,text];c=WorldLiveStrings1()
    assert c.size(value)==old(value)-4*canonical_size(text,16777216) and c.hits==1
    assert c.originals[id(text)] is text;cases.append('same-exact-object-data-once-full-ref-meta')
    left=text.encode().decode();right=text.encode().decode();assert left is not right and left==right
    c=WorldLiveStrings1();assert c.size([left,right])==old([left,right]) and c.hits==0;cases.append('equal-new-objects-both-full')
    c=WorldLiveStrings1();c.size(left);key=id(left);del left;gc.collect()
    assert type(c.originals[key]) is str and c.originals[key]==text;cases.append('actual-strong-reference-prevents-id-reuse')
    values=[('raw-%04d-payload'%i).encode().decode() for i in range(CAPACITY+2)];values.append(values[-1]);c=WorldLiveStrings1()
    assert c.size(values)==old(values) and len(c.originals)==CAPACITY and c.hits==0 and c.fallbacks>=3
    scratch=sys.getsizeof(c)+sys.getsizeof(vars(c))+sys.getsizeof(c.originals)+sum(sys.getsizeof(k) for k in c.originals)+sys.getsizeof(c.active)+16*1024+4096
    assert scratch<=196608;cases.append('bounded1024-strong-map-full-charge-fallback-and-window')
    v='deep';
    for _ in range(DEPTH+5):v=[v]
    c=WorldLiveStrings1();assert c.size(v)==old(v) and c.fallbacks>=1;cases.append('deep-valid-old-full-fallback-no-new-grammar-cap')
    value=(b'\x00\xff',{'raw':'literal'},['x',None]);assert WorldLiveStrings1().size(value)==old(value);cases.append('actual-tuple-bytes-legacy-bill')
    cycle=[];cycle.append(cycle);refused=False
    try:WorldLiveStrings1().size(cycle)
    except NativeUIError:refused=True
    assert refused;cases.append('original-cycle-refusal')
    return dict(cases=cases,count=len(cases),cacheCapacity=CAPACITY,depthCacheCutoff=DEPTH,
        actualScratchBytes=scratch,existingWindow=196608,dataOnly=True,owners=0,sourceSDK=0,
        nativeQualified=False,wholeClaim=False)
