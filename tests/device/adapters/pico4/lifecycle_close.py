"""Normal Scripts/Home X closure; every query still counts in original World.

This is a new private continuation, not a new source profile or frame budget.
The original World journal remains authoritative, including its 128-frame cap.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.chat_journey.original_memory import ChatOriginalMemory
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import state as file_state,parent_node
from adapters.pico4 import lifecycle_source as ui
from adapters.pico4.lifecycle_back import BUTTON,PicoLifecycleBack,envelope
from adapters.pico4.lifecycle_pending import PicoLifecyclePending,current_return
from adapters.pico4.lifecycle_pending_originals import LifecyclePendingOriginals
from adapters.pico4.lifecycle_process import closed
from adapters.pico4.lifecycle_world import MAX_FRAMES as WORLD_MAX_FRAMES,neutral
from adapters.script_journey.history import canonical,pack,unpack

VERSION=1
PHASES=('prepared','page-x-issued','home','tablet-x-issued','closed')


class LifecycleCloseOriginals(LifecyclePendingOriginals):
    """Same complete byte/FD grammar, distinct fixed close-stage ownership."""
    def __init__(self,path,run,binding):
        need(ui.nonce(run));self.root=PrivateFeatureState(path);self.run,self.binding=run,deepcopy(context(binding))
        need(self.root.path.name=='lifecycle-close-originals.json')
        self.scope=dict(lifecycleCloseOriginalsVersion=VERSION,runId=run,binding=self.binding,role='lifecycle-close')
        self.history=ChatSourceChunks(self.root,self.scope);self.parent=parent_node(self.root)
        self.disk=self.root.read();self.root_stamp=self._root_stamp=None;values=[]
        if self.disk is not None:
            observed,_raw,physical=file_state(self.root);need(observed==self.disk)
            self.root_stamp=self._root_stamp=tuple(physical)
            exact(self.disk,set(self.scope)|{'phase','chunks'})
            need(all(self.disk[key]==value and type(self.disk[key]) is type(value) for key,value in self.scope.items())
                and self.disk['phase']=='reading')
            values=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        self.memory=self._memory=ChatOriginalMemory(self.scope);self.hashes=self._hashes=();self.by_hash=self._by_hash={}
        for index,value in enumerate(values):
            self.original(value);need(value['sha256'] not in self.by_hash)
            self.by_hash[value['sha256']]=index;self.memory.append(value,self.scope)
            self.hashes=self._hashes=self.hashes+(value['sha256'],)


class PicoLifecycleClose:
    def __init__(self,pending,path):
        need(type(pending) is PicoLifecyclePending)
        self.pending,self.world=pending,pending.world
        self.run,self.binding,self.pid,self.lock=pending.run,deepcopy(pending.binding),pending.pid,pending.lock
        self.store=PrivateFeatureState(path);need(self.store.path==self.world.store.path.with_name('lifecycle-close-owner.json'))
        self.disk=self.state=None;self.deadline=self.last_clock=self.anchor=None
        with self.lock.held():
            self.disk=self.store.read();self.originals=LifecycleCloseOriginals(self.store.path.with_name('lifecycle-close-originals.json'),self.run,self.binding)
            need(self.disk is not None or self.originals.disk is None);self.load()

    def original_state(self):
        self.pending.original_state()
        need(self.run==self.pending.run and self.binding==self.pending.binding and self.pid==self.pending.pid
            and self.lock is self.pending.lock and self.store.read()==self.disk
            and self.world.store.read()==self.world.disk and len(self.world.state['frames'])<=WORLD_MAX_FRAMES)
        self.originals.verify()
        if self.disk is not None:
            need(self.disk['originalChunks']==self.originals.manifest and type(self.disk['originalStamp']) is list
                and all(type(value) is int for value in self.disk['originalStamp'])
                and self.disk['originalStamp']==list(self.originals.root_stamp))
        else:need(self.originals.disk is None)
        if self.state is not None:
            need(hashlib.sha256(canonical(self.pending.disk)).hexdigest()==self.state['pendingSha256'])

    def bound(self,*,host_only=False):
        self.lock.assert_held();self.original_state();now=self.world.monotonic()
        from adapters.native_feature_observation import number
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.deadline is None or now<=self.deadline));self.last_clock=now
        if not host_only:need(self.world.guard() is not False and self.pending.pending.guard() is not False)
        return now

    def fresh(self,*,host_only=False):
        self.bound(host_only=host_only)
        # Reuse exactly the original captured timestamps/age checker, never a
        # fresh HTTP/Qt sample to qualify an older query or controller intent.
        self.pending.anchor=self.anchor;self.pending.fresh(host_only=host_only)

    def released_fresh(self):
        self.original_state();self.pending.anchor=self.anchor;self.pending.released_fresh()
        now=self.world.monotonic();need(self.deadline is None or now<=self.deadline);self.last_clock=now

    def packet(self,row):
        exact(row,{'worldFrameIndex','original'});index=row['worldFrameIndex']
        need(integer(index,0,len(self.world.state['frames'])-1)
            and canonical(row['original']['world'])==canonical(self.world.state['frames'][index]))
        # Every physically distinct observation has its original World index.
        # This container cannot reset/exclude queries from World's fixed cap.
        return self.pending.packet(row['original'])

    def validate(self,value):
        exact(value,{'phase','pendingSha256','frames','inputs'})
        need(value['phase'] in PHASES and type(value['frames']) is list and 1<=len(value['frames'])<=12
            and type(value['inputs']) is list and len(value['inputs'])<=2)
        previous=None;indices=[]
        for row in value['frames']:
            packets,pending=self.packet(row);previous=ui.accept(previous,ui.summary(packets['ui']));indices.append(row['worldFrameIndex'])
            need(not pending['resources']['pendingRuns'] and pending['commit'] and not pending['commit']['observation']['pending']
                and pending['commit']['observation']['events'][-1]['kind']=='rejected'
                and pending['commit']['observation']['events'][-1]['reason']=='context-retired')
        need(indices==sorted(set(indices)))
        before,_pending=self.packet(value['frames'][0]);current=ui.current_editor(before['ui'])
        need(current is not None and current['id']==self.pending.state['replacementId'] and current['kind']=='scripts')
        for index,owned in enumerate(value['inputs']):
            exact(owned,{'envelope','neutral'})
            if owned['envelope'] is not None:
                envelope(owned['envelope'],self.world.session.profile)
                if owned['neutral'] is not None:PicoLifecycleBack.neutral(owned['neutral'],owned['envelope'],before['ui']['capturedEpochMs'])
            else:need(owned['neutral'] is None)
        if value['phase'] in ('home','tablet-x-issued','closed'):
            need(value['inputs'] and value['inputs'][0]['neutral'] is not None)
            reached=[self.packet(row)[0]['ui'] for row in value['frames']]
            home=next((packet for packet in reached if packet['source']['tabletShown'] and packet['source']['onHomeScreen']),None)
            need(home is not None);PicoLifecycleBack.home(home,self.pending.state['replacementId'])
        if value['phase']=='closed':
            need(len(value['inputs'])==2 and value['inputs'][1]['neutral'] is not None)
            closed(self.packet(value['frames'][-1])[0]['ui'])

    def load(self):
        self.bound();disk=self.store.read()
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecycleCloseOwnerVersion','runId','binding','originalChunks','originalStamp','payload'})
        need(type(disk['lifecycleCloseOwnerVersion']) is int and disk['lifecycleCloseOwnerVersion']==VERSION
            and disk['runId']==self.run and context(disk['binding'])==self.binding)
        values=self.originals.decode(unpack(disk['payload']));need(len(values)==1);self.validate(values[0])
        self.disk,self.state=deepcopy(disk),deepcopy(values[0]);self.bound()

    def save(self,value,*,host_only=False):
        self.bound(host_only=host_only);self.validate(value);encoded=self.originals.encode([value])
        disk=dict(lifecycleCloseOwnerVersion=VERSION,runId=self.run,binding=deepcopy(self.binding),
            originalChunks=self.originals.manifest,originalStamp=list(self.originals.root_stamp),payload=pack(encoded))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(value)
        self.bound(host_only=host_only)

    def capture(self):
        before=len(self.world.state['frames']);original=self.pending.capture()
        need(len(self.world.state['frames'])==before+1)
        row=dict(worldFrameIndex=before,original=original);self.packet(row);self.anchor=self.pending.anchor;return row

    @current_return
    def prepare(self):
        with self.lock.held():
            self.load();self.pending.load();need(self.state is None and self.pending.state['phase']=='quiet' and self.pending.state['cleanup'] is None)
            row=self.capture();self.pending.quiet_packet(self.pending.state,row['original'])
            before=self.pending.packet(self.pending.state['frames'][-1])[0]
            after=self.packet(row)[0];ui.accept(ui.summary(before['ui']),ui.summary(after['ui']))
            need(before['gesture']['source']['events']==after['gesture']['source']['events'])
            self.save(dict(phase='prepared',pendingSha256=hashlib.sha256(canonical(self.pending.disk)).hexdigest(),frames=[row],inputs=[]));self.fresh()

    @current_return
    def press(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('prepared','home'));row=self.capture();packet=self.packet(row)[0]['ui']
            first=self.state['phase']=='prepared'
            if first:
                self.pending.quiet_packet(self.pending.state,row['original'])
            else:
                PicoLifecycleBack.home(packet,self.pending.state['replacementId'])
                packets=self.packet(row)[0];neutral(packets['gesture']);actual=self.world.anchor.measure(packets['drive'])
                need(not actual['heldInputs'] and actual['worldDisplacement']<=.025)
            value=deepcopy(self.state);value['frames'].append(row);value['phase']='page-x-issued' if first else 'tablet-x-issued'
            value['inputs'].append(dict(envelope=None,neutral=None));self.save(value);self.fresh()
            def intent(owned):
                envelope(owned,self.world.session.profile);value=deepcopy(self.state);need(value['inputs'][-1]['envelope'] is None)
                value['inputs'][-1]['envelope']=deepcopy(owned);self.save(value,host_only=True);self.fresh(host_only=True)
            def before_publish(owned):
                need(owned==self.state['inputs'][-1]['envelope']);self.fresh(host_only=True)
            self.world.session.stage(self.binding['processIdentity'],'controller.button',deepcopy(BUTTON),intent=intent,before_publish=before_publish)
            return self.reconcile()

    @current_return
    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('page-x-issued','tablet-x-issued'))
            value=deepcopy(self.state);owned=value['inputs'][-1];need(owned['envelope'] is not None)
            owned['neutral']=deepcopy(self.world.session.require_owned_neutral(self.binding['processIdentity'],owned['envelope']))
            row=self.capture();packet=self.packet(row)[0]['ui']
            if self.state['phase']=='page-x-issued':PicoLifecycleBack.home(packet,self.pending.state['replacementId']);value['phase']='home'
            else:closed(packet);value['phase']='closed'
            value['frames'].append(row);self.save(value);result=self.report();self.fresh();return result

    def report(self):
        packets,pending=self.packet(self.state['frames'][-1]);current=ui.current_editor(packets['ui'])
        from adapters.native_chat_view import measured_keyboard
        actual=self.world.anchor.measure(packets['drive'])
        if current is not None:need(current['id']==self.pending.state['replacementId'])
        terminal=pending['commit']['observation']['events'][-1]
        return dict(editor=current['kind'] if current else 'none',text=current['text'] if current else '',
            generation=4 if current else 0,focused=bool(current and current['focused']),keyboard=measured_keyboard(packets['ui']['source']['keyboard']),
            heldInputs=actual['heldInputs'],worldDisplacement=actual['worldDisplacement'],positionDelta=dict(zip(('x','y','z'),actual['positionDelta'])),
            deferredInputs=len(pending['resources']['pendingRuns']),
            staleAttempts=int(terminal['kind']=='rejected' and terminal['reason']=='context-retired'),
            worldAttempts=len(self.world.attempts(self.world.state,packets['gesture'])),journalRetained=True,completeLifecycle=False)


@current_return
def run_close(owner):
    need(type(owner) is PicoLifecycleClose)
    with owner.lock.held():
        owner.load()
        if owner.state is None:owner.prepare()
        if owner.state['phase']=='prepared':owner.press()
        elif owner.state['phase']=='page-x-issued':owner.reconcile()
        if owner.state['phase']=='home':owner.press()
        elif owner.state['phase']=='tablet-x-issued':owner.reconcile()
        need(owner.state['phase']=='closed')
        row=owner.capture();closed(owner.packet(row)[0]['ui']);value=deepcopy(owner.state);value['frames'].append(row)
        owner.save(value);result=owner.report();owner.fresh();return result
