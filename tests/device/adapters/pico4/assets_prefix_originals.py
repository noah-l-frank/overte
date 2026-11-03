"""Passive Prefix1/2 originals; no candidate, live owner, input or observation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import re
import stat

from adapters.chat_journey import source_bundles
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_fd_owner import OriginalDescriptor, require_directory
from adapters.native_feature_observation import exact, integer, need
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.pico4.assets_raw_archive import PART_BYTES, MAX_LITERAL, expanded
from adapters.script_journey.history import canonical, MAX_FRAMES, MAX_RAW

BASE_SCOPE = {'assetsPrefixVersion', 'contractVersion', 'binding', 'runId', 'fixtureUrl'}
STATE = {'phase', 'chunks', 'bundles', 'pendingBundle', 'baseline', 'steps', 'pendingSource',
         'pendingChildSource', 'pendingInput', 'inputs', 'observations', 'nestedFrames', 'nestedDecodedBytes', 'cleanup'}


class AssetsPrefixOriginals:
    historical_only = True

    def __init__(self, path):
        self.store = PrivateFeatureState(path)
        self.directory = OriginalDescriptor(self.store.path.parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.root = ClosedOriginalFile(self.store.path, 0o600, self.directory_guard)
        self.files = {}
        raw, _stamp = self.root.read()
        value = self.store.read()
        need(canonical(value)+b'\n' == raw and type(value.get('assetsPrefixVersion')) is int
             and value['assetsPrefixVersion'] in (1, 2))
        self.version = value['assetsPrefixVersion']
        scope_fields = BASE_SCOPE | ({'assetsRawOriginalLayoutVersion'} if self.version == 2 else set())
        exact(value, scope_fields | STATE | ({'pendingRawRead','rawReads'} if self.version == 2 else set()))
        need(value['phase'] == 'reading' and value['pendingBundle'] is None
             and integer(value['nestedFrames'], 0, MAX_FRAMES) and integer(value['nestedDecodedBytes'], 0, MAX_RAW))
        if self.version == 2:
            need(type(value['assetsRawOriginalLayoutVersion']) is int and value['assetsRawOriginalLayoutVersion'] == 1
                 and type(value['rawReads']) is list and len(value['rawReads'])<=MAX_FRAMES)
        context(value['binding'])
        scope = {key:deepcopy(value[key]) for key in scope_fields}
        self.value = deepcopy(value)
        self.history = ChatSourceChunks(self.store, scope)
        self.history.load(value['chunks'])
        self.references = deepcopy(value['bundles'])
        need(sum(ref['parts'] for ref in self.references) == len(value['chunks']) <= MAX_FRAMES)
        self.expected_files = set()
        self.pending_names=set()
        self.pending=value.get('pendingRawRead')
        self.uncertain=[]
        if self.pending is not None:
            pending=self.pending
            exact(pending,{'assetsRawReadVersion','scopeSha256','read','role','commandSha256','commandBytes',
                'limit','reservedParts','state','literal'})
            need(type(pending['assetsRawReadVersion']) is int and pending['assetsRawReadVersion']==1
                 and pending['scopeSha256']==self.history.scope and integer(pending['read'],0,MAX_FRAMES-1)
                 and pending['read']==len(value['rawReads']) and type(pending['role']) is str
                 and re.fullmatch('[a-z-]{1,32}',pending['role']) and integer(pending['commandBytes'],0,65536)
                 and type(pending['commandSha256']) is str and re.fullmatch('[0-9a-f]{64}',pending['commandSha256'])
                 and integer(pending['limit'],1,MAX_LITERAL) and pending['reservedParts']==(pending['limit']+PART_BYTES-1)//PART_BYTES
                 and type(pending['reservedParts']) is int
                 and pending['state'] in ('reserved','retaining','sealed'))
            prefix=self.store.path.name+f'.child-raw-{pending["read"]:03d}-'
            with os.scandir(self.store.path.parent) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    if entry.name.startswith(prefix):
                        number=entry.name[len(prefix):]
                        need(re.fullmatch('[0-9]{2}\\.bin',number) and int(number[:2])<pending['reservedParts'])
                        self.pending_names.add(entry.name)
        raw_bytes = 0
        for row in value.get('rawReads',[]):
            if self.version == 2 and 'rawOriginal' in row:
                reference = self.raw_reference(expanded(row['rawOriginal'],self.store.path.name))
                raw_bytes += reference['bytes']
                for part in reference['parts']:
                    need(part['name'] not in self.expected_files)
                    self.expected_files.add(part['name'])
        pending_bytes=sum((self.store.path.parent/name).stat().st_size for name in self.pending_names)
        need(source_bundles.logical_bytes(self.references)+value['nestedDecodedBytes']+raw_bytes+pending_bytes+len(canonical(value.get('rawReads',[]))) <= MAX_RAW
             and len(value['chunks'])+len(self.expected_files|self.pending_names)+value['nestedFrames']+len(value.get('rawReads',[])) <= MAX_FRAMES)
        self.verify()

    def directory_guard(self):
        require_directory(self.directory, self.store.path.parent)

    def verify(self):
        self.directory_guard()
        raw, _stamp = self.root.read()
        need(raw == canonical(self.value)+b'\n')
        self.history.verify()
        if hasattr(self, 'expected_files'):
            with os.scandir(self.store.path.parent) as entries:
                actual = set()
                for index, entry in enumerate(entries):
                    need(index < 4096)
                    if entry.name.startswith(self.store.path.name+'.child-raw-'):
                        actual.add(entry.name)
            need(actual == self.expected_files|self.pending_names)

    def bundle(self, index):
        self.directory_guard()
        self.root.read()
        value, _raw = source_bundles.original(self.history, self.value['chunks'], self.references, index)
        self.root.read()
        return value

    def raw_reference(self, value):
        exact(value, {'assetsRawLiteralVersion', 'scopeSha256', 'read', 'bytes', 'sha256', 'parts'})
        need(type(value['assetsRawLiteralVersion']) is int and value['assetsRawLiteralVersion'] == 1
             and value['scopeSha256'] == self.history.scope and integer(value['read'], 0, MAX_FRAMES-1)
             and integer(value['bytes'], 0, MAX_LITERAL) and type(value['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}', value['sha256']) and type(value['parts']) is list
             and len(value['parts']) == (value['bytes']+PART_BYTES-1)//PART_BYTES)
        total = 0
        for index, part in enumerate(value['parts']):
            exact(part, {'name', 'bytes', 'sha256', 'physical'})
            need(part['name'] == self.store.path.name+f'.child-raw-{value["read"]:03d}-{index:02d}.bin'
                 and type(part['bytes']) is int and part['bytes'] == min(PART_BYTES, value['bytes']-total)
                 and type(part['sha256']) is str and re.fullmatch('[0-9a-f]{64}', part['sha256'])
                 and type(part['physical']) is list and len(part['physical']) == 8
                 and all(type(field) is int and 0 <= field <= 2**64-1 for field in part['physical']))
            total += part['bytes']
        need(total == value['bytes'])
        return value

    def literal(self, index):
        self.verify()
        if self.version==1:row=self.bundle(index)
        else:
            need(integer(index,0,len(self.value['rawReads'])-1));row=deepcopy(self.value['rawReads'][index])
        tag = 'role' if 'role' in row else 'childSource'
        need(tag in row and row[tag] in ('mappings', 'uploads', 'files', 'ui'))
        if self.version == 1:
            exact(row, {tag, 'raw', 'sha256'})
            need(type(row['raw']) is str)
            raw = row['raw'].encode('utf-8')
            need(len(raw) <= MAX_LITERAL and hashlib.sha256(raw).hexdigest() == row['sha256'])
        else:
            exact(row, {tag, 'rawOriginal'})
            reference = self.raw_reference(expanded(row['rawOriginal'],self.store.path.name))
            pieces = []
            for part in reference['parts']:
                if part['name'] not in self.files:
                    self.files[part['name']] = ClosedOriginalFile(self.store.path.parent/part['name'], 0o400, self.directory_guard)
                original = self.files[part['name']]
                actual, physical = original.read()
                need(physical == part['physical'] and len(actual) == part['bytes']
                     and hashlib.sha256(actual).hexdigest() == part['sha256'])
                pieces.append(actual)
            raw = b''.join(pieces)
            need(len(raw) == reference['bytes'] and hashlib.sha256(raw).hexdigest() == reference['sha256'])
        self.verify()
        return raw

    def close_host(self):
        return all([original.close() for original in self.files.values()]+[self.root.close(), self.directory.close()]
            +[owner.close() for owner in self.uncertain])

    def pending_read(self):
        """Inspect uncertain actual bytes; never qualify/adopt a failed scope.

        Before-write unknown CAS has no durable physical qualification for its
        new leaves. Exposing that distinction is essential: current bytes and
        a computed digest are not a replacement original receipt.
        """
        self.verify();need(self.pending is not None)
        pieces=[];rows=[]
        for name in sorted(self.pending_names):
            path=self.store.path.parent/name;owner=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            try:
                info=os.fstat(owner.fd);physical=signature(info)
                need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1
                     and stat.S_IMODE(info.st_mode) in (0o400,0o600) and 0<=info.st_size<=PART_BYTES)
                raw=os.pread(owner.fd,PART_BYTES+1,0);owner.require(owner.fd)
                need(len(raw)==info.st_size and signature(path.lstat())==signature(os.fstat(owner.fd))==physical)
                part=int(name[-6:-4]);pieces.append((part,raw))
                rows.append(dict(part=part,raw=raw,sha256=hashlib.sha256(raw).hexdigest(),physical=physical,
                                 immutable=stat.S_IMODE(info.st_mode)==0o400))
                self.directory_guard()
            finally:
                if not owner.close():self.uncertain.append(owner)
        expected=self.pending['literal']
        contiguous=all(part==index for index,(part,_raw) in enumerate(pieces))
        raw=b''.join(piece for _part,piece in pieces)
        complete=False
        if expected is None:
            complete=contiguous and len(rows)==1 and rows[0]['immutable']
        else:
            exact(expected,{'assetsRawLiteralVersion','scopeSha256','read','bytes','sha256','parts'})
            need(type(expected['assetsRawLiteralVersion']) is int and expected['assetsRawLiteralVersion']==1
                 and expected['scopeSha256']==self.history.scope and expected['read']==self.pending['read']
                 and integer(expected.get('bytes'),0,self.pending['limit'])
                 and type(expected.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}',expected['sha256']))
            complete=contiguous and len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
        self.verify()
        return dict(historicalOnly=True,qualifiedOriginal=False,liveAdoptionPermitted=False,
            completeBytes=bool(complete),raw=raw if complete else None,segments=rows)
