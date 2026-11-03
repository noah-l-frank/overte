"""Opt-in Layout2 transport composition over the SAME live Assets Parent.

Opaque SDK returns enter original storage before decoder/receipt/effect checks.
A Stage transport receipt is a separate bounded bundle, never a staged lease.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import uuid

from adb_transport import AdbTransport
from adapters.native_feature_observation import exact,integer,need
from adapters.pico4.assets_raw_archive import compact
from adapters.pico4.assets_transport import PicoAssetsTransport,read_body,BODY_LIMIT,AUX_LIMIT
from adapters.pico4.assets_raw_ranges import OVERLAY
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW


def bind_assets_navigation_raw(owner,io):
    """Existing Upload IO seam, shared with the cold child-runtime binder."""
    from adapters.pico4.navigation import NativeNavigationIO
    need(type(io) is NativeNavigationIO)
    read,raw=io.read,io._read
    def bounded_read():
        if type(owner) is AssetsChildUiRaw:need(owner.ui_anchor is not None)
        else:
            need(owner.ui_anchor is None)
            owner.ui_anchor=(owner.parent.phases.monotonic(),owner.parent.clock_ms())
        try:
            result=read();owner.parent.query_anchor=owner.ui_anchor;owner.parent.query_age()
            owner.last_ui_anchor=owner.ui_anchor;return result
        finally:owner.ui_anchor=None
    def retain(kind):
        need(kind in ('observation','status'));role='ui-'+kind
        if kind!='status' or owner.query is None:
            command=(owner.ui_command(kind) if type(owner) is AssetsChildUiRaw else
                dict(source='navigation-ui-'+kind,ticket=owner.parent.state['steps'][-1]['ticket']))
            owner.begin(role,command)
        else:
            need(owner.query['role']==role)
            if owner.parent.raw_archive.active is None:owner.parent.raw_archive.reserve(role,owner.query['command'])
            # Original input intent stays historical; this is a new actual
            # bounded ACK byte read, never another ordinary input.
            owner.parent.query_anchor=(owner.parent.phases.monotonic(),owner.parent.clock_ms())
        if owner.ui_anchor is not None:owner.parent.query_anchor=owner.ui_anchor
        owner.parent.query_age();value=raw(kind) if owner.parent.wire is None else owner.parent.wire.read(role)
        owner.acquired=value
        if owner.parent.wire is None:owner.retain_raw(role,value)
        else:owner.parent.wire.consume(role,value);owner.parent.raw_archive.parser_capacity(value,owner.query['command'])
        owner.acquired=None;owner.finish();return value
    io.read,io._read=bounded_read,retain
    return read,raw,bounded_read,retain


UNRESOLVED_UI=[]


class AssetsChildUiRaw:
    """Original child UI bytes, including cold runtime observations and ACKs.

    No parsed UI effect is supplied here. Existing Pico navigation and child
    validators still consume the body only after its durable raw receipt.
    """
    def __init__(self,parent):
        need(parent.version==3 and parent.wire is not None and parent.child is None
            and parent.child_ui is None and len(parent.state['steps'])==2
            and parent.state['steps'][-1]['status']=='issued')
        self.parent,self.wire=parent,parent.wire
        self.fixed=self.original_fixed=(parent,parent.wire,canonical(parent.binding),parent.run,parent.url,
            parent.state['steps'][1]['ticket'])
        self.slots=self.original_slots=();self.query=None;self.ui_anchor=None;self.last_ui_anchor=None
        self.failed=False;self.read_active=False;self.read_io=None
        self.raw_active=False;self.active_io=None;self.raw_anchor=None;self.acquired=None
        self.child=self.original_child=None

    def identity(self,*,held=True):
        p=self.parent
        need(not self.failed and not p.failed and p.child_ui is self
            and self.fixed is self.original_fixed and self.slots is self.original_slots
            and type(self.slots) is tuple and len(self.slots)<=16
            and self.child is self.original_child and (self.child is None or p.child is self.child)
            and self.fixed==(p,p.wire,canonical(p.binding),p.run,p.url,p.state['steps'][1]['ticket'])
            and p.wire is self.wire and len(p.state['steps']) in (2,3)
            and p.state['steps'][-1]['status'] in ('issued','returned'))
        if held:p.lock.assert_held()
        return p

    def fail(self):
        self.failed=True;self.parent.failed=True
        if self not in UNRESOLVED_UI:UNRESOLVED_UI.append(self)

    def slot(self,io,*,held=True):
        from adapters.pico4.navigation import NativeNavigationIO
        p=self.identity(held=held);rows=[row for row in self.slots if row[0] is io]
        need(len(rows)==1);row=rows[0]
        need(io.adapter is self.wire.adapter and io.target==self.wire.target
            and io.identity==p.binding['processIdentity'] and io.read is row[1] and io._read is row[2]
            and io._controller is row[5]
            and getattr(io.guard,'__func__',None) is NativeNavigationIO.guard
            and getattr(io.send,'__func__',None) is NativeNavigationIO.send
            and getattr(io.bind_input,'__func__',None) is NativeNavigationIO.bind_input)
        return row

    def bind_native(self,io):
        from adapters.pico4.navigation import NativeNavigationIO
        need(not self.read_active and not self.raw_active and self.query is None and self.ui_anchor is None)
        self.identity()
        need(type(io) is NativeNavigationIO and len(self.slots)<16 and not self.raw_active and self.query is None
            and self.ui_anchor is None and not any(row[0] is io for row in self.slots)
            and io.adapter is self.wire.adapter and io.target==self.wire.target
            and io.identity==self.parent.binding['processIdentity']
            and getattr(io.read,'__func__',None) is NativeNavigationIO.read
            and getattr(io._read,'__func__',None) is NativeNavigationIO._read)
        original_read,original_raw,bounded,retained=bind_assets_navigation_raw(self,io)
        def read():
            entered=False
            try:
                need(not self.failed and not self.parent.failed and self.ui_anchor is None
                    and self.query is None and not self.raw_active and not self.read_active)
                self.slot(io,held=False)
                self.read_active=True;self.read_io=io;entered=True
                self.ui_anchor=(self.parent.phases.monotonic(),self.parent.clock_ms())
                self.slot(io);return bounded()
            except BaseException:self.fail();raise
            finally:
                if entered:self.ui_anchor=None;self.read_active=False;self.read_io=None
        def raw(kind):
            entered=False
            try:
                need(not self.failed and not self.parent.failed and not self.raw_active and self.query is None
                    and type(kind) is str and kind in ('observation','status'))
                if self.read_active:need(self.read_io is io and kind=='observation' and self.ui_anchor is not None)
                self.slot(io,held=False)
                self.raw_active=True;self.active_io=io;entered=True
                self.raw_anchor=self.ui_anchor if self.ui_anchor is not None else (self.parent.phases.monotonic(),self.parent.clock_ms())
                self.slot(io)
                return retained(kind)
            except BaseException:self.fail();raise
            finally:
                if entered:self.raw_active=False;self.active_io=None;self.raw_anchor=None
        io.read,io._read=read,raw
        self.slots=self.original_slots=(*self.slots,(io,read,raw,original_read,original_raw,io._controller))
        return self.require_binding

    def require_binding(self,binding):
        try:
            self.identity();need(canonical(binding)==self.fixed[2]);return True
        except BaseException:self.fail();raise

    def attach(self,child):
        from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
        p=self.identity()
        need(type(child) is OwnedAssetsCancel and self.child is None and child.previous is None
            and canonical(child.binding)==self.fixed[2] and child.run==p.run and child.url==p.url
            and self.query is None and not self.raw_active and not self.read_active and self.ui_anchor is None)
        child.bind_budget_cache()
        self.child=self.original_child=child

    def ui_command(self,kind):
        need(self.active_io is not None and self.query is None)
        p=self.identity()
        anchor=self.ui_anchor if self.ui_anchor is not None else self.raw_anchor
        need(anchor is not None)
        return dict(assetsChildUiQueryVersion=1,queryId=uuid.uuid4().hex,kind=kind,
            ticket=p.state['steps'][-1]['ticket'],ownerOpenTicket=self.fixed[5],
            startedHostMonotonic=anchor[0],startedEpochMs=anchor[1])

    def begin(self,role,command):
        p=self.identity();need(self.query is None and role in ('ui-observation','ui-status'))
        # Keep the FIRST actual read anchor through old-query completion,
        # capacity admission, every raw receipt and all final publication.
        p.query_anchor=(command['startedHostMonotonic'],command['startedEpochMs'])
        p.complete_child_query(save=False)
        need(p.disk['pendingSource'] is None)
        self.query=dict(role=role,command=deepcopy(command))
        p.state['pendingChildSource']=dict(role=role,command=p.command_reference(command),raw=[])
        p.raw_archive.reserve('child-'+role,command);p.query_age()

    def finish(self):
        p=self.identity();pending=p.disk['pendingChildSource']
        need(self.query is not None and pending is not None and pending['raw']
            and pending['role']==self.query['role'] and p.command_original(pending['command'])==self.query['command'])
        p.state['pendingChildSource']=None;p.save();p.bill();p.query_age();self.query=None


def body_view(wire,view):
    exact(view,{'assetsWireViewVersion','nonce','bytes','sha256'})
    need(type(view['assetsWireViewVersion']) is int and view['assetsWireViewVersion']==1
        and type(view['nonce']) is str and len(view['nonce'])==32 and all(c in '0123456789abcdef' for c in view['nonce'])
        and integer(view['bytes'],0,BODY_LIMIT))
    body=read_body(wire,view['nonce'])
    need(len(body)==view['bytes'] and hashlib.sha256(body).hexdigest()==view['sha256'])
    return body


def stage_original(value,scope_sha):
    exact(value,{'assetsStageReceiptRawVersion','scopeSha256','commandId','commandSha256','commandOriginal','bytes','sha256','data'})
    need(type(value['assetsStageReceiptRawVersion']) is int and value['assetsStageReceiptRawVersion']==1
        and value['scopeSha256']==scope_sha and type(value['commandId']) is str and len(value['commandId'])==32
        and all(c in '0123456789abcdef' for c in value['commandId']) and integer(value['bytes'],0,AUX_LIMIT)
        and type(value['data']) is str)
    raw=base64.b64decode(value['data'],validate=True)
    need(base64.b64encode(raw).decode('ascii')==value['data'] and len(raw)==value['bytes']
        and hashlib.sha256(raw).hexdigest()==value['sha256']
        and type(value['commandSha256']) is str and len(value['commandSha256'])==64
        and all(c in '0123456789abcdef' for c in value['commandSha256']))
    return raw


class AssetsWireOwner:
    def __init__(self,parent,adapter,target):
        need(parent.version==3 and parent.scope['assetsRawOriginalLayoutVersion']==2
            and parent.scope.get('assetsWireOriginalLayoutVersion')==1
            and parent.wire is None and parent.state['observations']==0 and not parent.state['steps']
            and not parent.mappings.history and not parent.uploads.history
            and getattr(adapter.adb.execute_bytes,'__func__',None) is AdbTransport.execute_bytes)
        self.parent,self.adapter,self.target=parent,adapter,target
        self.last_receipt=self.last_return=None;self.consumed=True;self.stage_plan=None
        self.transport=PicoAssetsTransport(adapter,target,parent.binding['processIdentity'],self.guard,self.retain,
            self.capacity,parent.clock_ms,monotonic=parent.phases.monotonic,publish_view=self.publish_view)
        self.original=(parent,adapter,target,self.transport)

    def identity(self):
        p=self.parent;need((p,self.adapter,self.target,self.transport)==self.original and p.wire is self)
        p.bound();return p

    def guard(self):
        p=self.identity();p.query_age();return True

    def context(self):
        p=self.parent
        if p.state['pendingSource'] is not None:return 'pendingSource'
        if p.state['pendingChildSource'] is not None:return 'pendingChildSource'
        need(False)

    def capacity(self,role,command,wire_limit):
        p=self.identity();need(wire_limit==BODY_LIMIT+AUX_LIMIT);active=p.raw_archive.active
        need(active is not None and active['state']=='reserved')
        if role=='stage-receipt':
            name=self.context();pending=p.state[name]
            need(self.stage_plan is None and p.command_original(pending['command'])==command
                and command['operation']=='stage' and 'transportPending' not in pending)
            bill=p.bill();audio=p.raw_archive.audio
            reserved=audio.state['pending'];parts=sum(token['parts'] for token in reserved)
            size=sum(token['limit']+token['sideBytes'] for token in reserved)
            # One original bundle and its JSON/base64/fragment/readback/CAS
            # windows are guaranteed BEFORE the SDK starts. No second literal
            # lane spends or renews the existing native-response reservation.
            extra=4*AUX_LIMIT+4*65536
            need(bill['frames']+parts+2<=MAX_FRAMES
                and bill['decodedBytes']+size+OVERLAY+extra<=MAX_RAW
                and bill['storedBytes']+size+OVERLAY+extra<=MAX_RAW)
            plan=dict(assetsStageWireReservationVersion=1,commandId=command['commandId'],
                commandSha256=hashlib.sha256(canonical(command)).hexdigest(),limit=AUX_LIMIT,
                reservedFrames=1,reservedBytes=extra)
            pending['transportPending']=deepcopy(plan)
            p.save();self.stage_plan=(name,deepcopy(plan))
        else:
            expected=active['role'].removeprefix('child-')
            need(role==('ui-observation' if expected=='ui' else expected))
        p.query_age()

    def retain(self,role,raw):
        p=self.identity()  # physical/host identity only; no business clock
        need(type(raw) is bytes)
        if role=='stage-receipt':
            need(self.stage_plan is not None and len(raw)<=AUX_LIMIT)
            name,plan=self.stage_plan;pending=p.state[name]
            need(pending is not None and pending.get('transportPending')==plan)
            value=dict(assetsStageReceiptRawVersion=1,scopeSha256=p.history.scope,
                commandId=plan['commandId'],commandSha256=plan['commandSha256'],commandOriginal=deepcopy(pending['command']),bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),data=base64.b64encode(raw).decode('ascii'))
            stage_original(value,p.history.scope)
            actual=p.command_original(value['commandOriginal'])
            need(actual['commandId']==value['commandId'] and hashlib.sha256(canonical(actual)).hexdigest()==value['commandSha256'])
            def sealed(index):
                p.state['transportReceipts'].append(index)
                p.state[name].pop('transportPending')
            p.archive(value,on_seal=sealed);self.stage_plan=None;return
        active=p.raw_archive.active;need(active is not None and active['state']=='reserved')
        expected=active['role'].removeprefix('child-')
        need(role==('ui-observation' if expected=='ui' else expected))
        ref=p.raw_archive.retain_wire(raw)
        tag='childSource' if active['role'].startswith('child-') else 'role'
        field='pendingChildSource' if tag=='childSource' else 'pendingSource'
        pending=p.state[field]
        receipts=None if pending is None else pending['raw']
        index=p.raw_receipt({tag:expected,'rawOriginal':compact(ref)},receipts)
        self.last_receipt=(role,index);self.last_return=None;self.consumed=True

    def publish_view(self,role,body,nonce):
        p=self.identity();need(self.last_receipt is not None and self.last_receipt[0]==role)
        index=self.last_receipt[1];row=p.state['rawReads'][index];need('wireView' not in row)
        view=dict(assetsWireViewVersion=1,nonce=nonce,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
        raw=p.raw_archive.literal(row['rawOriginal']);need(body_view(raw,view)==body)
        row['wireView']=view;p.save();p.bill()
        self.last_return=(role,index,body);self.consumed=False

    def read(self,role):
        return self.transport.read(role).decode('utf-8')

    def consume(self,role,text):
        p=self.identity();need(type(text) is str and self.last_return is not None and not self.consumed)
        actual,index,body=self.last_return
        need(actual==('ui-observation' if role=='ui' else role) and text.encode('utf-8')==body
            and p.literal(index)==body)
        self.consumed=True;return index

    def dispatch(self,command,send):
        self.guard()
        if command.get('action')=='feature-pico-assets-files' and command.get('operation')=='stage':
            return self.transport.stage(command)
        return send(command)
