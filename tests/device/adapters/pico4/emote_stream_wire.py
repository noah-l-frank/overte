"""Fixed-file Source4 transport; every acquired byte precedes its parser.

The existing range archive owns original literals. This module supplies no
sample, native clock anchor, wanted pose or replay authority. Pending/partial
transport work is terminal and remains in that SAME archive.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import datetime
import shlex
import stat
import subprocess
import time
import uuid

from adapters.android_snapshot_files import original_stat
from adapters.native_feature_observation import integer,need,number
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4.emote_stream_frame import CONTROL_LIMIT,FRAME_LIMIT,control_command
from adapters.pico4.probe_originals import same_callable,strict_json
from adapters.script_journey.history import canonical

VERSION=1
HEADER=b'OVT_PICO_EMOTE_STREAM_BYTES_V1\n'
FOOTER=b'\nOVT_PICO_EMOTE_STREAM_BYTES_END_V1 '
UNCONFIRMED=[]

# Both scripts contain fixed paths. Their only arguments are the random read
# nonce and bounded byte count. A sample with an issued native write marker,
# a legacy file, link, changed metadata or missing success footer is refused.
_BODY=r'''
[ -d files ] && [ ! -L files ] || exit 1
[ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
[ "$(stat -c %a files/overte-e2e)" = 700 ] || exit 1
[ "$(stat -c %u files/overte-e2e)" = "$(id -u)" ] || exit 1
CHECK_SAMPLE
[ -f "$stream_path" ] && [ ! -L "$stream_path" ] || exit 1
[ "$(stat -c %h "$stream_path")" = 1 ] || exit 1
[ "$(stat -c %a "$stream_path")" = 600 ] || exit 1
[ "$(stat -c %u "$stream_path")" = "$(id -u)" ] || exit 1
stream_before=$(stat -c '%d %i %f %u %h %s %y %z' "$stream_path") || exit 1
stream_root_before=$(stat -c '%d %i %f %u %h %s %y %z' files/overte-e2e) || exit 1
printf 'OVT_PICO_EMOTE_STREAM_BYTES_V1\n%s\n%s\n%s\n' "$1" "$stream_root_before" "$stream_before"
head -c "$2" "$stream_path" || exit 1
stream_after=$(stat -c '%d %i %f %u %h %s %y %z' "$stream_path") || exit 1
stream_root_after=$(stat -c '%d %i %f %u %h %s %y %z' files/overte-e2e) || exit 1
[ ! -L "$stream_path" ] && [ "$stream_before" = "$stream_after" ] || exit 1
[ ! -L files/overte-e2e ] && [ "$stream_root_before" = "$stream_root_after" ] || exit 1
CHECK_SAMPLE
printf '\nOVT_PICO_EMOTE_STREAM_BYTES_END_V1 %s\n%s\n%s\n' "$1" "$stream_root_after" "$stream_after"
'''.strip()
_SAMPLE=r'''[ ! -e files/overte-e2e/feature-pico-remote-avatar-stream-pending.json ] && [ ! -L files/overte-e2e/feature-pico-remote-avatar-stream-pending.json ] || exit 1
[ ! -e files/overte-e2e/feature-pico-remote-avatar.json ] && [ ! -L files/overte-e2e/feature-pico-remote-avatar.json ] || exit 1'''
SCRIPTS={
    'sample':"stream_path=files/overte-e2e/feature-pico-remote-avatar-stream.json\n"+_BODY.replace('CHECK_SAMPLE',_SAMPLE),
    'control':"stream_path=files/overte-e2e/feature-pico-remote-avatar-stream-control.json\n"+_BODY.replace('CHECK_SAMPLE',''),
}
LIMITS={'sample':FRAME_LIMIT,'control':CONTROL_LIMIT}


def literal(wire,nonce,limit):
    return wire_original(wire,nonce,limit)[0]


def wire_original(wire,nonce,limit):
    need(type(wire) is bytes and integer(limit,1,FRAME_LIMIT) and len(wire)<=limit+1+4096)
    prefix=HEADER+nonce.encode('ascii')+b'\n';need(wire.startswith(prefix))
    root,separator,remainder=wire[len(prefix):].partition(b'\n');need(separator==b'\n' and 0<len(root)<=512)
    before,separator,body=remainder.partition(b'\n');need(separator==b'\n' and 0<len(before)<=512)
    suffix=FOOTER+nonce.encode('ascii')+b'\n'+root+b'\n'+before+b'\n';need(body.endswith(suffix));body=body[:-len(suffix)]
    fields=before.decode('ascii').split();need(len(fields)==12 and fields[5].isdigit());size=int(fields[5])
    need(original_stat(before.decode('ascii'),size));mode=int(fields[2],16)
    need(stat.S_ISREG(mode) and stat.S_IMODE(mode)==0o600 and len(body)==min(size,limit+1))
    parent=root.decode('ascii').split();need(len(parent)==12 and parent[4].isdigit() and parent[5].isdigit())
    # Reuse the exact original-stat lexical validator; only the directory's
    # actual link count differs from its regular-file rule.
    lexical=list(parent);lexical[4]='1'
    need(int(parent[4])>=1 and original_stat(' '.join(lexical),int(parent[5]))
        and stat.S_ISDIR(int(parent[2],16)) and stat.S_IMODE(int(parent[2],16))==0o700 and parent[3]==fields[3])
    # A bounded overrun is already retained, but it cannot become a complete
    # original, JSON packet or retry/adoption authorization.
    need(size<=limit and len(body)<=limit);return body,(root.decode('ascii'),before.decode('ascii'))


def physical_stamp(description):
    fields=description.split();need(len(fields)==12 and fields[5].isdigit())
    def epoch_ns(date,clock,zone):
        second,fraction=clock.split('.');need(len(fraction)==9 and fraction.isdigit())
        stamp=datetime.datetime.strptime(date+' '+second+' '+zone,'%Y-%m-%d %H:%M:%S %z')
        delta=stamp-datetime.datetime(1970,1,1,tzinfo=datetime.timezone.utc)
        return str((delta.days*86400+delta.seconds)*1000000000+int(fraction))
    return fields[:2]+[str(int(fields[2],16))]+fields[3:6]+[
        epoch_ns(*fields[6:9]),epoch_ns(*fields[9:12])]


class _SendFence:
    def __init__(self,owner):self.owner=owner
    def check(self):self.owner.bound()


class PicoEmoteStreamWire:
    """One resolved role transport, sharing the compound range/archive bill."""
    def __init__(self,adapter,target,native,archive,guard,*,role,monotonic=time.monotonic):
        need(adapter.kind=='pico' and adapter.profile['package']=='org.overte.pico'
            and type(target) is str and target and type(archive) is AudioRawArchive
            and role in ('primary','actor') and all(callable(fn) for fn in (guard,monotonic,native.send,native.clock_ms,native.guard))
            and getattr(native,'phase_fence',None) is None)
        self.adapter=self._adapter=adapter;self.target=self._target=target;self.native=self._native=native
        self.archive=self._archive=archive;self.guard=self._guard=guard;self.monotonic=self._monotonic=monotonic
        self.role=self._role=role;self.binary=self._binary=adapter.adb.execute_bytes
        self.send=self._send=native.send;self.clock_ms=self._clock_ms=native.clock_ms
        self.native_guard=self._native_guard=native.guard
        self.fence=self._fence=_SendFence(self);native.phase_fence=self.fence
        self.failed=False;self.active=False;self.started=self.previous=self.native_epoch=None
        self.call=self._call=self.clock_seal=None
        self.references=self._references=();self.last_reference=self.last_nonce=self.last_physical=None;self.control_count=0

    def identity(self):
        need(not self.failed and self.active and self.adapter is self._adapter and self.target==self._target
            and self.native is self._native and self.archive is self._archive and self.guard is self._guard
            and self.monotonic is self._monotonic and self.role==self._role
            and self.adapter.kind=='pico' and self.adapter.profile['package']=='org.overte.pico'
            and self.native.phase_fence is self.fence is self._fence
            and self.fence.owner is self and self.references is self._references
            and self.call is self._call and type(self.call) is tuple
            and self.call==(self.started,self.window,self.native_epoch)
            and self.clock_seal==(self.previous,self.call) and self.clock_seal[1] is self.call
            and all(same_callable(first,second) for first,second in (
                (self.binary,self._binary),(self.adapter.adb.execute_bytes,self._binary),
                (self.send,self._send),(self.native.send,self._send),(self.clock_ms,self._clock_ms),
                (self.native.clock_ms,self._clock_ms),(self.native.guard,self._native_guard))))

    def bound(self):
        self.identity();need(self.guard() is not False);self.identity()
        epoch=self.clock_ms();now=self.monotonic();self.identity()
        need(integer(epoch,self.native_epoch) and number(now,self.previous,self.started+self.window)
            and max((now-self.started)*1000,epoch-self.native_epoch)<self.window*1000)
        self.previous=now;self.clock_seal=(now,self.call);return now

    def begin(self,window):
        if self.active:self.failed=True;need(False)
        need(not self.failed and window in (1.5,5));self.active=True;self.window=window
        self.started=self.previous=self.monotonic();self.native_epoch=self.clock_ms()
        self.call=self._call=(self.started,self.window,self.native_epoch);self.clock_seal=(self.previous,self.call);self.bound()

    def retain(self,token,wire):
        if type(wire) is not bytes or len(wire)>token['limit']:
            UNCONFIRMED.append((self.archive,token,wire));need(False)
        # No business/admission guard between actual return and durable raw
        # receipt. The original archive/OFD authority remains independent.
        reference=self.archive.retain(token,wire)
        need(self.references is self._references)
        self.references=self._references=self.references+(canonical(reference),)
        self.last_reference=reference;return reference

    def acquire(self,kind,command,token=None):
        self.bound();need(kind in LIMITS);limit=LIMITS[kind];nonce=uuid.uuid4().hex;self.last_nonce=nonce
        if token is None:
            token=self.archive.reserve('emote-stream-'+self.role,dict(command,wireRead=nonce,wireKind=kind),
                limit+1+4096,side_bytes=8*(limit+1+4096))
        remote=' '.join(shlex.quote(value) for value in ('run-as','org.overte.pico','sh','-c',SCRIPTS[kind],
            'overte-pico-emote-stream',nonce,str(limit+1)))
        now=self.bound()
        try:wire=self.binary(['exec-out',remote],target=self.target,timeout=min(5,self.started+self.window-now))
        except BaseException as error:
            cause=error if isinstance(error,subprocess.TimeoutExpired) else error.__cause__
            if isinstance(cause,subprocess.TimeoutExpired) and type(cause.output) is bytes:self.retain(token,cause.output)
            raise
        self.retain(token,wire);self.bound()
        body,self.last_physical=wire_original(wire,nonce,limit);value=strict_json(body);self.bound();return value

    def read(self):
        try:
            self.begin(5)
            return self.acquire('sample',dict(picoEmoteStreamWireVersion=VERSION,operation='read-current-sample',role=self.role))
        except BaseException:self.failed=True;raise
        finally:self.active=False

    def control(self,request):
        try:
            self.begin(1.5);control_command(request);need(self.control_count<32)
            self.control_count+=1
            # Admission for the ACK literal and the actual send return is
            # durable BEFORE dispatch. No later getter spends that capacity.
            token=self.archive.reserve('emote-stream-'+self.role,request,CONTROL_LIMIT+1+4096,
                side_bytes=8*(CONTROL_LIMIT+1+4096))
            send_token=self.archive.reserve('emote-stream-'+self.role,dict(request,transport='send-return'),1)
            self.bound();returned=self.send(request)
            # Existing native.send is a command publication, not an effect.
            # Only its actual None return is represented; exceptions retain
            # the issued reservations and prohibit replay.
            need(returned is None);self.archive.retain(send_token,None);self.bound()
            return self.acquire('control',request,token)
        except BaseException:self.failed=True;raise
        finally:self.active=False
