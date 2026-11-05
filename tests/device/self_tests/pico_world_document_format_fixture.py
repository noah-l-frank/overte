# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Pure ACTUAL producer formatter cases, not Node/IME/product input."""
from adapters.pico4.world_document_model import WorldDocumentModelContext1,document_transaction,document_source,document_format_bound
from adapters.script_journey.history import canonical
from adapters.pico4.assets_raw_archive import quoted_bytes

BIG=(1<<64)-1
RUN='f'*32
SUFFIX='/feature-fixture/v1/runs/'+RUN+'/'
def hostname(size,unicode=False):
    out=[]
    while size:
        take=min(63,size)
        if size>63 and size-64<1:take-=1
        out.append(('界' if unicode else 'a')*take);size-=take
        if size:out.append('.');size-=1
    return ''.join(out)
def context(kind):
    if kind=='normal':url='https://primary.invalid'+SUFFIX
    else:
        scheme='http://' if kind=='http512' else 'https://'
        url=scheme+hostname(512-len(scheme)-len(SUFFIX))+SUFFIX
    c=WorldDocumentModelContext1(RUN,url,'e'*32,'d'*32,'c'*32,'b'*32,'a'*32,'ffffffff-ffff-ffff-ffff-ffffffffffff','9'*32)
    c.validate();return c

def authority(c):
    base=dict(handle='1',creation=BIG,grant=BIG,page=BIG,url=c.url,sourceUrl=c.url)
    native=dict(base,itemInstance=c.item,sourceIdentity='web-entity:'+c.entity,created=True,authorized=True,
        sessionActive=True,suspended=False,loading=False,capturedEpochMs=BIG,capturedMonotonicMs=BIG)
    java=dict(base,ownerCurrent=True,active=True,foreground=True,windowFocused=True,destroyed=False,closing=False,
        loading=False,capturedEpochMs=BIG,capturedElapsedMs=BIG)
    return dict(native=native,java=java)

def packet(c,text):
    before=authority(c);after=authority(c)
    finish=dict(handle='1',creation=BIG,grant=BIG,page=BIG,url=c.url,finishedEpochMs=BIG)
    dom=dict(webDOMVersion=1,requestId='8'*32,instance=c.dom,sequence=BIG,capturedEpochMs=BIG,
        document=dict(runId=c.run,href=c.url,responseId=c.response,readyState='complete'),
        editor=dict(text=text,focused=True),attempts=[],echoes=[])
    # Exact two functions called by ACTUAL WorldDocumentFileModel.send. This
    # does not duplicate its nested JSON quoting or use a fake warm owner.
    transaction=document_transaction(before,dom,after)
    source=document_source(before,after,finish,dom,transaction)
    return dict(picoWorldCurrentDocumentVersion=1,commandId='8'*32,runId=c.run,ownerToken=c.owner,
        instance=c.instance,sequence=BIG,processId=BIG,requestedEpochMs=BIG,requestedMonotonicMs=BIG,
        capturedEpochMs=BIG,capturedMonotonicMs=BIG,status='ready',source=source)

def pure_actual_document_format_bounds(_artifacts=None):
    mix=''
    while len((mix+'\\"漢🌍').encode('utf-16-le'))//2<=512:mix+='\\"漢🌍'
    while len(mix.encode('utf-16-le'))//2<512:mix+='漢'
    strings={'empty':'','ascii':'x'*512,'quote':'"'*512,'backslash':'\\'*512,
        'bmp':'漢'*512,'astral':'🌍'*256,'separator':'\u2028'*512,'mixed':mix}
    rows=[];old_understates=False
    for kind in ('normal','ascii512','http512'):
        c=context(kind);bound=document_format_bound(c);base=len(canonical(packet(c,'')))+1
        if kind!='normal':assert len(c.fixture_url)==512
        for name,text in strings.items():
            units=len(text.encode('utf-16-le'))//2;assert units<=512
            raw=canonical(packet(c,text))+b'\n'
            assert len(raw)<=bound<=65536,(kind,name,len(raw),bound)
            delta=len(raw)-base
            assert delta<=20*units,(kind,name,delta,units)
            old_understates|=delta>16*units
            rows.append(dict(context=kind,textDomain=name,utf16Units=units,actualWireBytes=len(raw),
                sourceFormatBound=bound,textWireDelta=delta,quotedUrl=quoted_bytes(c.url)))
    assert len(rows)==24 and old_understates
    return dict(green=True,cases=24,actualProducerFormatter=True,old16CoefficientUnderstates=True,
        correctedCoefficient=20,rows=rows,owners=0,sourceSDK=0,productInputs=0,nativeQualified=False)
