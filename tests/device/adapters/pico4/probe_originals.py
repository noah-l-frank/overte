"""Bounded original Pico probe bytes through the existing SDK reader.

The fixed read-only command returns a bounded prefix and actual before/after
file metadata. Every obtained wire return is archived before framing, UTF8 or
JSON validation. An oversized prefix is never a complete probe original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import shlex
import stat
import subprocess
import time
import uuid

from adapters.android.adapter import ANDROID_DEBUG_PROBE,AndroidAdapter
from adapters.android_snapshot_files import original_stat
from adapters.native_feature_observation import integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.script_journey.history import canonical

VERSION=1
LIMIT=262144
WIRE_LIMIT=LIMIT+1+4096
HEADER=b'OVT_PICO_PROBE_BYTES_V1\n'
FOOTER=b'\nOVT_PICO_PROBE_BYTES_END_V1 '
UNCONFIRMED_RETURNS=[]

# The framing/quoted fixed command follows AndroidSnapshotFiles. exec-out does
# not supply remote exit status; the footer exists only after successful read
# and unchanged named metadata. No path, package or wanted result is supplied
# by a feature request. The random read nonce cannot be inferred from the file.
SCRIPT=r'''
probe_path=files/overte-e2e/overte-probe.json
[ -d files ] && [ ! -L files ] || exit 1
[ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
[ -f "$probe_path" ] && [ ! -L "$probe_path" ] || exit 1
[ "$(stat -c %h "$probe_path")" = 1 ] || exit 1
[ "$(stat -c %u "$probe_path")" = "$(id -u)" ] || exit 1
probe_before=$(stat -c '%d %i %f %u %h %s %y %z' "$probe_path") || exit 1
printf 'OVT_PICO_PROBE_BYTES_V1\n%s\n%s\n' "$1" "$probe_before"
head -c "$2" "$probe_path" || exit 1
probe_after=$(stat -c '%d %i %f %u %h %s %y %z' "$probe_path") || exit 1
[ ! -L "$probe_path" ] && [ "$probe_before" = "$probe_after" ] || exit 1
printf '\nOVT_PICO_PROBE_BYTES_END_V1 %s\n%s\n' "$1" "$probe_after"
'''.strip()


def same_callable(first,second):
    if hasattr(first,'__func__'):
        return getattr(first,'__func__',None) is getattr(second,'__func__',None) and first.__self__ is second.__self__
    return first is second


def literal(wire,nonce):
    need(type(wire) is bytes and len(wire)<=WIRE_LIMIT)
    prefix=HEADER+nonce.encode('ascii')+b'\n';need(wire.startswith(prefix))
    before,separator,body=wire[len(prefix):].partition(b'\n');need(separator==b'\n' and 0<len(before)<=512)
    suffix=FOOTER+nonce.encode('ascii')+b'\n'+before+b'\n';need(body.endswith(suffix))
    body=body[:-len(suffix)];description=before.decode('ascii');fields=description.split()
    need(len(fields)==12 and fields[5].isdigit());size=int(fields[5])
    need(original_stat(description,size));mode=int(fields[2],16)
    need(stat.S_ISREG(mode) and stat.S_IMODE(mode)==0o600
        and len(body)==min(size,LIMIT+1))
    # The overrun's real bounded wire/prefix is already durable. Its missing
    # tail and full-file digest are unknown and cannot enter the SDK parser.
    need(size<=LIMIT and len(body)<=LIMIT)
    return body


def strict_json(raw):
    def pairs(items):
        value={}
        for key,child in items:need(key not in value);value[key]=child
        return value
    def invalid(_value):need(False)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)


class PicoProbeOriginals:
    def __init__(self,adapter,target,archive,guard,*,role,monotonic=time.monotonic):
        need(adapter.kind=='pico' and adapter.profile['package']=='org.overte.pico'
            and type(target) is str and target and type(archive) is AudioRawArchive
            and role in ('primary','actor') and callable(guard) and callable(monotonic)
            and getattr(adapter.read_probe_snapshot,'__func__',None) is AndroidAdapter.read_probe_snapshot)
        self.adapter=self._adapter=adapter;self.target=self._target=target
        self.archive=self._archive=archive;self.guard=self._guard=guard
        self.monotonic=self._monotonic=monotonic;self.role=self._role=role
        self.reader=self._reader=adapter.read_probe_snapshot
        self.binary=self._binary=adapter.adb.execute_bytes
        self.failed=False;self.active=False;self.started=self.previous=None
        self.last_body=self._last_body=None;self.receipts=self._receipts=()
        self.call=self._call=None;self.clock_seal=None

    def identity(self):
        need(not self.failed and self.active and self.adapter is self._adapter and self.target==self._target
            and self.archive is self._archive and self.guard is self._guard and self.monotonic is self._monotonic
            and self.role==self._role and self.adapter.kind=='pico'
            and self.adapter.profile['package']=='org.overte.pico'
            and self.call is self._call and type(self.call) is tuple
            and self.started==self.call[0] and type(self.after) is type(self.call[1]) and self.after==self.call[1]
            and self.previous==self.clock_seal[0] and self.call is self.clock_seal[1]
            and self.receipts is self._receipts and type(self.receipts) is tuple
            and self.last_body is self._last_body
            and same_callable(self.reader,self._reader)
            and same_callable(self.adapter.read_probe_snapshot,self._reader)
            and same_callable(self.binary,self._binary)
            and same_callable(self.adapter.adb.execute_bytes,self._binary))
    def bound(self):
        self.identity();need(self.guard() is not False);self.identity()
        now=self.monotonic();self.identity()
        need(number(now,self.previous,self.call[0]+5) and now-self.call[0]<5)
        self.previous=now;self.clock_seal=(now,self.call);return now

    def save_wire(self,token,wire):
        if type(wire) is not bytes or len(wire)>WIRE_LIMIT:
            UNCONFIRMED_RETURNS.append((self.archive,token,wire));need(False)
        reference=self.archive.retain(token,wire)
        need(self.receipts is self._receipts and type(self.receipts) is tuple)
        self.receipts=self._receipts=self.receipts+(canonical(reference),)
        return reference

    def raw(self,target,package,path,**options):
        need(target==self.target and package=='org.overte.pico' and path==ANDROID_DEBUG_PROBE
            and options=={'attempts':1})
        self.bound();need(len(self.receipts)<1024);nonce=uuid.uuid4().hex
        command=dict(picoProbeRawReadVersion=VERSION,commandId=nonce,operation='read-existing-probe',
            role=self.role,afterSequence=self.after,maximumBytes=LIMIT,
            targetFingerprint=hashlib.sha256(('org.overte.pico\0'+self.target).encode()).hexdigest())
        token=self.archive.reserve('sdk-probe-'+self.role,command,WIRE_LIMIT,side_bytes=8*WIRE_LIMIT)
        remote=' '.join(shlex.quote(value) for value in
            ('run-as',package,'sh','-c',SCRIPT,'overte-pico-probe',nonce,str(LIMIT+1)))
        now=self.bound()
        try:
            wire=self.binary(['exec-out',remote],target=self.target,
                timeout=min(5,self.started+5-now))
        except BaseException as error:
            cause=error.__cause__
            if isinstance(cause,subprocess.TimeoutExpired) and type(cause.output) is bytes:
                self.save_wire(token,cause.output)
            raise
        # Retain first, including an empty, malformed, partial or late return.
        # This deliberately uses only the archive's original host/OFD authority.
        self.save_wire(token,wire);self.bound()
        self.last_body=self._last_body=literal(wire,nonce)
        return self.last_body.decode('utf-8',errors='strict')

    def read(self,after_sequence=None):
        if self.active:self.failed=True;need(False)
        need(not self.active and not self.failed and (after_sequence is None or integer(after_sequence,0)))
        self.active=True;self.after=after_sequence;self.last_body=self._last_body=None
        self.started=self.previous=self.monotonic();before=len(self.receipts)
        self.call=self._call=(self.started,after_sequence);self.clock_seal=(self.previous,self.call)
        try:
            self.bound()
            value=self.reader(self.target,'org.overte.pico',after_sequence,raw_reader=self.raw)
            self.bound();need(len(self.receipts)>before and self.last_body is not None)
            original=strict_json(self.last_body);need(type(original) is dict and type(value) is dict
                and canonical(original)==canonical(value))
            self.bound();return value
        except BaseException:
            self.failed=True
            raise NativeUIError('Original bounded Pico probe is unavailable; source ownership remains') from None
        finally:self.active=False
