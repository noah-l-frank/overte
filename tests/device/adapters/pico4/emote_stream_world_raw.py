"""Exact returned world/storage/inventory literals before existing decoders.

Existing owner callbacks and query algorithms remain in place. The only new
work is guaranteed same-archive capacity before send/get and durable exact
UTF8/bytes retention before any later guard or parser can refuse the return.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import shlex
import subprocess
import uuid

from adapters.pico4.emote_stream_model_raw import literal
from adapters.pico4.emote_stream_wire import _BODY,physical_stamp
from adapters.world_render_evidence import FILE as WORLD_FILE
from adapters.world_render_receipts import INVENTORY_FILE
from adapters.world_render_storage import receipt_file

from adapters.native_feature_observation import need
from adapters.pico4.probe_originals import same_callable
from adapters.script_journey.history import canonical

UNCONFIRMED=[]


def script(name,*,capacity=False):
    # The receipt filename is derived from the actual already-issued command.
    # No requested path is accepted from a caller or a native response.
    need(name in (WORLD_FILE,INVENTORY_FILE) or (name.startswith('world-render-storage-')
        and name==receipt_file(name.removeprefix('world-render-storage-').removesuffix('.json'))))
    check='[ ! -e files/overte-e2e/feature-pico-emote-capture-pending.json ] && [ ! -L files/overte-e2e/feature-pico-emote-capture-pending.json ] || exit 1' if capacity else ''
    return 'stream_path=files/overte-e2e/'+name+'\n'+_BODY.replace('CHECK_SAMPLE',check)


class PicoEmoteStreamWorldRaw:
    def __init__(self,capture):
        self.capture=self._capture=capture;self.archive=self._archive=capture.cycle.originals.archive
        self.bindings=self._bindings=[];self.configs=self._configs=()
        self.binary=self._binary=capture.source.wire.adapter.adb.execute_bytes;self.target=self._target=capture.source.wire.target

    def bind(self,selected,label,limit):
        need(label in ('world','storage','inventory') and not any(row['object'] is selected for row in self.bindings))
        row=dict(object=selected,label=label,limit=limit,send=selected.send,get=selected.original,
            guard=selected.guard,token=None,command=None,reads=0,last=None)
        def send(command):
            self.bound(row);need(row['token'] is None);row['command']=deepcopy(command);row['command_bytes']=canonical(command)
            self.reserve(row)
            if label=='storage' and getattr(self.capture.cycle,'capacity',None) is not None:
                self.capture.cycle.capacity.receipt(self.capture.role,command)
            token=self.archive.reserve('emote-stream-'+label,dict(command,transport='send-return'),262144)
            self.bound(row);returned=row['send'](command)
            if returned is not None and (type(returned) not in (str,bytes) or len(returned.encode('utf-8') if type(returned) is str else returned)>262144):
                UNCONFIRMED.append((self.archive,token,returned));need(False)
            self.archive.retain(token,returned);need(returned is None);self.bound(row)
        def original(*args,**options):
            self.bound(row);need(not options and row['command'] is not None)
            name=WORLD_FILE if label=='world' else INVENTORY_FILE if label=='inventory' else receipt_file(row['command']['commandId'])
            need((label=='storage' and args==(name,)) or (label!='storage' and not args))
            if row['token'] is None:self.reserve(row)
            token,nonce=row['token'],row['nonce'];self.bound(row)
            remote=' '.join(shlex.quote(value) for value in ('run-as','org.overte.pico','sh','-c',script(name,capacity=getattr(self.capture.cycle,'capacity',None) is not None),
                'overte-pico-emote-world',nonce,str(limit+1)))
            remaining=self.capture._component_started+5-self.capture.monotonic();need(0<remaining<=5)
            try:value=self.binary(['exec-out',remote],target=self.target,timeout=remaining)
            except BaseException as error:
                cause=error if isinstance(error,subprocess.TimeoutExpired) else error.__cause__
                if isinstance(cause,subprocess.TimeoutExpired) and type(cause.output) is bytes:self.retain(row,token,cause.output)
                raise
            # No business guard or decoder may hide an already-issued wire.
            row['last']=self.retain(row,token,value);row['token']=None;row['reads']+=1
            self.bound(row);body,physical=literal(value,nonce)
            need(len(body)<=limit and physical_stamp(physical[0])[:5]==self.capture.source.state['nativeRootNode'])
            return body.decode('utf-8',errors='strict')
        row['send_hook'],row['get_hook']=send,original;selected.send=send;selected.original=original
        self.bindings.append(row);self.configs=self._configs=(*self._configs,(row,selected,label,limit,row['send'],row['get'],row['guard']))

    def bound(self,row):
        need(self.capture is self._capture and self.archive is self._archive and self.archive is self.capture.cycle.originals.archive
            and self.bindings is self._bindings and self.configs is self._configs and self.target==self._target
            and same_callable(self.binary,self._binary) and same_callable(self.capture.source.wire.adapter.adb.execute_bytes,self._binary))
        configs=[value for value in self.configs if value[0] is row];need(len(configs)==1);config=configs[0]
        need(any(value is row for value in self.bindings) and row['object'] is config[1] and row['label']==config[2] and row['limit']==config[3]
            and same_callable(row['send'],config[4]) and same_callable(row['get'],config[5]) and same_callable(row['guard'],config[6])
            and row['object'].send is row['send_hook'] and row['object'].original is row['get_hook']
            and same_callable(row['object'].guard,row['guard']))
        if row['command'] is not None:need(canonical(row['command'])==row['command_bytes'])
        self.capture.bound();need(row['guard']() is not False);self.capture.bound()

    def retain(self,row,token,value):
        if type(value) is not bytes or len(value)>row['limit']+1+4096:
            UNCONFIRMED.append((self.archive,token,value));need(False)
        return self.archive.retain(token,value)

    def reserve(self,row):
        self.bound(row);need(row['token'] is None and row['command'] is not None)
        row['nonce']=uuid.uuid4().hex;maximum=row['limit']+1+4096
        row['token']=self.archive.reserve('emote-stream-'+row['label'],dict(row['command'],literalRead=row['reads'],wireNonce=row['nonce']),
            maximum,side_bytes=8*maximum);self.bound(row)
