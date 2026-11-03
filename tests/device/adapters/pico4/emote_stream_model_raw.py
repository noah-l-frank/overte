"""Same original Pico model reply file, binary and durable before its parser."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import shlex
import stat
import subprocess
import uuid

from adapters.android_snapshot_files import original_stat
from adapters.native_avatar_render import LIMIT
from adapters.native_feature_observation import need,number,integer
from adapters.pico4.emote_model_draws import PicoWorldModelDraws,command as draw_command
from adapters.pico4.emote_stream_wire import HEADER,FOOTER,_BODY,physical_stamp
from adapters.pico4.probe_originals import same_callable,strict_json
from adapters.script_journey.history import canonical

VERSION=1
WIRE_LIMIT=LIMIT+1+4096
SCRIPT='stream_path=files/overte-e2e/feature-pico-world-model-draws.json\n'+_BODY.replace('CHECK_SAMPLE','')
CAPTURE_CHECK='[ ! -e files/overte-e2e/feature-pico-emote-capture-pending.json ] && [ ! -L files/overte-e2e/feature-pico-emote-capture-pending.json ] || exit 1'
SCRIPT2='stream_path=files/overte-e2e/feature-pico-world-model-draws.json\n'+_BODY.replace('CHECK_SAMPLE',CAPTURE_CHECK)
UNCONFIRMED=[]


def literal(wire,nonce):
    """Same stream-wire grammar; preserve the EXISTING model262144B limit."""
    need(type(wire) is bytes and len(wire)<=WIRE_LIMIT)
    prefix=HEADER+nonce.encode()+b'\n';need(wire.startswith(prefix))
    parent,separator,remaining=wire[len(prefix):].partition(b'\n');need(separator and 0<len(parent)<=512)
    description,separator,body=remaining.partition(b'\n');need(separator and 0<len(description)<=512)
    suffix=FOOTER+nonce.encode()+b'\n'+parent+b'\n'+description+b'\n';need(body.endswith(suffix));body=body[:-len(suffix)]
    fields=description.decode('ascii').split();need(len(fields)==12 and fields[5].isdigit());size=int(fields[5])
    need(original_stat(description.decode(),size) and stat.S_ISREG(int(fields[2],16))
        and stat.S_IMODE(int(fields[2],16))==0o600 and len(body)==min(size,LIMIT+1) and size<=LIMIT)
    root=parent.decode('ascii').split();need(len(root)==12 and root[4].isdigit() and root[5].isdigit())
    lexical=list(root);lexical[4]='1'
    need(int(root[4])>=1 and original_stat(' '.join(lexical),int(root[5])) and stat.S_ISDIR(int(root[2],16))
        and stat.S_IMODE(int(root[2],16))==0o700 and root[3]==fields[3])
    return body,(parent.decode('ascii'),description.decode('ascii'))


class PicoEmoteStreamModelRaw:
    def __init__(self,capture,reader):
        need(type(reader) is PicoWorldModelDraws and reader.pid==capture.pid and not reader.ios and reader.last is None)
        self.capture=self._capture=capture;self.reader=self._reader=reader
        self.source=self._source=capture.source;self.archive=self._archive=capture.cycle.originals.archive
        self.binary=self._binary=self.source.wire.adapter.adb.execute_bytes
        self.target=self._target=self.source.wire.target
        self.native_guard=self._native_guard=reader.guard;self.send=self._send=reader.send
        self.clock=self._clock=reader.clock_ms;self.monotonic=self._monotonic=reader.monotonic
        self.token=None;self.request=None;self.started=None;self.native_epoch=None;self.last=None;self.failed=False
        self.call=self._call=None
        self.guard_hook=self.guard;self.send_hook=self.dispatch;self.get_hook=self.acquire
        reader.guard=self.guard_hook;reader.send=self.send_hook;reader.original=self.get_hook

    def identity(self):
        need(not self.failed and self.capture is self._capture and self.reader is self._reader and self.source is self._source
            and self.archive is self._archive and self.archive is self.capture.cycle.originals.archive and self.target==self._target
            and same_callable(self.binary,self._binary) and same_callable(self.source.wire.adapter.adb.execute_bytes,self._binary)
            and self.reader.guard is self.guard_hook and self.reader.send is self.send_hook and self.reader.original is self.get_hook
            and same_callable(self.reader.clock_ms,self._clock) and same_callable(self.reader.monotonic,self._monotonic)
            and same_callable(self.send,self._send) and same_callable(self.native_guard,self._native_guard)
            and same_callable(self.clock,self._clock) and same_callable(self.monotonic,self._monotonic)
            and self.call is self._call)
        if self.call is None:need(self.started is None and self.native_epoch is None and self.request is None)
        else:need(self.call==(self.started,self.native_epoch,canonical(self.request)))

    def guard(self):
        self.identity();self.capture.bound();need(self.native_guard() is not False);self.capture.bound();self.identity()
        if self.started is not None:
            now=self.monotonic();epoch=self.clock()
            need(number(now,self.started,self.started+5) and integer(epoch,self.native_epoch)
                and max((now-self.started)*1000,epoch-self.native_epoch)<5000)
        return True

    def reservation(self):
        self.guard();need(self.token is None and self.request is not None);self.nonce=uuid.uuid4().hex
        self.token=self.archive.reserve('emote-stream-model',dict(self.request,wireRead=self.nonce),WIRE_LIMIT,side_bytes=8*WIRE_LIMIT)
        self.guard()

    def dispatch(self,request):
        try:
            self.guard();need(self.request is None);draw_command(request)
            self.started=self.monotonic();self.native_epoch=self.clock();self.request=deepcopy(request)
            self.call=self._call=(self.started,self.native_epoch,canonical(self.request))
            self.capture.remember('modelRequest',request);self.reservation()
            send_token=self.archive.reserve('emote-stream-model',dict(request,transport='send-return'),LIMIT)
            self.guard();returned=self.send(request)
            if returned is not None and (type(returned) not in (str,bytes) or len(returned.encode('utf-8') if type(returned) is str else returned)>LIMIT):
                UNCONFIRMED.append((self.archive,send_token,returned));need(False)
            self.archive.retain(send_token,returned);need(returned is None);self.guard()
        except BaseException:self.failed=True;raise

    def retain(self,token,wire):
        if type(wire) is not bytes or len(wire)>WIRE_LIMIT:UNCONFIRMED.append((self.archive,token,wire));need(False)
        return self.archive.retain(token,wire)

    def acquire(self):
        try:
            self.guard()
            if self.token is None:self.reservation()
            token,nonce=self.token,self.nonce
            selected_script=SCRIPT if getattr(self.capture.cycle,'capacity',None) is None else SCRIPT2
            remote=' '.join(shlex.quote(value) for value in ('run-as','org.overte.pico','sh','-c',selected_script,
                'overte-pico-emote-model',nonce,str(LIMIT+1)))
            self.guard();remaining=self.started+5-self.monotonic();need(0<remaining<=5)
            try:wire=self.binary(['exec-out',remote],target=self.target,timeout=remaining)
            except BaseException as error:
                cause=error if isinstance(error,subprocess.TimeoutExpired) else error.__cause__
                if isinstance(cause,subprocess.TimeoutExpired) and type(cause.output) is bytes:self.retain(token,cause.output)
                raise
            reference=self.retain(token,wire);self.token=None
            self.last=dict(picoEmoteStreamModelOriginalVersion=VERSION,rawReference=reference,wireNonce=nonce)
            self.guard();body,physical=literal(wire,nonce)
            need(physical_stamp(physical[0])[:5]==self.source.state['nativeRootNode'])
            return body.decode('utf-8',errors='strict')
        except BaseException:self.failed=True;raise

    def original(self,reference):
        self.capture.candidate();need(type(reference) is dict and set(reference)=={
            'picoEmoteStreamModelOriginalVersion','rawReference','wireNonce'}
            and type(reference['picoEmoteStreamModelOriginalVersion']) is int and reference['picoEmoteStreamModelOriginalVersion']==VERSION)
        wire=self.archive.literal(reference['rawReference']);body,physical=literal(wire,reference['wireNonce'])
        need(physical_stamp(physical[0])[:5]==self.source.state['nativeRootNode']);value=strict_json(body)
        self.capture.candidate();return value
