"""Durable ordinary SNAP page navigation and actual launcher restoration.

This owns visibility/navigation, not capture fidelity, system destinations,
resource weak death, acoustic facts or whole Feature 11 completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,NativeUIError,Locator
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters import snapshot_work,snapshot_capture_controls,tablet_launcher_controls

NAMESPACE='ios-snapshot-page'
PRIMARY={'hud.tablet':'OverteTabletOpen','tablet.close':'OverteTabletClose'}


class SnapshotPagePending(NativeUIError):pass


class IOSSnapshotPageOwner:
    def __init__(self,runtime,selector,run,lock,sources,*,ui,phase,epoch_ms,monotonic,sleep):
        from ios.adapters.snapshot_page_runtime import IOSSnapshotPageRuntime
        need(isinstance(runtime,IOSSnapshotPageRuntime) and isinstance(ui,NativeUI) and isinstance(phase,PhaseFixtureReader)
            and phase.area=='snapshots' and phase.run==run)
        self.runtime,self.selector,self.run,self.lock,self.sources=runtime,selector,identifier(run),lock,sources
        self.binding=deepcopy(context(sources['binding']));self.guard=sources['check'];self.ui,self.phase=ui,phase
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep;self.fixture_url=phase.fixture_url
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name(NAMESPACE+'-owner.json'));self.historical=False
        lock.assert_held();self.previous=self.store.read();self.state=dict(ticket=None,phaseOriginal=None,roots=None,setupQueries=[],records=[],observation=None,actions=[],initial=None,opened=None,restored=None,abandoned=[])
        self.frames=self.frame_store()
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(self.state)
        if self.tail() is not None:restore(sources['clock_source'],self.tail())
        self.work=sources['observer'].snapshot_work(sources['clock_source'])
        if self.state['records']:self.work.last=deepcopy(self.original(self.state['records'][-1])['originals']['work'])
        send=sources['clock_source'].send
        def query(command):self.query_intent(command);return send(command)
        sources['clock_source'].send=query;sources['native'].observe_intent=self.query_intent
        send_work=self.work.send
        def work_query(command):self.query_intent(command);return send_work(command)
        self.work.send=work_query

    @classmethod
    def archive(cls,store,lock,binding,run,fixture_url):
        owner=object.__new__(cls);owner.store,owner.lock,owner.binding,owner.run=store,lock,deepcopy(context(binding)),identifier(run)
        owner.fixture_url=fixture_url;owner.historical=True;owner.guard=lambda:True
        import time
        owner.monotonic=time.monotonic;lock.assert_held();owner.previous=store.read();need(owner.previous is not None)
        owner.frames=owner.frame_store();owner.state=unpack(owner.previous['payload'])[0];owner.state=owner.decode(owner.previous);return owner

    def frame_store(self):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,'primary',self.bound,self.storage_intent,
            namespace=NAMESPACE,schema_prefix='iosSnapshotPage',monotonic=self.monotonic)

    def envelope(self,state):return dict(iosSnapshotPageOwnerVersion=1,runId=self.run,binding=self.binding,fixtureUrl=self.fixture_url,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False);return True

    def save(self):
        self.bound();need(not self.historical);value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def inventory(self,state):
        expected={self.store.path}|{self.frames.path(self.frames.expand(row)) for row in state['records']}
        if state['observation'] is not None and state['observation']['wire'] is not None:expected.add(self.frames.path(state['observation']['wire']))
        for index,path in enumerate(self.store.path.parent.iterdir()):
            need(index<8192)
            if path.name.startswith(NAMESPACE+'-'):need(path in expected)

    def phase_original(self,value,ticket):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']==dict(verb='capture',inputs=dict(mode='still',format='png')))

    def active(self):
        value=self.phase.read(self.state['phaseOriginal']);self.phase_original(value['status'],self.state['ticket'])
        need(value['status']['instance']==self.state['phaseOriginal']['instance']);return value['status']

    def frame(self,value,previous=None):
        exact(value,{'iosSnapshotPageObservationVersion','originals','clockJoin','phaseBefore','phaseAfter','queries'})
        need(type(value['iosSnapshotPageObservationVersion']) is int and value['iosSnapshotPageObservationVersion']==1)
        self.phase_original(value['phaseBefore'],self.state['ticket']);self.phase_original(value['phaseAfter'],self.state['ticket'])
        phase_packet(value['phaseAfter'],run=self.run,area='snapshots',request=value['phaseAfter']['requestId'],epoch=value['phaseAfter']['capturedEpochMs'],previous=value['phaseBefore'])
        need(same(value['phaseBefore']['activations'],value['phaseAfter']['activations']))
        need(type(value['queries']) is list and len(value['queries'])<=64)
        seen=set()
        for query in value['queries']:
            self.query(query);need(query['commandId'] not in seen);seen.add(query['commandId'])
        originals=value['originals'];exact(originals,{'ui','work'});join=validate_join(value['clockJoin'],originals)
        pid=int(self.binding['processIdentity']);need(join['nativeBefore']['processId']==pid
            and join['nativeBefore']['lifecycle']==join['nativeAfter']['lifecycle'])
        ui=ui_packet(originals['ui'],pid,join['nativeAfter']['capturedEpochMs']);work=snapshot_work.original(originals['work'])
        need(work['processId']==pid and work['runId']==self.run
            and join['nativeBefore']['capturedEpochMs']<=work['clockBefore']['epochMs']<=work['clockAfter']['epochMs']<=join['nativeAfter']['capturedEpochMs'])
        for native in (join['nativeBefore'],join['nativeAfter']):need(native['requestId'] in seen)
        need(work['requestId'] in seen)
        root=self.runtime_root();snapshot_work.admit(work,root,quiet=True)
        if previous is not None:
            old=previous['originals'];follow_native(previous['clockJoin']['nativeAfter'],join['nativeBefore'])
            need(join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs'] and join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic']
                and join['nativeBefore']['lifecycle']==previous['clockJoin']['nativeAfter']['lifecycle']
                and ui['instance']==old['ui']['instance'] and ui['elapsedMs']>=old['ui']['elapsedMs'] and ui['lastSequence']>=old['ui']['lastSequence'])
            snapshot_work.validate(work,dict(schemaVersion=1,commandId=work['requestId'],action=snapshot_work.ACTION,runId=self.run),pid,previous=old['work'])
        return value

    def runtime_root(self):
        from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
        root=IOSSnapshotCaptureOwner.root_original(self,self.state['roots'])
        packet=self.state['roots'];ids={query['commandId'] for query in self.state['setupQueries']}
        need(packet['packet']['commandId'] in ids and all(packet['clockJoin'][key]['requestId'] in ids for key in ('nativeBefore','nativeAfter')))
        return root

    def original(self,reference):return self.frame(self.frames.read(self.frames.expand(reference)))

    def tail(self):
        if self.state['records']:return self.original(self.state['records'][-1])['clockJoin']['nativeAfter']
        if self.state['roots'] is not None:return self.state['roots']['clockJoin']['nativeAfter']
        return None

    @staticmethod
    def route(frame):
        ui=frame['originals']['ui'];work=frame['originals']['work'];row=[row for row in work['source']['workers'] if not row['ended']][0]
        capture=[row for row in ui['controls'] if row['id']=='snapshot.capture']
        launcher=[row for row in ui['controls'] if 'tabletLauncherControlVersion' in row]
        if not ui['tabletShown']:
            need(not capture and not launcher);return dict(kind='closed')
        if capture:
            need(len(capture)==1 and not launcher and row['state']['open']);snapshot_capture_controls.project(ui)
            need(not capture[0]['snapshotCapturing'] and not capture[0]['snapshotProcessing'] and not capture[0]['snapshotSystemBlocked'])
            return dict(kind='snapshot',root=capture[0]['snapshotRootId'])
        if launcher:
            need(not row['state']['open']);return dict(kind='launcher',selection=tablet_launcher_controls.selection(ui))
        return dict(kind='foreign')

    @staticmethod
    def query(command):
        action=command.get('action') if type(command) is dict else None
        if action==snapshot_work.ACTION:snapshot_work.command(command)
        elif action=='feature-script-roots-observe':
            from adapters.native_script_roots import command as root_command
            root_command(command,ios=True)
        else:
            exact(command,{'schemaVersion','commandId','action'}|({'operation'} if action=='normal-ui-input' else set()))
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and action in ('normal-ui-input','feature-native-observe'))
            need(type(command['commandId']) is str and command['commandId'].startswith('ios-'));identifier(command['commandId'][4:])
            if action=='normal-ui-input':need(command['operation']=='observe')

    def query_intent(self,command):
        self.bound();self.query(command)
        if self.state['observation'] is None:
            need(self.state['roots'] is None and not self.state['records']);queries=self.state['setupQueries']
        else:queries=self.state['observation']['queries']
        need(len(queries)<64);queries.append(deepcopy(command));self.save()

    def storage_intent(self,event,wire):
        self.bound();need(event=='original' and self.state['observation'] is not None)
        self.state['observation']['wire']=deepcopy(wire);self.save();return True

    def recover_observation(self):
        pending=self.state['observation']
        if pending is None:return
        wire=pending['wire']
        if wire is None:
            # Only GET-style source observations were issued. They may be
            # abandoned under their retained nonce prefix; no input is retried.
            pending['abandoned']=True;self.save();return
        need(wire['phase'] in ('opened','saved'));value=self.frames.read(wire)
        self.frame(value,None if not self.state['records'] else self.original(self.state['records'][-1]))
        need(wire['index']==len(self.state['records'])+1);self.state['records'].append(self.frames.compact(dict(wire,phase='saved')))
        self.state['observation']=None;self.save()

    def observe(self):
        self.bound();need(not self.historical and len(self.state['records'])<384)
        self.recover_observation()
        pending=self.state['observation']
        if pending is not None:
            need(pending['abandoned']);self.state.setdefault('abandoned',[]).append(pending);self.state['observation']=None;self.save()
        self.state['observation']=dict(queries=[],wire=None,abandoned=False);self.save()
        phase_before=self.active();clock=NativeClockAcquisition(self.sources['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        clock.begin(self.epoch_ms());ui=self.sources['native'].capture();work=self.work.read(self.run)
        originals=dict(ui=ui,work=work);join=clock.finish(originals,[('ui','sampleEpochMs')]);phase_after=self.active()
        value=dict(iosSnapshotPageObservationVersion=1,originals=originals,clockJoin=join,phaseBefore=phase_before,phaseAfter=phase_after,
            queries=deepcopy(self.state['observation']['queries']))
        previous=None if not self.state['records'] else self.original(self.state['records'][-1]);self.frame(value,previous)
        reference=self.frames.write(len(self.state['records'])+1,value);self.state['records'].append(reference);self.state['observation']=None;self.save()
        return reference

    def record(self,index):need(integer(index,1,len(self.state['records'])));return self.original(self.state['records'][index-1])

    def decode(self,value):
        exact(value,{'iosSnapshotPageOwnerVersion','runId','binding','fixtureUrl','payload'});rows=unpack(value['payload'])
        need(type(value['iosSnapshotPageOwnerVersion']) is int and value['iosSnapshotPageOwnerVersion']==1 and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'ticket','phaseOriginal','roots','setupQueries','records','observation','actions','initial','opened','restored','abandoned'})
        need(type(state['records']) is list and len(state['records'])<=384 and type(state['actions']) is list and len(state['actions'])<=72
            and type(state['abandoned']) is list and len(state['abandoned'])<=128)
        prior=self.state;self.state=state
        try:
            if state['ticket'] is not None:self.phase_original(state['phaseOriginal'],state['ticket'])
            need(type(state['setupQueries']) is list and len(state['setupQueries'])<=64)
            for query in state['setupQueries']:self.query(query)
            if state['roots'] is not None:self.runtime_root()
            previous=None
            for index,reference in enumerate(state['records'],1):
                need(reference['index']==index);current=self.original(reference);self.frame(current,previous);previous=current
            labels=set()
            for action in state['actions']:
                exact(action,{'label','control','before','element','issued','returned','after'});need(type(action['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',action['label'])
                    and action['label'] not in labels and (action['control'] in PRIMARY or action['control']=='tablet.home' or tablet_launcher_controls.control_id(action['control'])))
                labels.add(action['label']);need(type(action['issued']) is bool and type(action['returned']) is bool and (not action['returned'] or action['issued']))
                need(type(action['element']) is str and re.fullmatch('/element/[A-Za-z0-9_.:%-]{1,480}',action['element']))
                before=self.record(action['before']);self.input_before(action['control'],before)
                if action['after'] is not None:need(action['issued'] and action['after']>action['before']);self.input_effect(action['control'],before,self.record(action['after']))
            for pending in state['abandoned']+([] if state['observation'] is None else [state['observation']]):
                exact(pending,{'queries','wire','abandoned'});need(type(pending['queries']) is list and len(pending['queries'])<=64 and type(pending['abandoned']) is bool)
                for query in pending['queries']:self.query(query)
                if pending['wire'] is not None:
                    self.frames.original(pending['wire'])
                    if pending['wire']['phase']!='planned':self.frame(self.frames.read(pending['wire']))
                if pending in state['abandoned']:need(pending['wire'] is None and pending['abandoned'])
            if state['initial'] is not None:need(self.route(self.record(state['initial']))['kind'] in ('launcher','snapshot','foreign'))
            if state['opened'] is not None:need(self.route(self.record(state['opened']))['kind']=='snapshot')
            if state['restored'] is not None:self.restoration()
            self.inventory(state)
        finally:self.state=prior
        return deepcopy(state)

    @staticmethod
    def row(frame,control):
        rows=[row for row in frame['originals']['ui']['controls'] if row['id']==control];need(len(rows)==1 and rows[0]['enabled']);return rows[0]

    def input_before(self,control,frame):
        route=self.route(frame);self.row(frame,control)
        if control=='hud.tablet':need(route['kind']=='closed')
        elif control=='tablet.close':need(route['kind']!='closed')
        elif control=='tablet.home':need(route['kind']=='snapshot')
        elif control=='snapshot.entry':need(route['kind']=='launcher');need(self.row(frame,control)['inputReady'])
        else:
            need(tablet_launcher_controls.control_id(control) and control.startswith('tablet.page.') and route['kind']=='launcher')
            row=self.row(frame,control);need(row['inputReady'] and row['launcherControlIndex']!=route['selection']['launcherCurrentIndex'])

    def input_effect(self,control,before,after):
        old,new=self.route(before),self.route(after)
        if control=='hud.tablet':need(new['kind']!='closed')
        elif control=='tablet.close':need(new['kind']=='closed')
        elif control=='tablet.home':need(new['kind']=='launcher')
        elif control=='snapshot.entry':need(new['kind']=='snapshot')
        else:need(new['kind']=='launcher' and new['selection']['launcherRootId']==old['selection']['launcherRootId']
            and new['selection']['launcherPageCount']==old['selection']['launcherPageCount']
            and new['selection']['launcherCurrentIndex']==int(control.rsplit('.',1)[1])-1)

    def drive(self,label,control):
        found=[row for row in self.state['actions'] if row['label']==label]
        if found:action=found[0];need(action['control']==control)
        else:
            reference=self.observe();before=self.original(reference);self.input_before(control,before);row=self.row(before,control)
            locator=Locator('accessibility id',PRIMARY.get(control,'OverteNavigation.'+control));element=self.ui._resolve(locator)
            # These are actual resolved UIKit objects. Generic proxy values
            # expose their source token; primary toolbar buttons instead retire
            # the entire object on token changes and keep its captured token.
            if control not in PRIMARY:need(self.ui._request('GET',element+'/attribute/value')==row['token'])
            current=self.original(self.observe());need(same(self.row(current,control),row))
            action=dict(label=label,control=control,before=reference['index'],element=element,issued=False,returned=False,after=None)
            need(len(self.state['actions'])<72);self.state['actions'].append(action);self.save()
        if action['after'] is not None:return self.record(action['after'])
        if not action['issued']:
            fresh=self.original(self.observe());self.input_before(control,fresh)
            need(same(self.row(fresh,control),self.row(self.record(action['before']),control)))
            self.active();self.ui._check();action['issued']=True;self.save()
            self.ui._request('POST',action['element']+'/click',{});self.ui._check();action['returned']=True;self.save()
        after=self.observe();self.input_effect(control,self.record(action['before']),self.original(after));action['after']=after['index'];self.save()
        return self.original(after)

    @operation
    def open(self,ticket):
        self.bound();identifier(ticket)
        if self.state['ticket'] is None:
            status=self.phase.read();self.phase_original(status['status'],ticket)
            self.state.update(ticket=ticket,phaseOriginal=status['status']);self.save()
        else:need(self.state['ticket']==ticket)
        need(self.state['restored'] is None)
        if self.state['roots'] is None:self.state['roots']=self.runtime.roots(self);self.runtime_root();self.save()
        if self.state['opened'] is not None:
            fresh=self.route(self.original(self.observe()));need(same(fresh,self.route(self.record(self.state['opened']))));return self.open_result()
        self.drive('open-tablet','hud.tablet')
        if self.state['initial'] is None:self.state['initial']=next(row['after'] for row in self.state['actions'] if row['label']=='open-tablet');self.save()
        initial=self.route(self.record(self.state['initial']));need(initial['kind']!='foreign')
        if initial['kind']=='snapshot':self.state['opened']=self.state['initial'];self.save();return self.open_result()
        if any(row['label']=='open-snapshot' for row in self.state['actions']):
            self.drive('open-snapshot','snapshot.entry');self.state['opened']=next(row['after'] for row in self.state['actions'] if row['label']=='open-snapshot');self.save();return self.open_result()
        for attempt in range(33):
            current=self.original(self.observe());route=self.route(current);need(route['kind']=='launcher')
            selection=route['selection'];origin=initial['selection'];need(selection['launcherRootId']==origin['launcherRootId'] and selection['launcherPageCount']==origin['launcherPageCount'])
            if any(row['id']=='snapshot.entry' for row in current['originals']['ui']['controls']):
                self.drive('open-snapshot','snapshot.entry');self.state['opened']=next(row['after'] for row in self.state['actions'] if row['label']=='open-snapshot');self.save();return self.open_result()
            visited={origin['launcherCurrentIndex']}|{int(row['control'].rsplit('.',1)[1])-1 for row in self.state['actions'] if row['label'].startswith('find-page-') and row['after'] is not None}
            targets=[index for index in range(selection['launcherPageCount']) if index not in visited]
            if not targets:raise SnapshotPagePending('Actual launcher has no observed SNAP entry')
            target=targets[0];self.drive('find-page-'+str(target),'tablet.page.'+str(target+1))
        raise SnapshotPagePending('Snapshot launcher pagination exhausted its bound')

    def open_result(self):
        need(self.state['opened'] is not None);frame=self.record(self.state['opened']);need(self.route(frame)['kind']=='snapshot')
        return dict(snapshotPageOpen=True,originalPage=self.route(self.record(self.state['initial'])),normalInputOwned=True,
            unknownInputReturns=any(row['issued'] and not row['returned'] for row in self.state['actions']),wholeFeatureRequired=True)

    @operation
    def capture(self,ticket):
        """Vertical composition without taking a second flock on the same file."""
        self.open(ticket);child=self.runtime.capture_child(self);result=child.capture(ticket)
        # The next page acquisition validates the original native prefix from
        # its own last page read through this separately owned child interval.
        return dict(capture=result,page=self.open_result(),pageRestoreRequired=True)

    def restoration(self):
        need(self.state['restored'] is not None);last=self.record(self.state['restored']);need(self.route(last)['kind']=='closed')
        initial=self.route(self.record(self.state['initial']));actions={row['label']:row for row in self.state['actions']}
        if initial['kind']=='launcher':
            if self.state['opened'] is not None:need('restore-home' in actions and actions['restore-home']['after'] is not None)
            close=actions['restore-close'];route=self.route(self.record(close['before']));need(route['kind']=='launcher')
            a,b=initial['selection'],route['selection'];need(a['launcherCurrentIndex']==b['launcherCurrentIndex'] and a['launcherPageCount']==b['launcherPageCount'])
        elif initial['kind']=='snapshot':need(self.route(self.record(actions['restore-close']['before']))['kind']=='snapshot')
        else:need(same(self.record(self.state['initial'])['originals']['ui']['controls'],self.record(actions['restore-close']['before'])['originals']['ui']['controls']))
        return dict(tabletClosed=True,originalRouteRestored=True,launcherSelectionRestored=initial['kind']=='launcher',
            inputDeliveryUnknown=any(row['issued'] and not row['returned'] for row in self.state['actions']),
            resourceRetirementRequired=True,independentWitnessRequired=True,pairedCleanupRequired=True,wholeFeatureRequired=True)

    @operation
    def restore(self):
        self.bound();need(self.state['initial'] is not None)
        if self.state['restored'] is not None:
            fresh=self.observe();need(self.route(self.original(fresh))['kind']=='closed');self.state['restored']=fresh['index'];self.save();return self.restoration()
        if any(row['label']=='restore-close' for row in self.state['actions']):
            self.drive('restore-close','tablet.close');self.state['restored']=next(row['after'] for row in self.state['actions'] if row['label']=='restore-close');self.save();return self.restoration()
        initial=self.route(self.record(self.state['initial']))
        if initial['kind']=='launcher':
            if any(row['label']=='restore-home' for row in self.state['actions']):self.drive('restore-home','tablet.home')
            current=self.original(self.observe());route=self.route(current)
            if route['kind']=='snapshot':self.drive('restore-home','tablet.home')
            elif route['kind']=='launcher':
                # Only owned pagination or a previously issued restore input
                # can account for this route. Never navigate a foreign editor.
                need(self.state['opened'] is None or any(row['label']=='restore-home' and row['issued'] for row in self.state['actions']))
            else:raise SnapshotPagePending('Snapshot restore encountered an unowned route')
            current=self.original(self.observe());selection=self.route(current);need(selection['kind']=='launcher')
            wanted=initial['selection'];actual=selection['selection'];need(actual['launcherPageCount']==wanted['launcherPageCount'])
            if actual['launcherCurrentIndex']!=wanted['launcherCurrentIndex'] or any(row['label']=='restore-page' for row in self.state['actions']):
                self.drive('restore-page','tablet.page.'+str(wanted['launcherCurrentIndex']+1))
        elif initial['kind']=='snapshot':need(self.route(self.original(self.observe()))['kind']=='snapshot')
        else:need(self.state['opened'] is None and self.route(self.original(self.observe()))['kind']=='foreign')
        self.drive('restore-close','tablet.close');self.state['restored']=next(row['after'] for row in self.state['actions'] if row['label']=='restore-close');self.save()
        return self.restoration()
