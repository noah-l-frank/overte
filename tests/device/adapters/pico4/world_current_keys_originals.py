"""Warm World-owned originals using the existing bounded source chunk codec.

Historical references never replace a fresh keyboard/focus/DOM acquisition.
Uncertain writes/descriptor ownership stay retained; there is no adoption API.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import re
import base64
import os
import zlib
from pathlib import Path
from adapters.native_feature_observation import need,exact,integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.host_process_identity import host_identity
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest,digest
from adapters.script_journey.history import canonical,pack,MAX_FRAMES,MAX_RAW,MAX_PACKED
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.native_fd_owner import require_directory,OriginalDescriptor
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature

FILE='pico-world-current-keys-originals.json'
VERSION=2
LITERAL_FRAGMENT=16384
UNRESOLVED_HOST_FILES=[]
UNRESOLVED_SOURCE_RECORDS=[]


class WorldCurrentKeysHostPass:
    """One callback-free host staging window, not a source/input admission.

    Full Parent bytes/pins bracket the pass. Within it, every old physical
    identity is checked freshly and only prepared own file writes may change
    the expected set. No arbitrary post-write inventory is ever adopted.
    """
    def __init__(self,ledger,baseline):
        self.ledger=ledger;self.parent=ledger.parent;self.failed=False;self.writers=[];self.final_pins=None
        self.directory=None;self.expected={row['path']:deepcopy(row) for row in baseline}
        need(len(self.expected)==len(baseline) and json_digest(self.parent.pins())==json_digest(baseline))
        try:
            self.directory=OriginalDescriptor(self.parent.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.guard()
        except BaseException:
            self.failed=True;UNRESOLVED_HOST_FILES.append(self);raise

    def physical(self,*,except_root=False):
        need(not self.failed and self.directory is not None)
        require_directory(self.directory,self.parent.root)
        # Atomic replacement can invalidate a retained directory stream's
        # enumeration state even after listdir reports an offset of zero.
        # Explicitly rewind this same verified original OFD for every scan.
        os.lseek(self.directory.fd,0,os.SEEK_SET)
        names=set(os.listdir(self.directory.fd));need(names=={Path(path).name for path in self.expected})
        for path,row in self.expected.items():
            if except_root and path==str(self.ledger.store.path):continue
            info=os.stat(Path(path).name,dir_fd=self.directory.fd,follow_symlinks=False)
            need(signature(info)==row['signature'])
        require_directory(self.directory,self.parent.root)

    def guard(self):self.physical()

    def remember(self):
        # Only this actual root prepared/retained OFD may replace the header.
        # All unrelated/old child nodes remain the original exact 8-stat set.
        self.physical(except_root=True);self.ledger.file.guard()
        need(self.ledger.file.parent.node==self.directory.node)
        self.expected[str(self.ledger.store.path)]=dict(path=str(self.ledger.store.path),
            signature=list(self.ledger.file.stamp),sha256=hashlib.sha256(self.ledger.file.raw).hexdigest())
        self.guard()

    def child(self,writer):
        writer.guard();require_directory(writer.parent,self.parent.root)
        path=str(writer.path);need(path not in self.expected and writer.parent.node==self.directory.node)
        self.expected[path]=dict(path=path,signature=list(writer.stamp),sha256=hashlib.sha256(writer.raw).hexdigest())
        self.guard()

    def finish(self):
        self.guard();self.ledger.file.guard()
        observed=self.parent.pins();expected=[self.expected[path] for path in sorted(self.expected)]
        # Compare FIRST. A byte-equal replacement or foreign edit cannot be
        # adopted by updating the caller's expected Parent pins afterwards.
        need(json_digest(observed)==json_digest(expected));self.guard()
        for writer in self.writers:writer.guard()
        for writer in self.writers:
            if not writer.close_host():self.failed=True;UNRESOLVED_HOST_FILES.append(self);need(False)
        if not self.directory.close():self.failed=True;UNRESOLVED_HOST_FILES.append(self);need(False)
        self.final_pins=deepcopy(observed)


def source_literal(record,raw):
    if 'literalReference' in record:
        need(not any(k.startswith('literalCodec') or k in ('literalEncoding','literalBytes','literalSha256','literalData') for k in record))
        return raw(record['literalReference'])
    need(type(record.get('literalCodecVersion')) is int and record['literalCodecVersion']==1
         and record.get('literalEncoding')=='utf8-base64-inline' and integer(record.get('literalBytes'),0,131072)
         and type(record.get('literalSha256')) is str and re.fullmatch('[0-9a-f]{64}',record['literalSha256'])
         and type(record.get('literalData')) is str and len(record['literalData'])<=174764)
    value=base64.b64decode(record['literalData'],validate=True)
    need(base64.b64encode(value).decode()==record['literalData'] and len(value)==record['literalBytes']
         and hashlib.sha256(value).hexdigest()==record['literalSha256'])
    return value.decode('utf-8',errors='strict')


def decode_reference(rows,reference):
    exact(reference,{'parts','bytes','sha256'})
    need(type(reference['parts']) is list and len(reference['parts'])<=128
         and all(integer(i,0,len(rows)-1) for i in reference['parts']) and integer(reference['bytes'],0,524288)
         and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256']))
    parts=reference['parts'];need(not parts or parts==list(range(parts[0],parts[-1]+1)))
    selected=[rows[i] for i in parts]
    for row in selected:exact(row,{'kind','value'});need(type(row['value']) is str)
    if not selected:raw=b''
    elif all(row['kind']=='world-keyboard-original' for row in selected):raw=''.join(row['value'] for row in selected).encode()
    else:
        need(all(row['kind']=='world-keyboard-literal-utf8-base64' for row in selected));fragments=[]
        for index,row in enumerate(selected):
            fragment=base64.b64decode(row['value'],validate=True)
            need(base64.b64encode(fragment).decode()==row['value'] and 0<len(fragment)<=LITERAL_FRAGMENT
                 and (index==len(selected)-1 or len(fragment)==LITERAL_FRAGMENT))
            fragments.append(fragment)
        raw=b''.join(fragments)
    need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
    return raw.decode('utf-8',errors='strict')


def historical_literal(store,reference):
    """Read historical1/2 complete originals; never recreate a warm producer.

    A reading header remains reading. No pending record, clock, Native source,
    controller session or original producer-host ownership is adopted.
    """
    need(type(store) is PrivateFeatureState);store._parent()
    directory=OriginalDescriptor(store.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    def guard():require_directory(directory,store.path.parent)
    original=ClosedOriginalFile(store.path,0o600,guard)
    try:
        raw,_stamp=original.read();header=json.loads(raw);need(store.read()==header)
        exact(header,{'picoWorldCurrentKeysOriginalsVersion','parentScope','binding','producerHostProcessIdentity','phase','chunks','records','pending'})
        need(type(header['picoWorldCurrentKeysOriginalsVersion']) is int and header['picoWorldCurrentKeysOriginalsVersion'] in (1,2)
             and header['phase'] in ('reading','retained') and type(header['records']) is list and reference in header['records'])
        scope={k:v for k,v in header.items() if k not in ('phase','chunks','records','pending')}
        chunks=ChatSourceChunks(store,scope);rows=chunks.load(header['chunks']);result=decode_reference(rows,reference)
        observed,_=original.read();need(observed==raw);guard();need(original.close())
        if not directory.close():UNRESOLVED_HOST_FILES.append(directory);need(False)
        return result
    except BaseException:
        if not original.close():UNRESOLVED_HOST_FILES.append(original)
        if not directory.close():UNRESOLVED_HOST_FILES.append(directory)
        raise


def resolve_original(reference,read,raw):
    record=read(reference);need(type(record) is dict)
    if record.get('kind')=='exact-canonical-original':
        exact(record,{'kind','sha256','original'});need(json_digest(record['original'])==record['sha256']);return deepcopy(record['original'])
    if record.get('kind') in ('calibration','focus-original','fresh-independent-effect'):
        exact(record,{'kind','original'});return deepcopy(record['original'])
    exact(record,{'kind','references','sha256'});need(record['kind']=='keyboard-original-bundle')
    exact(record['references'],{'request','raw'})
    request=read(record['references']['request']);literal=read(record['references']['raw'])
    need(json_digest(request['request'])==json_digest(literal['request']))
    focus=resolve_original(request['focusOriginalReference'],read,raw) if 'focusOriginalReference' in request else request['focusOriginal']
    value=dict(raw=source_literal(literal,raw),request=deepcopy(request['request']),focusOriginal=deepcopy(focus))
    need(json_digest(value)==record['sha256']);return value


def historical_original(store,reference):
    """Resolve original v1/v2 bundles without returning any current source."""
    def raw(ref):return historical_literal(store,ref)
    def read(ref):
        text=raw(ref);value=json.loads(text);need(canonical(value).decode()==text);return value
    return resolve_original(reference,read,raw)


class WorldCurrentKeysOriginals:
    def __init__(self,parent,guard,remember):
        self.parent,self.guard_parent,self.remember=parent,guard,remember
        self.store=PrivateFeatureState(parent.root/FILE);self.previous=None;self.failed=False;self.closed=False
        self.file=None;self.rows=[];self.pass_window=None
        try:
            parent.lock.assert_held();guard()
            need(self.store.read() is None and not any(p.name.startswith(FILE) for p in parent.root.iterdir()))
            self.scope=dict(picoWorldCurrentKeysOriginalsVersion=VERSION,parentScope=deepcopy(parent.scope),
                            binding=deepcopy(parent.state['binding']),producerHostProcessIdentity=host_identity())
            self.chunks=ChatSourceChunks(self.store,self.scope);self.chunks.load([])
            self.file=object.__new__(LifecycleProcessFile);LifecycleProcessFile.__init__(self.file,self.store)
            self.state=dict(phase='reading',chunks=[],records=[],pending=None);self.original_index={}
            self.save(initial=True)
        except BaseException:
            self.failed=True
            if self.file is not None:UNRESOLVED_HOST_FILES.append(self.file)
            raise

    def guard(self):
        need(not self.failed and not self.closed);self.parent.lock.assert_held();self.guard_parent()
        need(self.scope['producerHostProcessIdentity']==host_identity())
        self.file.guard();require_directory(self.file.parent,self.parent.root)
        need(self.store.read()==self.previous);self.chunks.verify()

    @contextmanager
    def host_transaction(self,baseline):
        self.parent.lock.assert_held();need(self.pass_window is None and not self.failed and not self.closed)
        window=WorldCurrentKeysHostPass(self,baseline);self.pass_window=window
        try:
            yield window
            window.finish()
        except BaseException:
            window.failed=True;self.failed=True
            if window not in UNRESOLVED_HOST_FILES:UNRESOLVED_HOST_FILES.append(window)
            raise
        finally:self.pass_window=None

    def append_frame(self,frame):
        if self.pass_window is None:return self.chunks.append(frame,self.state['chunks'])
        self.guard();need(self.state['phase']=='reading' and len(self.chunks.identities)==len(self.state['chunks'])<MAX_FRAMES)
        header=self.store.read();need(header['phase']=='reading' and header['chunks']==self.state['chunks'])
        transcript=pack([deepcopy(frame)]);total=self.chunks.raw_bytes+transcript['bytes']-2+(1 if self.state['chunks'] else 0)
        need(total<=MAX_RAW);index=len(self.state['chunks'])
        value=dict(chatSampleChunkVersion=1,scopeSha256=self.chunks.scope,index=index,transcript=transcript)
        child=self.chunks.store(index);need(child.read() is None)
        writer=object.__new__(LifecycleProcessFile);self.pass_window.writers.append(writer)
        LifecycleProcessFile.__init__(writer,child);need(writer.file is None)
        writer.write(value,None);self.pass_window.child(writer)
        original=self.chunks.signature(index)
        need((original[0],original[1],original[4],original[3],original[5],original[2],original[6],original[7])==tuple(writer.stamp))
        self.chunks.identities.append(original);self.chunks.raw_bytes=total
        return self.state['chunks']+[digest(value)]

    def save(self,*,initial=False):
        if not initial:self.guard()
        value=dict(self.scope,**deepcopy(self.state));self.file.write(value,self.previous);self.previous=deepcopy(value)
        self.remember();self.guard()

    def capacity(self,maximum=131072,*,literal=True):
        self.guard();need(integer(maximum,1,524288) and self.state['pending'] is None)
        # JSON literal escaping may require six ASCII bytes per original byte.
        size=LITERAL_FRAGMENT if literal else 4096
        parts=(maximum+size-1)//size+1
        need(len(self.rows)+parts<=MAX_FRAMES and self.chunks.raw_bytes+6*maximum+parts*128<=MAX_RAW)
        future=deepcopy(self.state);future['chunks']+=['f'*64]*parts
        future['records'].append(dict(parts=[MAX_FRAMES-1]*parts,bytes=maximum,sha256='f'*64))
        future['records'].append(dict(parts=[MAX_FRAMES-1],bytes=maximum,sha256='f'*64))
        need(len(canonical(dict(self.scope,**future)))+1<=65536)
        stored=sum(v[2] for v in self.chunks.identities)+self.store.path.lstat().st_size
        need(stored+(parts+2)*65536<=MAX_RAW)
        # Parent pins every existing original in this SAME bounded namespace.
        need(len(list(self.parent.root.iterdir()))+parts+2<=512)

    def retain(self,value):
        self.guard();raw=canonical(value).decode();need(len(raw.encode())<=524288)
        return self._retain_text(raw)

    def retain_literal(self,raw):
        self.guard();need(type(raw) is str and len(raw.encode())<=131072)
        return self._retain_text(raw,literal=True)

    def retain_source(self,value):
        """Retain one NEW transport request/raw, reusing exact old originals.

        Only nested already-captured focus data is referenced. New request
        nonces, every raw reply and literal mapping are always newly retained.
        """
        self.guard();need(type(value) is dict);acquired=value;UNRESOLVED_SOURCE_RECORDS.append(acquired)
        try:
            if 'focusOriginal' in value:
                original=value['focusOriginal'];ref=self.intern_original(original)
                value={k:deepcopy(v) for k,v in value.items() if k!='focusOriginal'}
                value['focusOriginalReference']=ref
            if type(value.get('raw')) is str:
                literal=value['raw'];encoded=literal.encode();need(len(encoded)<=131072)
                metadata={k:deepcopy(v) for k,v in value.items() if k!='raw'}
                # Closed World commands have a <=512-byte ASCII fixture URL
                # and fixed nonce/operation fields. Keep their complete raw
                # association within the reserved one metadata child.
                need(len(canonical(metadata))<=4096)
                inline=dict(metadata,literalCodecVersion=1,literalEncoding='utf8-base64-inline',literalBytes=len(encoded),
                    literalSha256=hashlib.sha256(encoded).hexdigest(),literalData=base64.b64encode(encoded).decode())
                text=canonical(inline).decode();frame=dict(kind='world-keyboard-original',value=text)
                # The SAME actual codec size, calculated before selecting a
                # layout. An unrelated encoding/CAS error is never caught and
                # misclassified as an oversized candidate.
                candidate=base64.b64encode(zlib.compress(canonical([frame]),level=9))
                if len(candidate)<=MAX_PACKED:
                    self.capacity();reference=self._retain_prepared(text,[frame])
                else:
                    literal_ref=self.retain_literal(literal);metadata['literalReference']=literal_ref
                    reference=self.retain(metadata)
            else:reference=self.retain(value)
            for index,record in enumerate(UNRESOLVED_SOURCE_RECORDS):
                if record is acquired:del UNRESOLVED_SOURCE_RECORDS[index];break
            return reference
        except BaseException:
            self.failed=True
            if self.file not in UNRESOLVED_HOST_FILES:UNRESOLVED_HOST_FILES.append(self.file)
            raise

    def _retain_text(self,raw,*,literal=False):
        self.capacity(len(raw.encode()) or 1,literal=literal)
        encoded=raw.encode()
        if literal:
            parts=[dict(kind='world-keyboard-literal-utf8-base64',value=base64.b64encode(encoded[offset:offset+LITERAL_FRAGMENT]).decode())
                   for offset in range(0,len(encoded),LITERAL_FRAGMENT)]
        else:parts=[dict(kind='world-keyboard-original',value=raw[offset:offset+4096]) for offset in range(0,len(raw),4096)]
        return self._retain_prepared(raw,parts)

    def _retain_prepared(self,raw,parts):
        reference=dict(parts=[],bytes=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest())
        try:
            self.state['pending']=deepcopy(reference);self.save()
            for part in parts:
                # A Unicode code point is preserved across JSON-string chunks;
                # each child is independently well within the existing codec.
                index=len(self.rows)
                self.state['chunks']=self.append_frame(part);self.rows.append(part)
                self.state['pending']['parts'].append(index);self.remember();self.save()
            reference=deepcopy(self.state['pending']);self.state['records'].append(reference);self.state['pending']=None;self.save()
            return deepcopy(reference)
        except BaseException:
            self.failed=True;UNRESOLVED_HOST_FILES.append(self.file);raise

    def raw(self,reference):
        self.guard();exact(reference,{'parts','bytes','sha256'})
        need(type(reference['parts']) is list and len(reference['parts'])<=128
             and all(integer(i,0,511) for i in reference['parts']) and integer(reference['bytes'],0,524288)
             and type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256']))
        need(reference in self.state['records'] and (not reference['parts'] or reference['parts']==list(range(reference['parts'][0],reference['parts'][-1]+1))))
        # Fresh original inventory, full private-file bytes and stamps every
        # time; in-memory decoded rows alone cannot qualify a reference.
        rows=self.chunks.load(self.state['chunks']);need(json_digest(rows)==json_digest(self.rows))
        text=decode_reference(rows,reference);self.guard();return text

    def read(self,reference):
        text=self.raw(reference);value=json.loads(text);need(canonical(value).decode()==text);return value

    def original(self,reference):return resolve_original(reference,self.read,self.raw)

    def intern_original(self,value):
        """Reuse only exact original DTO bytes, with fresh existing file proof."""
        self.guard();digest=json_digest(value);raw=canonical(value)
        existing=self.original_index.get(digest)
        if existing is not None:
            pinned,reference_bytes=existing;need(pinned==raw)
            reference=json.loads(reference_bytes)
            # Re-read the actual retained canonical record as well as all
            # original Parent/file proofs. Forging mutable cache/reference
            # fields cannot redirect a new query to another original.
            original=self.read(reference)
            exact(original,{'kind','sha256','original'})
            need(original['kind']=='exact-canonical-original' and original['sha256']==digest
                 and canonical(original['original'])==raw and json_digest(original['original'])==digest)
            self.guard();return reference
        reference=self.retain(dict(kind='exact-canonical-original',sha256=digest,original=deepcopy(value)))
        self.original_index[digest]=(raw,canonical(reference));self.guard();return deepcopy(reference)

    def finish_host(self):
        self.guard();need(self.state['pending'] is None)
        self.state['phase']='retained';self.save()
        if not self.file.close_host():
            self.failed=True;UNRESOLVED_HOST_FILES.append(self.file);need(False)
        self.closed=True
