"""Explicit Assets Layout2 over existing original range/index ownership.

The native body cap remains4MiB. Up to4096 opaque transport framing/overrun
bytes are preserved in an explicitly reserved original bundle. The enclosing
Parent supplies the SAME global512/16MiB bill; this is not another quota lane.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import os
import re

from adapters.chat_journey.source_chunks import json_digest
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.native_fd_owner import require_directory
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need
from adapters.pico4.audio_raw_archive import AudioRawArchive,MAX_LITERAL as AUDIO_LITERAL,PART
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW,same

MAX_LITERAL=4*AUDIO_LITERAL
AUX=4096
# RetainedUTF8/extents/copy/CAS reservation; not a Python heap/RSS claim.
SIDE=MAX_LITERAL
OVERLAY=MAX_LITERAL+2*AUX+2*PART
UNCONFIRMED=[]


def scope(parent):
    return dict(assetsRawOriginalLayoutVersion=2,maximumLiteralBytes=MAX_LITERAL,parentScopeSha256=json_digest(parent))


def compact_reference(value):
    exact(value,{'assetsRawCompactVersion','read','sha256','tailBundle'})
    need(type(value['assetsRawCompactVersion']) is int and value['assetsRawCompactVersion']==2
        and integer(value['read'],0,MAX_FRAMES-1) and type(value['sha256']) is str
        and re.fullmatch('[0-9a-f]{64}',value['sha256'])
        and (value['tailBundle'] is None or integer(value['tailBundle'],0,MAX_FRAMES-1)))
    return value


def reference(value,parent_scope):
    exact(value,{'assetsRawLiteralVersion','scopeSha256','read','bytes','sha256','rangeOriginal','tailBundle'})
    need(type(value['assetsRawLiteralVersion']) is int and value['assetsRawLiteralVersion']==2
        and value['scopeSha256']==parent_scope and integer(value['read'],0,MAX_FRAMES-1)
        and integer(value['bytes'],0,MAX_LITERAL+AUX) and type(value['sha256']) is str
        and re.fullmatch('[0-9a-f]{64}',value['sha256'])
        and (value['tailBundle'] is None or integer(value['tailBundle'],0,MAX_FRAMES-1)))
    raw=value['rangeOriginal'];exact(raw,{'audioRawRangeVersion','scopeSha256','read','sha256'})
    need(type(raw['audioRawRangeVersion']) is int and raw['audioRawRangeVersion']==1
        and integer(raw['read'],0,MAX_FRAMES-1) and raw['read']==value['read']
        and type(raw['scopeSha256']) is str and re.fullmatch('[0-9a-f]{64}',raw['scopeSha256'])
        and type(raw['sha256']) is str and re.fullmatch('[0-9a-f]{64}',raw['sha256'])
        and (value['bytes']<=MAX_LITERAL)==(value['tailBundle'] is None))
    return value


class AssetsRawRanges:
    def __init__(self,owner):
        need(owner.scope['assetsPrefixVersion']==3 and owner.scope['assetsRawOriginalLayoutVersion']==2)
        self.owner,self.scope=owner,canonical(owner.scope);self.scope_sha=json_digest(owner.scope)
        self.path=owner.store.path;self.active=None;self.failed=False;self.rows=[];self.reads=0
        self.unconfirmed=None;self.overlay=0;self.final_windows=[];self.final_overlay=0
        self.audio_ctor_complete=self._audio_ctor_complete=False
        # Keep the actual partially constructed owner before any directory
        # acquisition or original CAS. A lost constructor response is not an
        # empty source, and its original descriptor pairs must remain held.
        self.audio=self.original_audio=self._original_audio=object.__new__(AudioRawArchive)
        try:
            AudioRawArchive.__init__(self.audio,self.path.with_name(self.path.name+'.child-raw2'),scope(owner.scope),owner.lock,
                self.identity,self.other_bill,owner.phases.monotonic,literal_limit=MAX_LITERAL)
            self.verify();self.audio_ctor_complete=self._audio_ctor_complete=True
        except BaseException:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
            raise

    def audio_owned(self):
        if (self.audio is self.original_audio is self._original_audio
                and type(self.audio_ctor_complete) is bool and self.audio_ctor_complete is self._audio_ctor_complete):return True
        self.failed=True
        if self not in UNCONFIRMED:UNCONFIRMED.append(self)
        return False

    def identity(self,*,held=True):
        need(self.audio_owned())
        if held:self.owner.lock.assert_held()
        self.owner.archival_identity()
        need(self.path==self.owner.store.path and canonical(self.owner.scope)==self.scope)

    def verify(self,*,held=True):
        if not held:return self.verify_final()
        self.identity()
        if self.audio is not None:self.audio.verify()

    def final_anchor(self):
        need(self.audio_owned())
        # Runs before AND after every fresh qualified-file window. No kernel
        # source-lock acquisition and no business/native clock callback here.
        a=self.audio
        need(a is not None and a is self.original_audio and a.directory is a.original_directory and not a.failed
            and a.lock is a._lock is self.owner.lock and a.identity is a._identity
            and a.other_bill is a._other_bill and a.clock is a._clock
            and a.path==self.path.with_name(self.path.name+'.child-raw2') and a.store.path==a.path
            and a.host==host_identity() and a.scope==scope(self.owner.scope)
            and a.scope_sha==json_digest(a.scope) and a.literal_profile is a.original_literal_profile
            and a.literal_profile==(MAX_LITERAL,a.scope_sha) and type(a.literal_limit) is type(a._literal_limit) is int
            and a.literal_limit==a._literal_limit==MAX_LITERAL)
        require_directory(a.directory,a.path.parent)
        if a.writer is not None:
            a.writer.require(a.writer.fd);row=a.state['parts'][-1]
            need(not row['closed'] and signature(os.fstat(a.writer.fd))==row['physical']
                and signature(a.part_path(len(a.state['parts'])-1).lstat())==row['physical'])
        for index,original in a.closed.items():
            need(not original.failed and original.active is None and original.path==a.part_path(index)
                and original.stamp==a.state['parts'][index]['physical'])

    def final_file(self,path,mode,expected,physical):
        self.final_anchor()
        original=object.__new__(ClosedOriginalFile);self.final_windows.append(original)
        ClosedOriginalFile.__init__(original,path,mode,self.final_anchor)
        raw,actual=original.read(lambda raw:need(raw==expected))
        need(actual==physical and raw==expected and original.close())
        self.final_windows.remove(original)

    def verify_final(self):
        try:
            need(not self.failed);self.final_anchor();self.identity(held=False);a=self.audio
            need(a.state==a.disk['state'] and json_digest(a.state)==json_digest(a.disk['state']))
            current=self.owner.bill();ours=a.bill()
            transient=ours['literalBytes']+2*ours['metadataBytes']+2*PART
            need(current['decodedBytes']+transient<=MAX_RAW and current['storedBytes']+transient<=MAX_RAW)
            self.final_overlay=transient
            self.final_file(a.path,0o600,canonical(a.disk)+b'\n',a.pin)
            names=set()
            # Confirmed immutable index bytes come from the same original
            # Audio archive. Rehash them freshly and encode each live DTO once.
            need(type(a.page_bodies) is dict and set(a.page_bodies)==set(a.page_pins)
                and all(type(body) is bytes and 0<len(body)<PART for body in a.page_bodies.values()))
            expected_pages=[]
            for index,(value,physical) in sorted(a.page_pins.items()):
                need(type(index) is int and value is a.pages[index])
                body=a.page_bodies[index];digest=hashlib.sha256(body).hexdigest()
                need(digest==json_digest(value))
                path=a.page_store(index).path;names.add(path.name)
                self.final_file(path,0o600,body+b'\n',physical)
                expected_pages.append(dict(page=index,sha256=digest,physical=physical))
            need(same(a.state['pages'],expected_pages))
            for index,row in enumerate(a.state['parts']):
                path=a.part_path(index);names.add(path.name)
                if row['closed']:
                    need(index in a.closed);expected=a.closed[index].raw;mode=0o400
                else:
                    need(index==len(a.state['parts'])-1 and a.writer is not None);expected=a.open_data;mode=0o600
                need(type(expected) is bytes and len(expected)==row['bytes']
                    and hashlib.sha256(expected).hexdigest()==row['sha256'])
                if expected:self.final_file(path,mode,expected,row['physical'])
                else:
                    # Empty open extents use the still-owned original writer;
                    # ClosedOriginalFile intentionally refuses empty files.
                    self.final_anchor();need(os.pread(a.writer.fd,PART+1,0)==b'')
                    a.writer.require(a.writer.fd);self.final_anchor()
            actual=set()
            with os.scandir(a.path.parent) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    if entry.name.startswith(a.path.name+'.'):actual.add(entry.name)
            need(actual==names);self.final_anchor();self.identity(held=False);self.final_overlay=0
        except BaseException:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
            raise

    def bill(self):
        need(self.audio_owned())
        if self.audio is None:return dict(parts=0,bytes=0)
        bill=self.audio.bill()
        return dict(parts=bill['files'],bytes=bill['decodedBytes']+self.final_overlay)

    def other_bill(self):
        need(self.audio_owned())
        current=self.owner.bill();own=self.audio.bill()
        if self.owner.raw_archive is not self:
            # The original Audio constructor may call back before Parent's
            # RHS assignment attaches this wrapper. Include exactly the own
            # files/bytes absent from that actual Parent bill, then use the
            # same subtraction as an already attached current family.
            current=dict(current,frames=current['frames']+own['files'],
                decodedBytes=current['decodedBytes']+own['decodedBytes'],
                storedBytes=current['storedBytes']+own['storedBytes'])
        # Actual index/root files are already in Parent.frames. Subtract only
        # data parts added by Audio.reserve itself; reserve one new index page.
        return dict(parts=current['frames']-own['parts']+2,
            decodedBytes=current['decodedBytes']-own['decodedBytes']+self.overlay,
            storedBytes=current['storedBytes']-own['storedBytes']+self.overlay)

    def reserve(self,role,command,limit=MAX_LITERAL):
        try:
            self.verify();need(not self.failed and self.active is None and self.owner.disk['pendingRawRead'] is None
                and integer(limit,1,MAX_LITERAL) and self.reads<MAX_FRAMES and type(role) is str and re.fullmatch('[a-z-]{1,32}',role))
            command_ref=self.owner.command_reference(command)
            # Command-reference creation is itself durable and accounted for.
            # Scope does not renew; every subsequent send/getter rechecks age.
            need(len(canonical(command_ref))<=4096)
            self.overlay=OVERLAY
            token=self.audio.reserve(role,command_ref,limit,side_bytes=SIDE)
            self.active=dict(assetsRawReadVersion=2,scopeSha256=self.scope_sha,read=self.reads,role=role,
                commandSha256=json_digest(command),commandBytes=len(canonical(command)),limit=limit,
                state='reserved',literal=None,rangeToken=token)
            self.owner.state['pendingRawRead']=deepcopy(self.active);self.owner.save()
            # Largest short receipt plus4096-tail original bundle/reference is
            # included before any SDK get, even when the actual tail is empty.
            need(len(canonical(self.owner.state))+2048<=PART)
            return deepcopy(self.active)
        except BaseException:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
            raise

    def retain(self,text):
        try:need(type(text) is str);return self.retain_bytes(text.encode('utf-8'))
        except BaseException:self.failed=True;raise

    def retain_bytes(self,raw):
        return self.retain_wire(raw,allow_aux=False)

    def retain_wire(self,raw,*,allow_aux=True):
        try:
            # Original issued return is strongly held before physical checks.
            need(self.active is not None and type(raw) is bytes)
            self.unconfirmed=raw
            self.verify();need(not self.failed and self.active['state']=='reserved'
                and len(raw)<=self.active['limit']+(AUX if allow_aux else 0))
            prefix=raw[:self.active['limit']];tail=raw[self.active['limit']:]
            range_ref=self.audio.retain(self.active['rangeToken'],prefix)
            tail_index=None
            if tail:
                tail_index=self.owner.archive(dict(assetsRawWireTailVersion=1,read=self.reads,
                    bytes=len(tail),sha256=hashlib.sha256(tail).hexdigest(),data=base64.b64encode(tail).decode('ascii')))
            literal=dict(assetsRawLiteralVersion=2,scopeSha256=self.scope_sha,read=self.reads,bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),rangeOriginal=range_ref,tailBundle=tail_index)
            reference(literal,self.scope_sha)
            self.active.update(state='sealed',literal=deepcopy(literal));self.overlay=0
            self.verify();return deepcopy(literal)
        except BaseException:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
            raise

    def clear_intent(self):
        need(not self.failed and self.active is not None and self.active['state']=='sealed')
        self.owner.state['pendingRawRead']=None

    def delivered(self,index):
        try:
            self.verify();need(not self.failed and self.active is not None and self.active['state']=='sealed'
                and self.owner.disk['pendingRawRead'] is None)
            from adapters.pico4.assets_raw_archive import compact
            value=self.owner.raw_record(index);need(same(value['rawOriginal'],compact(self.active['literal'])))
            self.rows.append(deepcopy(self.active['literal']));self.reads+=1;self.active=None;self.unconfirmed=None
        except BaseException:self.failed=True;raise

    def parser_capacity(self,text,command):
        from adapters.pico4.assets_raw_archive import quoted_bytes
        self.verify();need(not self.failed and self.rows and type(text) is str)
        required=quoted_bytes(text)+len(canonical(command))+4096
        try:need(self.owner.bill()['decodedBytes']+required<=MAX_RAW)
        except BaseException:self.failed=True;raise
        return required

    def literal(self,value):
        need(type(value) is dict)
        # Only closed DTO validation lies between this Parent window and
        # Audio.literal's full fresh entry guard. Keep its actual range/OFD
        # reads and our full final verify; do not repeat that entry beforehand.
        self.identity()
        if value.get('assetsRawCompactVersion')==2:
            from adapters.pico4.assets_raw_archive import compact
            compact_reference(value);need(integer(value['read'],0,len(self.rows)-1))
            original=self.rows[value['read']];need(same(value,compact(original)));value=original
        reference(value,self.scope_sha);need(any(same(value,row) for row in self.rows))
        raw=self.audio.literal(value['rangeOriginal']);need(type(raw) is bytes)
        if value['tailBundle'] is not None:
            tail=self.owner.original(value['tailBundle']);exact(tail,{'assetsRawWireTailVersion','read','bytes','sha256','data'})
            need(type(tail['assetsRawWireTailVersion']) is int and tail['assetsRawWireTailVersion']==1
                and tail['read']==value['read'] and integer(tail['bytes'],1,AUX) and type(tail['data']) is str)
            extra=base64.b64decode(tail['data'],validate=True)
            need(base64.b64encode(extra).decode('ascii')==tail['data'] and len(extra)==tail['bytes']
                and hashlib.sha256(extra).hexdigest()==tail['sha256']);raw+=extra
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']);self.verify();return raw

    def close_host(self):
        if not self.audio_owned() or not self.audio_ctor_complete:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
            return False
        results=[]
        for original in self.final_windows:
            try:results.append(original.close())
            except BaseException:results.append(False)
        results.append(True if self.audio is None else self.audio.close_host())
        result=all(results)
        if not result:
            self.failed=True
            if self not in UNCONFIRMED:UNCONFIRMED.append(self)
        return result
