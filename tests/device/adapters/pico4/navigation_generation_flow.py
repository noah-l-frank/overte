"""Normal actions 13–15 on the original observed G1 lineage.

The common v16 recipe is authoritative. G0 and restart journals are immutable;
this generation owns only its later normal Open/Delete/Close inputs. This
private composition does not advertise a public feature or whole cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import need,exact,number,fresh
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.pico4.navigation import integer,identifier
from adapters.token_places_ui import control_id
from openxr_input.controller_protocol import validate_envelope
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation_originals import verify_archive,read_original
from adapters.script_journey.history import same,pack,unpack
from feature_journeys.contract import arguments
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1


class NavigationGenerationFlow:
    """One continuation of the same recipe, with no original-file migration."""
    def __init__(self,continuation,runtime_factory,open_factory,close_factory,bookmark_factory):
        need(all(callable(fn) for fn in (runtime_factory,open_factory,close_factory,bookmark_factory)))
        self.previous=continuation;self.parent=continuation.prefix;self.lock=self.parent.lock
        self.run=self.parent.run;self.restart=continuation.restart()
        need(self.restart.state is not None and self.restart.state['phase']=='observed'
            and continuation.continuation_disk['phase']=='ready')
        self.binding=deepcopy(self.restart.state['proof']['input']['newBinding'])
        self.restart_sha=json_digest(self.restart.disk);self.previous_sha=json_digest(continuation.continuation_disk)
        self.runtime_factory,self.open_factory,self.close_factory,self.bookmark_factory=runtime_factory,open_factory,close_factory,bookmark_factory
        self.store=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-parent.json'))
        self.scope_sha=json_digest(self.scope());self.disk=self.store.read();self.state=None
        self.runtime=None;self.open_owner=self.close_owner=None;self.native_anchor=None
        self.adopted=None
        # Save exact bound-method objects once for the existing original IO
        # single-owner admission API. No generic forwarding API is introduced.
        self.qml_callback=self.before_send;self.controller_callback=self.before_controller
        self.intent_callback=self.controller_intent;self.publish_callback=self.before_publish
        if self.disk is not None:self.load()

    def scope(self):
        return dict(runId=self.run,binding=self.binding,restartSha256=self.restart_sha,
            previousSha256=self.previous_sha,path=str(self.store.path),sourceLock=str(self.lock.path))

    def control(self):
        self.memory_control()
        need(same(self.restart.store.read(),self.restart.disk)
            and json_digest(self.previous.continuation_store.read())==self.previous_sha)
        self.restart.scope()
        if self.state is not None:need(same(self.store.read(),self.disk))

    def memory_control(self):
        self.lock.assert_held();self.parent.control()
        need(self.scope_sha==json_digest(self.scope()) and json_digest(self.restart.disk)==self.restart_sha
            and same(unpack(self.restart.disk['payload']),[self.restart.state])
            and json_digest(self.previous.continuation_disk)==self.previous_sha)
        if self.state is not None:need(same(unpack(self.disk['payload']),[self.state]))

    def validate(self,value):
        exact(value,{'phase','fixture','completed','active','receipt','frames','qml','controllers','openSha256','closeSha256','bookmarksSha256','tabPending','tabHistory'})
        need(value['phase'] in ('ready','acting') and type(value['completed']) is list and len(value['completed'])<=3
            and (value['active'] is None)==(value['phase']=='ready') and type(value['frames']) is list and len(value['frames'])<=16
            and type(value['qml']) is list and len(value['qml'])<=128 and type(value['controllers']) is list and len(value['controllers'])<=16)
        ids=[]
        for command in value['qml']:
            exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'})
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                and all(identifier(command[k]) for k in ('commandId','bridgeId','generation','controlToken'))
                and command['bridgeId']==self.binding['sessionId'] and integer(command['sequence']) and command['sequence']>=1
                and integer(command['observedElapsedMs']) and control_id(command['controlId']) and command['action']=='activate')
            ids.append(command['commandId'])
        need(len(ids)==len(set(ids)))
        for index,record in enumerate(value['controllers']):
            exact(record,{'ticket','kind','envelope'});envelope=record['envelope']
            validate_envelope(envelope,self.restart.state['profile'])
            need(record['kind'] in ('open','open-home','close-home','close') and len(envelope['commands'])==1
                and envelope['sessionNonce']==self.restart.state['newSession']['sessionNonce'] and type(envelope['sequence']) is int
                and envelope['sequence']==self.restart.state['newSession']['nextSequence']+index)
            expected='tablet.open' if record['kind']=='open' else 'tablet.close' if record['kind']=='close' else 'input.primary'
            need(envelope['commands'][0]['operation']==expected)
        tickets=[]
        for index,item in enumerate(value['completed']):
            exact(item,{'ticket','verb'});need(item['verb']==SCENARIOS['world-navigation']['steps'][12+index]['verb']);tickets.append(item['ticket'])
        need(len(set(tickets))==len(tickets))
        if value['active'] is not None:
            active=value['active'];exact(active,{'arguments','stage'})
            call=arguments('feature.world-navigation.act',active['arguments']);index=len(value['completed']);need(index<3)
            row=SCENARIOS['world-navigation']['steps'][12+index]
            need(call['runId']==self.run and call['fixtureUrl']==self.parent.phase.fixture_url
                and same(dict(verb=call['verb'],inputs=call['inputs']),dict(verb=row['verb'],inputs=expand(row['inputs'],context(self.run))))
                and active['stage'] in ('open','delete','tab','close','sample'))
        need(type(value['tabHistory']) is list and len(value['tabHistory'])<=1)
        for pending in value['tabHistory']+([] if value['tabPending'] is None else [value['tabPending']]):
            exact(pending,{'placesInputVersion','action','controlId','controlToken','scope'})
            need(type(pending['placesInputVersion']) is int and pending['placesInputVersion']==1
                and pending['action']=='activate' and pending['controlId']=='places.tab.0'
                and pending['scope']['instance']==self.binding['sessionId']
                and pending['scope']['processId']==int(self.binding['processIdentity'].split(':',1)[0]))
        fixture=value['fixture'];old=self.restart.state['fixture']
        phase_packet(fixture,run=self.run,area='world-navigation',request=fixture['requestId'],epoch=fixture['capturedEpochMs'])
        need(fixture['instance']==old['instance'] and same(fixture['activations'][:len(old['activations'])],old['activations']))
        for index,item in enumerate(value['completed']):
            row=SCENARIOS['world-navigation']['steps'][12+index]
            matches=[entry for entry in fixture['activations'] if entry['ticket']==item['ticket']]
            need(len(matches)==1 and same(matches[0]['stimulus'],dict(verb=row['verb'],inputs=expand(row['inputs'],context(self.run)))))
        self.validate_links(value)
        for frame in value['frames']:self.source().project(frame);self.parent.original_facts(frame)
        for index in range(1,len(value['frames'])):self.source().advance_frames(value['frames'][index-1],value['frames'][index])

    def child_original(self,name,key,digest):
        body=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-'+name+'.json')).read()
        exact(body,{key,'scope','payload'})
        need(type(body[key]) is int and body[key]==1 and same(body['scope'],self.scope()) and json_digest(body)==digest)
        rows=unpack(body['payload']);need(len(rows)==1 and type(rows[0]) is dict)
        return rows[0]

    def validate_links(self,value):
        # Read only actual private host journals. This also runs inside locked
        # publication callbacks, so no source/SDK/phase/Session call belongs here.
        count=len(value['completed']);active=value['active'];stage=None if active is None else active['stage']
        if active is not None:
            need(stage in (('open','sample') if count==0 else ('delete','tab','sample') if count==1 else ('close','sample')))
        opened=count>=1 or count==0 and stage=='sample'
        closed=count==3 or count==2 and stage=='sample'
        need((value['openSha256'] is not None)==opened and (value['closeSha256'] is not None)==closed
            and (value['bookmarksSha256'] is not None)==opened)
        if not opened:return
        original=self.child_original('open','navigationGenerationOpenVersion',value['openSha256'])
        ticket=value['completed'][0]['ticket'] if count else active['arguments']['ticket']
        need(original['phase']=='ready' and original['ticket']==ticket and original['pending'] is None
            and original['adoptedSha256']==json_digest(original['adoptedOriginal'])
            and same(value['receipt'],dict(ticket=ticket,afterEpochMs=original['after']['before']['ui']['observedEpochMs'])))
        adopted=NavigationBookmarks.archive(original['adoptedOriginal'])
        need(same(adopted['binding'],self.binding) and adopted['runId']==self.run and adopted['active'] is None and not adopted['completed'])
        handoff=unpack(adopted['handoff']);need(len(handoff)==1 and same(handoff[0]['previous'],self.restart.bookmark_original())
            and same(handoff[0]['proof']['oldNative'],self.restart.state['oldNative'])
            and same(handoff[0]['proof']['oldBookmark'],self.restart.state['oldBookmark'])
            and same(handoff[0]['proof']['input']['newBinding'],self.binding))
        actual=NavigationBookmarks.archive(PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-bookmarks.json')).read())
        need(same(actual['binding'],self.binding) and actual['runId']==self.run
            and same(actual['handoff'],adopted['handoff']) and same(actual['original'],adopted['original'])
            and actual['nativeInstance']==adopted['nativeInstance'])
        if stage!='delete':need(json_digest(actual)==value['bookmarksSha256'])
        if count>=2 or count==1 and stage in ('tab','sample'):
            delete_ticket=value['completed'][1]['ticket'] if count>=2 else active['arguments']['ticket']
            need(actual['active'] is None and len(actual['completed'])==1
                and actual['completed'][0]['verb']=='bookmark-delete' and actual['completed'][0]['ticket']==delete_ticket)
        if closed:
            final=self.child_original('close-join','navigationGenerationCloseVersion',value['closeSha256'])
            close_ticket=value['completed'][2]['ticket'] if count==3 else active['arguments']['ticket']
            need(final['phase']=='closed' and final['ticket']==close_ticket)
            tablet=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-tablet-close.json')).read()
            need(tablet is not None and type(tablet['navigationTabletCloseVersion']) is int and tablet['navigationTabletCloseVersion']==3
                and tablet['runId']==self.run and same(tablet['binding'],self.binding)
                and tablet['sourceKind']=='generation-places' and json_digest(tablet)==final['closeSha256'])

    def load(self):
        body=self.store.read();exact(body,{'navigationGenerationFlowVersion','scope','payload'})
        need(type(body['navigationGenerationFlowVersion']) is int and body['navigationGenerationFlowVersion']==VERSION and same(body['scope'],self.scope()))
        rows=unpack(body['payload']);need(len(rows)==1);self.validate(rows[0]);self.disk=deepcopy(body);self.state=rows[0]

    def save(self,value,*,host_only=False):
        if host_only:self.memory_control()
        else:self.control()
        self.validate(value)
        body=dict(navigationGenerationFlowVersion=VERSION,scope=self.scope(),payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value)

    def source(self):
        if self.runtime is None:
            value=self.runtime_factory(self);exact(value,{'source','native','presence','session'})
            self.previous.runtime_scope(self.restart,value['source'])
            need(same(value['session'].profile,self.restart.state['profile']));self.runtime=value
        return self.runtime['source']

    def fence(self):
        self.control();source=self.source();need(source.guard() is not False)
        self.previous.runtime_scope(self.restart,source)
        phase=self.parent.phase.read();old=self.restart.state['fixture']
        need(phase['status']['instance']==old['instance'] and same(phase['status']['activations'][:len(old['activations'])],old['activations']))
        if self.state is not None:
            ticket=self.state['active']['arguments']['ticket'] if self.state['active'] is not None else self.state['completed'][-1]['ticket']
            need(phase['ticket']==ticket and same(phase['status']['activations'],self.state['fixture']['activations']))
        epoch=self.runtime['native'].clock_ms();fresh(phase['status']['capturedEpochMs'],epoch)
        return phase

    def before_send(self,command):
        self.control();need(self.state is not None and self.state['phase']=='acting')
        if self.state['active']['stage']=='tab':
            pending=self.state['tabPending'];need(pending is not None);scope=pending['scope']
            need(command['controlId']==pending['controlId'] and command['controlToken']==pending['controlToken']
                and command['action']=='activate' and command['bridgeId']==scope['instance']
                and command['generation']==scope['generation'] and command['sequence']==scope['sequence']+1)
        elif self.state['active']['stage']=='delete':
            owner=self.bookmarks();need(owner.state['active'] is not None and owner.state['active']['pending'] is not None)
            pending=owner.state['active']['pending'];scope=pending['scope']
            need(command['controlId']==pending['controlId'] and command['controlToken']==pending['controlToken']
                and command['action']==pending['action'] and command['bridgeId']==scope['instance']
                and command['generation']==scope['generation'] and command['sequence']==scope['sequence']+1)
        else:self.child().admit_qml(command)
        current=deepcopy(self.state);current['qml'].append(deepcopy(command));self.save(current)
        self.fence()  # Exact phase after durable original command CAS, before writer.

    def record_controller(self,envelope,kind):
        self.memory_control();need(self.state['phase']=='acting')
        value=deepcopy(self.state);value['controllers'].append(dict(ticket=value['active']['arguments']['ticket'],kind=kind,envelope=deepcopy(envelope)))
        self.save(value,host_only=True)

    def controller_recorded(self,envelope,kind):
        self.memory_control();need(self.state['controllers'] and same(self.state['controllers'][-1],
            dict(ticket=self.state['active']['arguments']['ticket'],kind=kind,envelope=envelope)))

    def before_controller(self,operation):return self.child().before_controller(operation)
    def controller_intent(self,envelope):return self.child().intent(envelope)
    def before_publish(self,envelope):return self.child().before_publish(envelope)

    def child(self):
        need(self.state is not None and self.state['active'] is not None)
        stage=self.state['active']['stage']
        if stage=='open':
            if self.open_owner is None:self.open_owner=self.open_factory(self)
            return self.open_owner
        if stage=='close':
            if self.close_owner is None:self.close_owner=self.close_factory(self)
            return self.close_owner
        # Delete uses the existing adopted NavigationBookmarks owner, not a
        # parallel text/delete dispatcher. Its exact intent is joined below
        # once normal Open has produced its original handoff.
        need(False)

    def bookmarks(self):
        if self.adopted is None:self.adopted=self.bookmark_factory(self,False)
        need(self.adopted is not None and isinstance(self.adopted,NavigationBookmarks)
            and same(self.adopted.binding,self.binding) and self.adopted.run==self.run
            and self.adopted.store.path==self.lock.path.with_name('navigation-prefix-generation-1-bookmarks.json'))
        if self.open_owner is None:self.open_owner=self.open_factory(self)
        original=self.open_owner
        need(original.state is not None and original.state['phase']=='ready' and json_digest(original.disk)==self.state['openSha256'])
        old=original.state['adoptedOriginal'];current=self.adopted.state
        need(same(current['handoff'],old['handoff']) and same(current['original'],old['original'])
            and current['nativeInstance']==old['nativeInstance'])
        return self.adopted

    def tab_intent(self,pending):
        self.control();need(self.state['active']['stage']=='tab' and self.state['tabPending'] is None
            and not self.state['tabHistory'] and pending['controlId']=='places.tab.0')
        value=deepcopy(self.state);value['tabPending']=deepcopy(pending);self.save(value)

    def return_directory(self):
        from adapters.token_places_ui import TokenPlacesUI
        ui=TokenPlacesUI(self.source().normal.io,self.tab_intent,self.run,
            monotonic=self.parent.monotonic,sleep=self.runtime['native'].sleep)
        pending=self.state['tabPending']
        if pending is None:
            current=ui.capture()
            if ui.page(current)['tab']==0:return
            need(not self.state['tabHistory']);ui.input('places.tab.0');pending=self.state['tabPending']
        # A cold uncertain Tab input is only observed; a second normal click
        # cannot be inferred safe from a lost response or a current token.
        value=ui.wait(lambda row:ui.page(row)['tab']==0)
        old=pending['scope'];current=value['scope']
        need(all(current[k]==old[k] for k in ('instance','generation','processId'))
            and current['sequence']==old['sequence']+1)
        next_value=deepcopy(self.state);next_value['tabHistory'].append(deepcopy(pending));next_value['tabPending']=None;self.save(next_value)

    def act(self,call):
        call=deepcopy(arguments('feature.world-navigation.act',call));need(self.parent.role=='primary' and self.lock._owner is None)
        with self.lock.held():
            self.control();index=0 if self.state is None else len(self.state['completed']);need(index<3)
            row=SCENARIOS['world-navigation']['steps'][12+index]
            need(call['runId']==self.run and call['fixtureUrl']==self.parent.phase.fixture_url
                and same(dict(verb=call['verb'],inputs=call['inputs']),dict(verb=row['verb'],inputs=expand(row['inputs'],context(self.run)))))
            if self.state is None or self.state['active'] is None:
                need(self.source().guard() is not False);phase=self.parent.phase.read()
                need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
                if self.state is None:
                    value=dict(phase='acting',fixture=deepcopy(phase['status']),completed=[],active=None,tabPending=None,tabHistory=[],
                        receipt=deepcopy(self.parent.state['receipt']),frames=[],qml=[],controllers=[],
                        openSha256=None,closeSha256=None,bookmarksSha256=None)
                else:value=deepcopy(self.state);value.update(phase='acting',fixture=deepcopy(phase['status']))
                value['active']=dict(arguments=call,stage=('open','delete','close')[index]);self.save(value)
            need(same(self.state['active']['arguments'],call));self.fence()
            if self.state['active']['stage']=='open':
                child=self.child();child.act(call['ticket']);need(child.state['phase']=='ready')
                value=deepcopy(self.state);value.update(openSha256=json_digest(child.disk),bookmarksSha256=child.state['adoptedSha256'],
                    receipt=dict(ticket=call['ticket'],afterEpochMs=child.state['after']['before']['ui']['observedEpochMs']))
                value['active']['stage']='sample';self.save(value)
            elif self.state['active']['stage']=='delete':
                owner=self.bookmarks();owner.act(call['ticket'],'bookmark-delete')
                value=deepcopy(self.state);value.update(bookmarksSha256=json_digest(owner.store.read()))
                value['active']['stage']='tab';self.save(value)
            if self.state['active']['stage']=='tab':
                self.return_directory()
                value=deepcopy(self.state);value['active']['stage']='sample';self.save(value)
            if self.state['active']['stage']=='close':
                child=self.child();child.close(call['ticket']);need(child.state['phase']=='closed')
                value=deepcopy(self.state);value['closeSha256']=json_digest(child.disk);value['active']['stage']='sample';self.save(value)
            # Keep actual measured facts. Matching the shared step is acceptance
            # checking only, never a source of the returned projected values.
            phase=self.fence();started=self.parent.now();requested=self.runtime['native'].clock_ms()
            frame=self.source().capture(self.state['receipt'],phase['status'],lookup_receipt=self.parent.state['lookupReceipt'])
            value=deepcopy(self.state);value['frames'].append(frame);self.save(value)
            facts=self.source().project(frame);self.parent.original_facts(frame)
            expected=expand(row['state'],context(self.run));need(all(facts[key]==item for key,item in expected.items()))
            value=deepcopy(self.state);value['completed'].append(dict(ticket=call['ticket'],verb=call['verb']));value.update(phase='ready',active=None);self.save(value)
            self.fence();captured=frame['before']['ui']['observedEpochMs'];runtime=self.runtime
            guards=(runtime['source'].guard,runtime['native'].guard);pins=self.pin_current(runtime)
        self.finalize(runtime,requested,started,captured,guards,pins)
        return dict(performed=True)

    def observe(self):
        from feature_journeys.phase_fixture import PhasePending
        p=self.parent;need(self.lock._owner is None)
        with self.lock.held():
            current=self.store.read()
            if not same(current,self.disk):self.load()
            self.control()
            if self.state is None or self.state['phase']!='ready':raise PhasePending('The original G1 Navigation input remains unresolved')
            source=self.source();runtime=self.runtime;phase=self.fence()
            store=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-'+p.role+'-sources.json'))
            scope=dict(runId=self.run,binding=self.binding,role=p.role,restartSha256=self.previous.continuation_disk['restartSha256'])
            chunks=ChatSourceChunks(store,scope);old=store.read();manifest=[] if old is None else old['chunks'];frames=chunks.load(manifest)
            if old is not None:
                exact(old,{'navigationGenerationSamplesVersion','scope','phase','chunks'})
                need(type(old['navigationGenerationSamplesVersion']) is int and old['navigationGenerationSamplesVersion']==1
                    and same(old['scope'],scope) and old['phase']=='ready')
            previous=self.restart.state['newFrame']
            for frame in frames:
                source.project(frame);p.original_facts(frame);source.advance_frames(previous,frame);previous=frame
            reading=dict(navigationGenerationSamplesVersion=1,scope=scope,phase='reading',chunks=manifest);store.write(reading,old)
            started=p.now();requested=runtime['native'].clock_ms()
            frame=source.capture(self.state['receipt'],phase['status'],lookup_receipt=p.state['lookupReceipt'])
            manifest=chunks.append(frame,manifest);facts=source.project(frame);p.original_facts(frame);source.advance_frames(previous,frame)
            ready=deepcopy(reading);ready.update(phase='ready',chunks=manifest);store.write(ready,reading);chunks.verify();self.fence()
            original=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-'+p.role+'-sources.json')).read()
            captured=frame['before']['ui']['observedEpochMs']
            guards=(source.guard,runtime['native'].guard);pins=self.pin_current(runtime)
            result=dict(sequence=len(original['chunks'])+len(manifest),capturedEpochMs=captured,state=facts,
                fullNavigationRecipe=False,deviceAcceptance=False,journalsRetained=True,generation=1)
        self.finalize(runtime,requested,started,captured,guards,pins)
        need(same(store.read(),ready));chunks.verify()
        # Immutable copies and physical archive work are part of publication.
        self.finalize(runtime,requested,started,captured,guards,pins)
        return result

    def pin_current(self,runtime):
        paths=[self.store.path,runtime['source'].normal.io.original.navigation.path]
        for name in ('open','bookmarks','close-join','tablet-close'):
            path=self.lock.path.with_name('navigation-prefix-generation-1-'+name+'.json')
            if path.exists():paths.append(path)
        return [read_original(path) for path in paths]

    def finalize(self,runtime,requested,started,captured,guards,pins):
        self.parent.control()
        need(self.scope_sha==json_digest(self.scope()) and runtime['source'].guard is guards[0] and runtime['native'].guard is guards[1])
        need(self.lock._owner is None and same(self.store.read(),self.disk) and same(unpack(self.disk['payload']),[self.state]))
        need(same(self.pin_current(runtime),pins))
        verify_archive(self.restart.state['files'],self.restart.store.path.parent,self.run,self.restart.state['normalUiPath'])
        need(same(self.previous.continuation_store.read(),self.previous.continuation_disk)
            and same(self.restart.store.read(),self.restart.disk) and json_digest(self.restart.disk)==self.restart_sha)
        need(runtime['native'].guard() is not False);self.previous.runtime_scope(self.restart,runtime['source'])
        with runtime['session']._lock():session=runtime['session']._load()
        need(session is not None and session['processIdentity']==self.binding['processIdentity']
            and session['sessionNonce']==self.restart.state['newSession']['sessionNonce']
            and session['nextSequence']==self.restart.state['newSession']['nextSequence']+len(self.state['controllers']))
        phase=self.parent.phase.read();need(phase['ticket']==self.state['completed'][-1]['ticket']
            and same(phase['status']['activations'],self.state['fixture']['activations']))
        epoch=runtime['native'].clock_ms();now=self.parent.now();fresh(captured,epoch)
        need(runtime['source'].guard is guards[0] and runtime['native'].guard is guards[1]
            and now>=started and max(epoch-captured,requested-captured+(now-started)*1000)<=1500)
