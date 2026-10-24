"""Original pre-input process baseline through normal viewpoint restoration.

This joins existing owners. It neither sets avatar properties nor fabricates
a process/network birth, and it never replays uncertain navigation inputs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import uuid

from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need
from adapters.native_graphics_subject import validate as validate_subject
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.graphics_surface import PicoGraphicsSurface
from adapters.pico4.lifecycle_close import PicoLifecycleClose
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
from adapters.pico4.lifecycle_pending import current_return
from adapters.pico4.lifecycle_process import PicoLifecycleProcessRetirement,PicoLifecycleDomain,closed
from adapters.pico4.navigation import validate_snapshot,identifier
from adapters.pico4.tablet_home import validate as validate_home
from adapters.pico4 import lifecycle_source as ui
from adapters.script_journey.history import canonical,pack,unpack
from openxr_input.controller_protocol import validate_envelope

VERSION=1


def sha(value):return hashlib.sha256(canonical(value)).hexdigest()


class PicoLifecycleRestoreSurface(PicoGraphicsSurface):
    """Only this owner may type its frozen original location-only literal.

    The ordinary Graphics URL policy is untouched. AddressManager's existing
    path-only branch calls handlePath without replacing the original scene URL.
    """
    def authorized_url(self,value):
        need(type(value) is str and 0<len(value)<=2048
            and re.fullmatch(r'/[-0-9.,]+/[-0-9.,]+',value) is not None)
        return self.allow_url(value) is True


class PicoLifecycleRestore:
    def __init__(self,process,joined,native,domain,path,surface_factory):
        need(type(process) is PicoLifecycleProcessRetirement and type(joined) is PicoLifecycleXJoin
            and isinstance(native,NativeFeatureObservation) and type(domain) is PicoLifecycleDomain
            and callable(surface_factory))
        self.process,self.joined,self.world=process,joined,joined.world
        self.native,self.domain,self.surface_factory=native,domain,surface_factory
        self.run,self.binding,self.lock,self.pid=self.world.run,deepcopy(self.world.binding),self.world.lock,self.world.pid
        need(process.lock is self.lock and domain.source_lock is self.lock and native.pid==domain.pid==self.pid)
        self.store=PrivateFeatureState(path)
        need(self.store.path==self.world.store.path.with_name('lifecycle-restore-owner.json'))
        self.disk=self.state=self.deadline=None
        with self.lock.held():self.load()

    def bound(self,*,host_only=False):
        self.lock.assert_held();need(self.store.read()==self.disk and self.world.store.read()==self.world.disk
            and self.process.store.read()==self.process.disk)
        now=self.world.monotonic();need(self.deadline is None or now<=self.deadline)
        if not host_only:need(self.world.guard() is not False and self.native.guard() is not False)
        return now

    def baseline(self):
        need(self.process.state is not None)
        history=self.process.history(self.process.state['originalWorld'],self.binding)
        original=history.originals(history.state['frames'][0])['drive']['source']
        need(not history.state['attempts'])
        def decimal(value):return format(value,'.9f').rstrip('0').rstrip('.') or '0'
        return '/'+','.join(decimal(v) for v in original['feetPosition'])+'/'+','.join(decimal(v) for v in original['orientation'])

    def validate(self,state):
        exact(state,{'phase','baselineSha256','restorePath','leases','inputs','preparedSha256'})
        need(state['phase'] in ('begun','navigating','prepared') and state['restorePath']==self.baseline())
        baseline={key:self.process.state[key] for key in ('binding','originalWorld','originalNative','originalDomain')}
        need(state['baselineSha256']==sha(baseline))
        exact(state['leases'],{'tablet','address','menu'})
        need(all(type(value) is bool for value in state['leases'].values())
            and type(state['inputs']) is list and len(state['inputs'])<=32)
        indices=[]
        for row in state['inputs']:
            exact(row,{'stage','subject','source','control','worldFrameIndex','worldSha256','command','envelope'})
            index=row['worldFrameIndex'];need(integer(index,0,len(self.world.state['frames'])-1))
            world=self.world.state['frames'][index];need(sha(world)==row['worldSha256']);indices.append(index)
            packets=self.world.originals(world);epoch=min(packet['capturedEpochMs'] for packet in packets.values())
            subject=row['subject'];request=dict(schemaVersion=1,commandId=subject['requestId'],
                action='feature-graphics-subject-observe',runId=self.run)
            validate_subject(subject,request,self.pid,epoch,require_avatar=True,require_framework=True)
            exact(row['source'],{'kind','value'});kind,value=row['source']['kind'],row['source']['value']
            if kind=='navigation':
                validate_snapshot(value,self.pid,value['updatedEpochMs']);need(value['bridgeId']==self.binding['sessionId'])
            else:
                need(kind=='home');validate_home(value,value['commandId'],self.pid,value['capturedEpochMs'])
            need(type(row['stage']) is str and type(row['control']) is str)
            stages={'tablet-open':('tablet.open',None),'tablet-close':('tablet.close',None),
                'address-open':('navigation.goto','activate'),'address-focus':('navigation.address','activate'),
                'address-replace':('navigation.address','replace'),'address-go':('navigation.address','submit')}
            if row['stage'].startswith('tablet-tablet.page.'):
                need(row['stage']=='tablet-'+row['control'] and re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',row['control']))
                action='activate'
            else:need(row['stage'] in stages and stages[row['stage']][0]==row['control']);action=stages[row['stage']][1]
            need(row['command'] is None or row['envelope'] is None)
            if row['command'] is not None:
                command=row['command'];fields={'schemaVersion','commandId','bridgeId','generation','sequence',
                    'observedElapsedMs','controlId','controlToken','action'}
                exact(command,fields|({'text'} if command.get('action')=='replace' else set()))
                need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                    and str(uuid.UUID(command['commandId']))==command['commandId']
                    and str(uuid.UUID(command['controlToken']))==command['controlToken']
                    and type(command['generation']) is str and identifier(command['generation'])
                    and integer(command['sequence'],1) and integer(command['observedElapsedMs'])
                    and command['controlId']==row['control'] and command['bridgeId']==self.binding['sessionId'] and command['action']==action)
                if command['action']=='replace':need(command['controlId']=='navigation.address' and command['text']==state['restorePath'])
                elif command['action']=='submit':need(command['controlId']=='navigation.address')
                else:need(command['action']=='activate' and (command['controlId'] in ('navigation.goto','navigation.address')
                    or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',command['controlId'])))
                need(kind=='navigation' and command['generation']==value['generation'] and command['bridgeId']==value['bridgeId'])
                control=next((item for item in value['controls'] if item['id']==command['controlId']),None)
                need(control is not None and control['token']==command['controlToken'] and control['enabled'])
            if row['envelope'] is not None:
                validate_envelope(row['envelope'],self.world.session.profile)
                need(row['control'] in ('tablet.open','tablet.close') and len(row['envelope']['commands'])==1
                    and row['envelope']['commands'][0]['operation']==row['control'])
        need(indices==sorted(set(indices)))
        if state['phase']=='begun':need(not state['inputs'] and not any(state['leases'].values()))
        if state['phase']=='prepared':
            need(not any(state['leases'].values()) and self.process.state['phase']=='prepared'
                and state['preparedSha256']==sha(self.process.disk))
        else:need(state['preparedSha256'] is None)

    def load(self):
        self.bound();self.process.load();self.world.load()
        value=self.store.read()
        if value is None:need(self.state is None);return
        exact(value,{'lifecycleRestoreOwnerVersion','runId','binding','payload'})
        need(type(value['lifecycleRestoreOwnerVersion']) is int and value['lifecycleRestoreOwnerVersion']==VERSION
            and value['runId']==self.run and context(value['binding'])==self.binding)
        states=unpack(value['payload']);need(len(states)==1);self.validate(states[0])
        self.disk,self.state=deepcopy(value),deepcopy(states[0]);self.bound()

    def save(self,state,*,host_only=False):
        self.bound(host_only=host_only);self.validate(state)
        value=dict(lifecycleRestoreOwnerVersion=VERSION,runId=self.run,binding=deepcopy(self.binding),payload=pack([state]))
        self.store.write(value,self.disk);need(self.store.read()==value)
        self.disk,self.state=deepcopy(value),deepcopy(state);self.bound(host_only=host_only)

    def released_fresh(self):
        need(self.store.read()==self.disk and self.world.store.read()==self.world.disk)
        self.world.final_result(None)
        need(self.deadline is None or self.world.monotonic()<=self.deadline)

    @current_return
    def begin(self):
        """Must execute before the existing Create/World/Chat/Scripts prefix."""
        with self.lock.held():
            self.load();need(self.state is None)
            if self.world.state is None:self.world.prepare()
            self.joined.load()
            need(not self.world.state['attempts'] and self.joined.state is None)
            if self.process.state is None:self.process.begin(self.world,self.native,self.domain)
            need(self.process.state['phase']=='begun')
            baseline={key:self.process.state[key] for key in ('binding','originalWorld','originalNative','originalDomain')}
            self.save(dict(phase='begun',baselineSha256=sha(baseline),restorePath=self.baseline(),
                leases=dict(tablet=False,address=False,menu=False),inputs=[],preparedSha256=None))
            return dict(originalProcessBaselineRecorded=True,completeLifecycle=False)

    def intent(self,stage,subject,source,control):
        self.bound();need(self.state['phase']=='navigating' and source['kind']=='navigation')
        # Close leaves owned Home hidden. A surprising Home-ray need is not a
        # license for an unjournaled alternate trigger transport.
        # Every authoritative observation still appends to the SAME World128
        # history. The normal input copies never provide another sample budget.
        self.world.current();index=len(self.world.state['frames'])-1
        state=deepcopy(self.state);state['inputs'].append(dict(stage=stage,subject=deepcopy(subject),
            source=deepcopy(source),control=control,worldFrameIndex=index,
            worldSha256=sha(self.world.state['frames'][index]),command=None,envelope=None))
        self.save(state);self.world.final_result(None)

    def owns(self,field):return self.state['leases'][field]

    def lease(self,field,value):
        state=deepcopy(self.state);need(field in state['leases'] and type(value) is bool)
        state['leases'][field]=value;self.save(state);self.world.fresh_current()

    def authorized_url(self,url):return type(url) is str and url==self.state['restorePath']

    def command(self,command):
        state=deepcopy(self.state);row=state['inputs'][-1]
        need(row['command'] is None and row['envelope'] is None and command['controlId']==row['control'])
        row['command']=deepcopy(command);self.save(state);self.world.final_result(None)

    def controller(self,operation):
        need(self.state['inputs'][-1]['control']==operation);self.world.final_result(None)

    def envelope(self,original):
        state=deepcopy(self.state);row=state['inputs'][-1]
        validate_envelope(original,self.world.session.profile)
        need(row['command'] is None and row['envelope'] is None and original['commands'][0]['operation']==row['control'])
        row['envelope']=deepcopy(original);self.save(state,host_only=True);self.world.fresh_current()

    def before_publish(self,original):
        self.bound(host_only=True);need(original==self.state['inputs'][-1]['envelope']);self.world.fresh_current()

    @current_return
    def restore(self,close):
        with self.lock.held():
            self.load();need(type(close) is PicoLifecycleClose and close.world is self.world)
            close.load();need(close.state['phase']=='closed' and self.state['phase'] in ('begun','navigating'))
            need(len(self.world.state['attempts'])==2 and self.world.state['attempts'][-1]['phase']=='quiet')
            if self.state['phase']=='begun':
                state=deepcopy(self.state);state['phase']='navigating';self.save(state)
                surface=self.surface_factory(self.intent,self.owns,self.lease,self.authorized_url)
                need(type(surface) is PicoLifecycleRestoreSurface and surface.run==self.run)
                io=surface.ui.io.navigation.io
                io.bind_before_send(self.command)
                io.bind_controller_admission(self.controller,intent=self.envelope,before_publish=self.before_publish)
                surface.navigate(self.state['restorePath'])
            # If transport was uncertain, never call navigate again. Only the
            # actually restored pose/closed UI may complete the existing quiet
            # preparation. Its original thirteen World frames are the restore
            # proof too, rather than a second duplicate observation window.
            self.process.prepare(self.joined,self.native,self.domain)
            packets=self.world.originals(self.world.state['frames'][-1]);closed(packets['ui'])
            state=deepcopy(self.state);state.update(phase='prepared',preparedSha256=sha(self.process.disk),
                leases=dict(tablet=False,address=False,menu=False));self.save(state)
            result=self.world.report(packets,2)
            current=ui.current_editor(packets['ui']);need(current is None)
            result.update(editor='none',text='',generation=0,focused=False,keyboard=False,
                processShutdownPrepared=True,completeLifecycle=False,journalsRetained=True)
            return result
