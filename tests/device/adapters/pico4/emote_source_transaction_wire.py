"""Private proposed source-transaction wire prerequisite; no Native factory.

This component retains ONE real transport return in the existing range writer
before framing/UTF8/JSON. It does not yet replace Primary source getters, create
a Native producer, or qualify the cold Source/Parent/Common operation graph.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from copy import deepcopy
import hashlib
import re
import subprocess
from types import MappingProxyType

from adapters.native_feature_observation import exact,integer,need,number
from adapters.pico4.audio_raw_archive import AudioRawArchive,MAX_LITERAL
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.pico4.probe_originals import same_callable,strict_json
from adapters.script_journey.history import canonical

VERSION=1
WIRE_LIMIT=MAX_LITERAL
METADATA_LIMIT=16384
METADATA_OVERLAP_LIMIT=METADATA_LIMIT+8192
SIDE_LIMIT=4*WIRE_LIMIT+METADATA_OVERLAP_LIMIT
EXISTING_SIDE_LIMIT=2*(11*48000*2*2+44)
HEADER=b'OVT_PICO_EMOTE_SOURCE_TRANSACTION_V1\n'
FOOTER=b'OVT_PICO_EMOTE_SOURCE_TRANSACTION_END_V1\n'
LABELS=('rootsBefore','script','inventory','native','rootsAfter','widgets')
LIMITS=MappingProxyType(dict(rootsBefore=16384,script=262144,inventory=262144,
    native=262144,rootsAfter=16384,widgets=262144))
OWNED=[]
UNCONFIRMED=[]


def checksum(raw):return hashlib.sha256(raw).hexdigest()


def request(value):
    exact(value,{'schemaVersion','action','commandId','runId','originalPolicySha256','parentBaselineSha256'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']=='feature-pico-emote-source-transaction')
    for key in ('commandId','runId','originalPolicySha256','parentBaselineSha256'):
        need(type(value[key]) is str and re.fullmatch('[0-9a-f]{'+str(32 if key in ('commandId','runId') else 64)+'}',value[key]))
    need(len(canonical(value))<=1024)
    return value


@dataclass(frozen=True,slots=True)
class SourceExtent:
    label:str
    offset:int
    size:int
    sha256:str


@dataclass(frozen=True,slots=True)
class SourceExtents:
    header:bytes
    records:tuple


def extents(wire,expected,*,start=0,end=None):
    """Wire framing only; no inner source JSON becomes a current observation."""
    request(expected);need(type(wire) is bytes and len(wire)<=WIRE_LIMIT)
    if end is None:end=len(wire)
    need(type(start) is int and type(end) is int and 0<=start<end<=len(wire) and wire.startswith(HEADER,start,end))
    offset=start+len(HEADER);line_end=wire.find(b'\n',offset,end)
    need(line_end>=offset and line_end-offset<=4096)
    raw_header=wire[offset:line_end];header=strict_json(raw_header.decode('utf-8'))
    exact(header,set(expected)|{'picoEmoteSourceTransactionVersion','complete','sourceCount'})
    need(type(header['picoEmoteSourceTransactionVersion']) is int and header['picoEmoteSourceTransactionVersion']==VERSION
        and header['complete'] is True and type(header['sourceCount']) is int and header['sourceCount']==6
        and all(type(header[key]) is type(value) and header[key]==value for key,value in expected.items()))
    offset=line_end+1;records=[];next_label=0;pending=0
    while next_label<len(LABELS):
        line_end=wire.find(b'\n',offset,end);need(line_end>=offset and line_end-offset<=128)
        fields=wire[offset:line_end].split(b' ');need(len(fields)==3)
        label=fields[0].decode('ascii');size_text=fields[1];digest=fields[2].decode('ascii')
        need(size_text.isdigit() and size_text==str(int(size_text)).encode('ascii')
            and re.fullmatch('[0-9a-f]{64}',digest))
        size=int(size_text);offset=line_end+1
        if label=='nativePending':
            need(LABELS[next_label]=='native' and pending<51 and integer(size,1,256));pending+=1
        else:
            need(label==LABELS[next_label] and integer(size,1,LIMITS[label]));next_label+=1
        need(offset+size<end and wire[offset+size:offset+size+1]==b'\n')
        # A bounded memoryview hashes the existing bytes, not another body copy.
        need(hashlib.sha256(memoryview(wire)[offset:offset+size]).hexdigest()==digest)
        records.append(SourceExtent(label,offset,size,digest));offset+=size+1
    need(end-offset==len(FOOTER) and wire.startswith(FOOTER,offset,end))
    result=SourceExtents(raw_header,tuple(records))
    need(canonical_size(dict(header=raw_header.decode(),parsedHeader=header,request=expected,records=[dict(label=r.label,offset=r.offset,
        size=r.size,sha256=r.sha256) for r in records]))<=METADATA_LIMIT)
    return result


def decode_sources(wire,proof):
    """Bounded lexical decoding only; Native validators are still required.

    This decoder's byte-domain proof is wire<=W, prior JSON<=W, next body<=W/4,
    its original UTF8 text<=W/4, newly parsed canonical JSON<=5W/4, and a number
    token<=W/4: at most4W plus bounded metadata. Unicode expansion is at most3x;
    finite JSON scientific notation can expand e.g.1e15 into18 canonical bytes,
    so3x would be wrong. The closed5x per-packet bound is checked below.
    This is a decoded/stored-byte accounting statement, not Python RSS.
    No complete canonical JSON buffer or whole-frame deepcopy is made here.
    """
    need(type(wire) is bytes and len(wire)<=WIRE_LIMIT and type(proof) is SourceExtents
        and type(proof.records) is tuple)
    values={};used=2
    for row in proof.records:
        need(type(row) is SourceExtent and integer(row.offset,0,len(wire))
            and integer(row.size,1,256 if row.label=='nativePending' else LIMITS[row.label])
            and row.offset+row.size<=len(wire))
        body=wire[row.offset:row.offset+row.size]
        need(checksum(body)==row.sha256)
        text=body.decode('utf-8',errors='strict');value=strict_json(text)
        size=canonical_size(value,limit=5*LIMITS['native'])
        need(size<=5*len(body))
        del body,text
        if row.label=='nativePending':
            exact(value,{'schemaVersion','requestId','pending'})
            need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['pending'] is True
                and type(value['requestId']) is str and re.fullmatch('[0-9a-f]{32}',value['requestId']))
            # Retained in the opaque wire, never a substitute current source.
            continue
        need(row.label not in values and type(value) is dict)
        used+=len(row.label)+3+size+(1 if values else 0);need(used<=WIRE_LIMIT)
        values[row.label]=value
    need(tuple(values)==LABELS);return values


def protocol_identity():
    values=(VERSION,WIRE_LIMIT,METADATA_LIMIT,METADATA_OVERLAP_LIMIT,SIDE_LIMIT,EXISTING_SIDE_LIMIT,HEADER,FOOTER,LABELS)
    return (tuple((type(value),value) for value in values),LIMITS,
        tuple((key,type(value),value) for key,value in LIMITS.items()),
        request,extents,decode_sources,SourceExtent,SourceExtents)


class PicoEmoteSourceTransactionWire:
    """Lower-level opaque return owner, intentionally not a Source factory.

    ``exchange`` must be the later reviewed fixed one-SDK operation, with SDK
    check=False so a nonzero remote exit cannot discard acquired stdout. Its current
    Host tests supply a declared transport boundary; no Native provider is wired.
    A Source-capacity/native-file/cold-identity integration is still mandatory.
    """
    def __init__(self,archive,exchange,guard,clock):
        need(type(archive) is AudioRawArchive and all(callable(v) for v in (exchange,guard,clock))
            and archive.scope.get('picoEmoteSourceTransactionVersion')==VERSION
            and type(archive.scope.get('picoEmoteSourceTransactionVersion')) is int
            and SIDE_LIMIT<=EXISTING_SIDE_LIMIT)
        self.archive,self.exchange,self.guard,self.clock=archive,exchange,guard,clock
        self._pins=(archive,exchange,guard,clock);self.active=None;self.failed=False
        self.pending=None;self.reference=None;self.acquired=None;self.started=None
        self.claims=self._claims=()
        self._protocol=protocol_identity;self._protocol_pin=protocol_identity()
        self._issued=None
        # Cold selection, before every guard/clock/getter callback. Subclasses
        # may compose a physical protocol without another Raw writer.
        self.reply_reserver=self._reply_reserver=self.reserve_reply
        self.reply_parser=self._reply_parser=self.parse_reply
        OWNED.append(self)

    def identity(self):
        need(not self.failed and self.archive is self._pins[0] and same_callable(self.exchange,self._pins[1])
            and same_callable(self.guard,self._pins[2]) and same_callable(self.clock,self._pins[3])
            and same_callable(self.reply_reserver,self._reply_reserver) and same_callable(self.reserve_reply,self._reply_reserver)
            and same_callable(self.reply_parser,self._reply_parser) and same_callable(self.parse_reply,self._reply_parser)
            and self.claims is self._claims and self._protocol()==self._protocol_pin)
        self.archive.lock.assert_held()

    def reserve_reply(self,value):
        return self.archive.reserve('emote-source-txn',value,WIRE_LIMIT,side_bytes=SIDE_LIMIT)

    def parse_reply(self,wire,value):
        proof=extents(wire,value);return proof,decode_sources(wire,proof)

    def fresh(self):
        self.identity();need(self.guard() is not False);self.identity();now=self.clock();self.identity()
        need(number(now,self.started,self.started+5) and now-self.started<5)
        return now

    def retain(self,value):
        # The actual already-issued reservation/retainer survives business,
        # callback, public archive and module-format substitution independently.
        need(self._issued is not None)
        archive,token,retainer,limit=self._issued
        if type(value) is not bytes or len(value)>limit:
            UNCONFIRMED.append((self,self._issued,value));need(False)
        self.acquired=value
        reference=retainer(token,value)
        self.reference=reference;self.pending=None;self.acquired=None;self._issued=None;return reference

    def read(self,value):
        self.identity()
        if self.active is not None:self.failed=True;need(False)
        request(value)
        frozen=canonical(value)
        # The existing original journal is the nonce history. Do not retain a
        # second unbounded list of full commands in this decoder's side budget.
        prior=[row for page in self.archive.pages.values() for row in page['receipts'] if row is not None]
        need(not any(row['role']=='emote-source-txn' and row['command'].get('commandId')==value['commandId'] for row in prior)
            and not any(row['role']=='emote-source-txn' and row['command'].get('commandId')==value['commandId']
                for row in self.archive.state['pending']))
        del prior
        claim=object();self.active=claim # BEFORE clock/guard/transport callbacks.
        self.claims=self._claims=((claim,frozen),)
        self.reference=None;self.acquired=None
        try:
            self.started=self.clock();need(number(self.started,0,1e15));self.fresh()
            token=self.reply_reserver(value)
            self.pending=deepcopy(token)
            self._issued=(self.archive,token,self.archive.retain,token['limit'])
            now=self.fresh();need(canonical(value)==frozen and self.active is claim)
            try:wire=self.exchange(value,timeout=self.started+5-now)
            except BaseException as error:
                partial=(subprocess.TimeoutExpired,subprocess.CalledProcessError)
                cause=error if isinstance(error,partial) else error.__cause__
                if isinstance(cause,partial) and type(cause.output) is bytes:self.retain(cause.output)
                raise
            self.retain(wire) # Resource authority only, before every parser or late business guard.
            self.fresh();need(canonical(value)==frozen and self.active is claim)
            proof,sources=self.reply_parser(wire,value)
            self.fresh();need(canonical(value)==frozen and self.active is claim)
            return self.reference,proof,sources
        except BaseException:self.failed=True;raise
        finally:
            if self.active is claim:self.active=None
