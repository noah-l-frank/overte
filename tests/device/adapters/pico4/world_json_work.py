"""HOST work projection, not a source decoder/verdict or general DTO parser.

Build no dict/list DTO. Only real CurrentDocument nested JSON-string fields
are scalar-unescaped, counted and discarded before returning integer bounds.
Original decode/validate still runs, after SAME-Root prospective admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0

VERSION=1  # Internal HOST contract; no public/native capability.
from dataclasses import dataclass
from json.decoder import scanstring
import re
import sys

MAX_WIRE=65536
LEXICAL_SLOT=64*MAX_WIRE
NUMBER=re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')
ROOT,SOURCE,TRANSACTION,DOM,ECHO_ARRAY,ECHO,OTHER,FRAME=range(8)


class WorldJsonWorkRefused(ValueError):pass


def require(value):
    if not value:raise WorldJsonWorkRefused('CurrentDocument HOST lexical work is unavailable')


@dataclass(frozen=True)
class WorldJsonWork1:
    utf8_bytes:int
    max_canonical:int
    total_nodes:int
    combined_depth:int
    streams:tuple
    decoded_data:int
    decoded_metadata:int
    lexical_slot:int=LEXICAL_SLOT

    @property
    def call_work(self):
        # Original SDK string/UTF8/reassembly windows stay live in BOTH phases. Scalar
        # scan returns only integers; no hidden strings escape on success.
        return 12*MAX_WIRE+max(52*MAX_WIRE,self.decoded_data+self.decoded_metadata)+8*4096


class _Projection:
    def __init__(self):
        self.active=[];self.nodes=0;self.maximum=0;self.depth=0
        self.streams={'outer':0,'transaction':0,'quoted-dom':0,'dom':0,'echo':0,'frame':0}
    def observe_depth(self):
        self.depth=max(self.depth,sum(scanner.depth for scanner in self.active))
    def parse(self,raw,kind):
        scanner=_Scanner(self,raw,kind);self.active.append(scanner)
        try:
            scanner.run()
            self.nodes+=scanner.nodes;self.maximum=max(self.maximum,scanner.canonical)
            self.streams[kind]+=1
        finally:
            require(self.active[-1] is scanner);self.active.pop()
    def embedded(self,kind,text):self.parse(text,kind)
    def finish(self,raw_bytes):
        require(not self.active)
        metadata=12*256*(self.nodes+1)+1024*(self.depth+1)+4096
        return WorldJsonWork1(raw_bytes,self.maximum,self.nodes,self.depth,
            tuple(self.streams.items()),48*self.maximum,metadata)


class _Scanner:
    def __init__(self,owner,raw,kind):
        require(type(raw) is str)
        size=len(raw.encode('utf-8'));require(size<=MAX_WIRE)
        self.owner,self.raw,self.kind=owner,raw,kind
        self.i=0;self.end=len(raw);self.nodes=self.canonical=self.depth=0
    def ws(self):
        while self.i<self.end and self.raw[self.i] in ' \n\r\t':self.i+=1
    def run(self):
        self.ws()
        if self.i==self.end:
            # Empty acquisition is a real receipt; original reader skips its
            # parser and may poll the SAME nonce. It is not a null verdict.
            require(self.kind=='outer');return
        state={'outer':ROOT,'transaction':TRANSACTION,'dom':DOM}.get(self.kind,OTHER)
        if self.kind=='quoted-dom' and self.raw[self.i]=='"':
            text=self.string(True);self.owner.embedded('dom',text)
        else:self.value(state)
        self.ws();require(self.i==self.end)
    def string(self,decoded=False):
        require(self.i<self.end and self.raw[self.i]=='"')
        start=self.i;self.i+=1;size=2
        while self.i<self.end:
            char=self.raw[self.i]
            if char=='"':
                self.i+=1;self.canonical+=size;self.nodes+=1
                if decoded:
                    value,at=scanstring(self.raw,start+1,True)
                    require(type(value) is str and at==self.i);return value
                return None
            if char=='\\':
                require(self.i+1<self.end);escape=self.raw[self.i+1]
                if escape=='u':
                    require(self.i+6<=self.end)
                    digits=self.raw[self.i+2:self.i+6]
                    require(all(c in '0123456789abcdefABCDEF' for c in digits))
                    unit=int(digits,16)
                    size+=2 if unit in (8,9,10,12,13,34,92) else 1 if 32<=unit<=126 else 6
                    self.i+=6;continue
                require(escape in '"\\/bfnrt');size+=1 if escape=='/' else 2
                self.i+=2;continue
            unit=ord(char);require(unit>=32)
            size+=1 if unit<=126 else 6 if unit<=65535 else 12
            self.i+=1
        require(False)
    def value(self,state):
        self.ws();require(self.i<self.end);char=self.raw[self.i]
        if char=='"':self.string();return
        if char in '{[':
            self.nodes+=1;self.canonical+=1;self.depth+=1;self.owner.observe_depth()
            self.i+=1
            if char=='{':self.object(state)
            else:self.array(state)
            self.depth-=1;return
        for literal in ('true','false','null'):
            if self.raw.startswith(literal,self.i):
                self.i+=len(literal);self.nodes+=1;self.canonical+=len(literal);return
        if char=='-' or '0'<=char<='9':
            start=self.i
            while self.i<self.end and self.raw[self.i] in '-+0123456789.eE':self.i+=1
            token=self.raw[start:self.i];require(NUMBER.fullmatch(token) is not None)
            self.nodes+=1
            # Finite binary64 shortest decimal: <=17 significant digits,
            # sign/dot/exponent markers+3 exponent digits, comfortably<=32.
            # Overflow fails original strict/grammar later; no value is made.
            self.canonical+=32 if any(c in token for c in '.eE') else len(token)
            return
        require(False)
    def object(self,state):
        self.ws()
        if self.i<self.end and self.raw[self.i]=='}':self.i+=1;self.canonical+=1;return
        while True:
            self.ws();key=self.string(state in (ROOT,SOURCE,TRANSACTION,DOM,ECHO,FRAME))
            self.ws();require(self.i<self.end and self.raw[self.i]==':')
            self.i+=1;self.canonical+=1;self.ws()
            embedded=None;child=OTHER
            if state==ROOT and key=='source':child=SOURCE
            elif state==SOURCE and key in ('domRaw','focusRaw','geometryRaw'):embedded='transaction'
            elif state==SOURCE and key=='frame':child=FRAME
            elif state==FRAME and key=='raw':embedded='frame'
            elif state==TRANSACTION and key in ('domRaw','geometryRaw'):embedded='quoted-dom'
            elif state==DOM and key=='echoes':child=ECHO_ARRAY
            elif state==ECHO and key=='message':embedded='echo'
            if embedded is not None and self.i<self.end and self.raw[self.i]=='"':
                text=self.string(True);self.owner.embedded(embedded,text)
                # Drop this scalar before visiting another source field.
                del text
            else:self.value(child)
            self.ws();require(self.i<self.end)
            punctuation=self.raw[self.i];require(punctuation in ',}')
            self.i+=1;self.canonical+=1
            if punctuation=='}':return
    def array(self,state):
        self.ws()
        if self.i<self.end and self.raw[self.i]==']':self.i+=1;self.canonical+=1;return
        while True:
            self.value(ECHO if state==ECHO_ARRAY else OTHER)
            self.ws();require(self.i<self.end)
            punctuation=self.raw[self.i];require(punctuation in ',]')
            self.i+=1;self.canonical+=1
            if punctuation==']':return


def project(raw):
    require(type(raw) is str and sys.implementation.name=='cpython'
        and sys.float_info.radix==2 and sys.float_info.mant_dig==53
        and sys.float_info.max_exp==1024 and sys.float_info.min_exp==-1021)
    size=len(raw.encode('utf-8'));require(size<=MAX_WIRE)
    owner=_Projection();owner.parse(raw,'outer')
    return owner.finish(size)
