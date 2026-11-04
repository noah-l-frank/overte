"""Bounded literal storage before Assets JSON interpretation; no source authority.

The enclosing Prefix2 owns durable intent and the original lock. Binary leaves
reuse the existing immutable original-file windows and original directory OFD.
No cold adoption, unlink, input, candidate query or clock renewal exists here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import re
import stat

from adapters.chat_journey.archive_file import ClosedOriginalFile, signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_fd_owner import OriginalDescriptor, require_directory
from adapters.native_feature_observation import integer, need
from adapters.script_journey.history import canonical, MAX_FRAMES, MAX_RAW, same

VERSION = 1
PART_BYTES = 65536
MAX_LITERAL = 4*1024*1024
META_RESERVE = 65536


def compact(reference):
    if reference.get('assetsRawLiteralVersion')==2:
        from adapters.pico4.assets_raw_ranges import reference as validate
        validate(reference,reference['scopeSha256']);return dict(assetsRawCompactVersion=2,read=reference['read'],
            sha256=reference['sha256'],tailBundle=reference['tailBundle'])
    return dict(assetsRawCompactVersion=1, scopeSha256=reference['scopeSha256'], read=reference['read'],
        bytes=reference['bytes'], sha256=reference['sha256'],
        parts=[[part['bytes'], part['sha256'], part['physical']] for part in reference['parts']])


def expanded(value, name):
    if type(value) is dict and value.get('assetsRawCompactVersion')==2:
        from adapters.pico4.assets_raw_ranges import compact_reference
        compact_reference(value);return deepcopy(value)
    need(type(value) is dict and set(value)=={'assetsRawCompactVersion','scopeSha256','read','bytes','sha256','parts'}
         and type(value['assetsRawCompactVersion']) is int and value['assetsRawCompactVersion']==1
         and integer(value['read'],0,MAX_FRAMES-1) and type(value['parts']) is list and len(value['parts'])<=64)
    parts=[]
    for index,part in enumerate(value['parts']):
        need(type(part) is list and len(part)==3)
        parts.append(dict(name=name+f'.child-raw-{value["read"]:03d}-{index:02d}.bin',
            bytes=part[0],sha256=part[1],physical=part[2]))
    return dict(assetsRawLiteralVersion=1,scopeSha256=value['scopeSha256'],read=value['read'],
        bytes=value['bytes'],sha256=value['sha256'],parts=parts)


def quoted_bytes(text):
    """Exact ensure_ascii JSON string length without constructing that string."""
    need(type(text) is str)
    if str.isascii(text):
        count = 2+len(text)+str.count(text, '"')+str.count(text, '\\')
        if not text or str.isprintable(text):
            return count
        for match in re.finditer(r'[\x00-\x1f\x7f]', text):
            count += 1 if match[0] in '\b\f\n\r\t' else 5
        return count
    count = 2
    for character in text:
        code = ord(character)
        if character in ('"', '\\', '\b', '\f', '\n', '\r', '\t'):
            count += 2
        elif code < 32 or 127 <= code <= 65535:
            count += 6
        elif code > 65535:
            count += 12
        else:
            count += 1
    return count


class AssetsRawArchive:
    def __new__(cls,owner):
        if owner.scope.get('assetsRawOriginalLayoutVersion')==2:
            from adapters.pico4.assets_raw_ranges import AssetsRawRanges
            return AssetsRawRanges(owner)
        return super().__new__(cls)

    def __init__(self, owner):
        need(type(owner.scope.get('assetsPrefixVersion')) is int and owner.scope['assetsPrefixVersion'] in (2,3))
        self.owner, self.scope = owner, canonical(owner.scope)
        self.scope_sha = json_digest(owner.scope)
        self.path = owner.store.path
        self.directory = OriginalDescriptor(self.path.parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.original_directory = self.directory
        self.files, self.rows, self.active = {}, [], None
        self.uncertain_writers=[]
        self.reads, self.failed = 0, False
        self.verify()

    def guard(self, *, held=True):
        if held:
            self.owner.lock.assert_held()
        getattr(self.owner,'archival_identity',self.owner.identity)()
        need(self.owner.store.path == self.path and canonical(self.owner.scope) == self.scope
             and json_digest(self.owner.scope) == self.scope_sha and self.directory is self.original_directory)
        require_directory(self.directory, self.path.parent)

    def verify(self, *, held=True):
        self.guard(held=held)
        for name, original in self.files.items():
            need(signature((self.path.parent/name).lstat()) == original.stamp)
        prefix = self.path.name+'.child-raw-'
        with os.scandir(self.path.parent) as entries:
            names = set()
            for index, entry in enumerate(entries):
                need(index < 4096)
                if entry.name.startswith(prefix):
                    names.add(entry.name)
        need(names == set(self.files))

    def _save(self, value):
        self.owner.state['pendingRawRead'] = deepcopy(value)
        self.owner.save()

    def reserve(self, role, command, limit=MAX_LITERAL):
        try:
            self.verify()
            need(not self.failed and self.active is None and self.owner.disk['pendingRawRead'] is None
                 and integer(limit, 1, MAX_LITERAL) and type(role) is str and re.fullmatch('[a-z-]{1,32}', role))
            json_digest(command)
            command_size = len(canonical(command))
            need(type(command) is dict and command_size <= META_RESERVE-4096 and self.reads < MAX_FRAMES)
            parts = (limit+PART_BYTES-1)//PART_BYTES
            current = self.owner.bill()
            # Guaranteed literal storage comes first. Native JSON/history
            # expansion is independently preflighted only AFTER this copy.
            need(current['frames']+parts+4 <= MAX_FRAMES
                 and current['decodedBytes']+limit+3*META_RESERVE <= MAX_RAW
                 and current.get('storedBytes', 0)+limit+5*META_RESERVE <= MAX_RAW)
            self.active = dict(assetsRawReadVersion=VERSION, scopeSha256=self.scope_sha, read=self.reads,
                role=role, commandSha256=json_digest(command), commandBytes=command_size,
                limit=limit, reservedParts=parts, state='reserved', literal=None)
            # Reserve the actual root's eventual full physical reference too;
            # a large stage command is already retained by its source intent.
            # Do not duplicate that command in the raw reservation.
            maximum = dict(assetsRawLiteralVersion=VERSION, scopeSha256=self.scope_sha, read=self.reads,
                bytes=limit, sha256='f'*64, parts=[dict(name=self.path.name+f'.child-raw-{self.reads:03d}-{index:02d}.bin',
                bytes=PART_BYTES, sha256='f'*64, physical=[2**64-1]*8) for index in range(parts)])
            rows=[*self.owner.state['rawReads'],dict(role=role,rawOriginal=compact(maximum))]
            prospective = dict(self.owner.state, pendingRawRead=None,rawReads=rows)
            # The final CAS only adds the <=3-digit receipt index and may use
            # childSource rather than role. All physical fields are already
            # reserved at their complete unsigned64-bit widths above.
            need(len(canonical(prospective))+64 <= META_RESERVE)
            self._save(self.active)
            return deepcopy(self.active)
        except BaseException:
            self.failed = True
            raise

    def retain(self, text):
        try:
            need(type(text) is str)
            return self._retain_bytes(text.encode('utf-8'))
        except BaseException:
            self.failed=True;raise

    def retain_bytes(self, raw):
        # Only explicit Prefix3 accepts actual backend-file/HTTP binary bytes.
        # Prefix2 transport strings retain their original UTF-8 interpretation.
        try:
            need(self.owner.scope['assetsPrefixVersion']==3 and type(raw) is bytes)
            return self._retain_bytes(raw)
        except BaseException:
            self.failed=True;raise

    def _retain_bytes(self, raw):
        try:
            self.verify()
            need(not self.failed and self.active is not None and self.active['state'] == 'reserved' and type(raw) is bytes)
            need(len(raw) <= self.active['limit'])
            literal = dict(assetsRawLiteralVersion=VERSION, scopeSha256=self.scope_sha, read=self.reads,
                           bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), parts=[])
            self.active.update(state='retaining', literal=deepcopy(literal))
            if len(raw)>PART_BYTES:
                self._save(self.active)
            for offset in range(0, len(raw), PART_BYTES):
                part = raw[offset:offset+PART_BYTES]
                name = self.path.name+f'.child-raw-{self.reads:03d}-{offset//PART_BYTES:02d}.bin'
                self.guard()
                # Reuse the original-pair primitive for the writer as well.
                # No fdopen/finally may close a same-file recycled foreign FD.
                writer=OriginalDescriptor('/proc/self/fd/'+str(self.directory.fd)+'/'+name,
                    os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    self.guard();writer.require(writer.fd);os.fchmod(writer.fd,0o600)
                    offset_written=0
                    while offset_written<len(part):
                        writer.require(writer.fd);written=os.write(writer.fd,part[offset_written:])
                        writer.require(writer.fd);need(type(written) is int and written>0)
                        offset_written+=written
                    os.fchmod(writer.fd,0o400);writer.require(writer.fd);os.fsync(writer.fd)
                    writer.require(writer.fd);physical=signature(os.fstat(writer.fd));self.guard()
                    need(writer.close())
                except BaseException:
                    if not writer.close():self.uncertain_writers.append(writer)
                    raise
                original = ClosedOriginalFile(self.path.parent/name, 0o400, self.guard)
                actual, observed = original.read()
                need(actual == part and observed == physical)
                self.files[name] = original
                literal['parts'].append(dict(name=name, bytes=len(part), sha256=hashlib.sha256(part).hexdigest(), physical=observed))
            os.fsync(self.directory.fd)
            self.active.update(state='sealed', literal=deepcopy(literal))
            self.verify()
            return deepcopy(literal)
        except BaseException:
            self.failed = True
            raise

    def clear_intent(self):
        """Only inside the final parent CAS sealing its immutable raw reference."""
        need(not self.failed and self.active is not None and self.active['state'] == 'sealed')
        self.owner.state['pendingRawRead'] = None

    def delivered(self, index):
        try:
            self.verify()
            need(not self.failed and self.active is not None and self.active['state'] == 'sealed'
                 and self.owner.disk['pendingRawRead'] is None)
            value = self.owner.raw_record(index)
            need(same(expanded(value.get('rawOriginal'),self.path.name), self.active['literal']))
            self.rows.append(deepcopy(self.active['literal']))
            self.reads += 1
            self.active = None
        except BaseException:
            self.failed = True
            raise

    def parser_capacity(self, text, command):
        # No JSON serialization of the untrusted literal occurs here. A4MiB
        # NUL reply is safely sealed first, then its24MiB quoted form is refused.
        self.verify()
        need(not self.failed and self.rows and type(text) is str)
        required = quoted_bytes(text)+len(canonical(command))+4096
        try:
            need(self.owner.bill()['decodedBytes']+required <= MAX_RAW)
        except BaseException:
            self.failed = True
            raise
        return required

    def literal(self, reference):
        self.verify()
        need(type(reference) is dict and reference.get('assetsRawLiteralVersion') == VERSION
             and any(same(reference, row) for row in self.rows))
        pieces = []
        for part in reference['parts']:
            original = self.files[part['name']]
            raw, physical = original.read()
            need(physical == part['physical'] and len(raw) == part['bytes']
                 and hashlib.sha256(raw).hexdigest() == part['sha256'])
            pieces.append(raw)
        raw = b''.join(pieces)
        need(len(raw) == reference['bytes'] and hashlib.sha256(raw).hexdigest() == reference['sha256'])
        return raw

    def bill(self):
        # Include uncertain/partial actual leaves too. Counting does not admit
        # them: verify() still forbids any unknown namespace before a query.
        count=total=0
        with os.scandir(self.path.parent) as entries:
            for index,entry in enumerate(entries):
                need(index<4096)
                if entry.name.startswith(self.path.name+'.child-raw-'):
                    info=entry.stat(follow_symlinks=False)
                    need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1
                         and stat.S_IMODE(info.st_mode) in (0o400,0o600) and 0<=info.st_size<=PART_BYTES)
                    count+=1;total+=info.st_size
        return dict(parts=count, bytes=total)

    def close_host(self):
        # No uncertain foreign descriptor is forced closed. No original file is
        # removed, and this host-resource result is not feature cleanup.
        return all([original.close() for original in self.files.values()]+[self.directory.close()]
            +[writer.close() for writer in self.uncertain_writers])
