"""Whole Create action/cleanup ownership on ordinary product controls.

This coordinator records actual UUID ownership before naming/editing it. It
never returns observed feature success: the separate original observation owner
must join both actors, rendered pixels, files and native lifetime drainage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact, need
from adapters.graphics_subject_geometry import rotate
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import Locator, NativeUI, NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments, identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters import create_state, create_work
from ios.adapters.create_action_owner import CreateActionOwner, CreateInputPending
from ios.adapters.create_files import OwnedCreateFiles
from ios.adapters.create_inputs import IOSCreateUI
from ios.adapters.create_marker_identity import PreparedCreateMarker
from ios.adapters.create_product_state import adopt_created, selected
from ios.adapters.create_rez_client import CreateRezClient
from ios.adapters.create_world_input import CreateWorldInput
from ios.adapters.native_geometry import OriginalGeometry

VERSION = 1


def semantic_map(packet, exclude=()):
    source = create_state.live(packet)
    return {row['id']:{key:row[key] for key in ('hostType','createdEpochUs','semanticBytes','semanticSha256')}
            for row in source['tree']['entities'] if row['id'] not in exclude}


def editor(packet):
    roots = [row for row in create_state.live(packet)['roots'] if not row['destroyed'] and row['kind'] == 'editor']
    need(len(roots) <= 1); return None if not roots else deepcopy(roots[0])


class CreateActions:
    def __init__(self, store, lock, binding, run, fixture_url, guard, *, source, work, scripts_root,
                 ui, normal, inputs, cleanup_inputs, files, rez, phase, geometry, world_factory, marker_scope,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(store, PrivateFeatureState) and isinstance(lock, ScriptSourceLock) and callable(guard)
             and isinstance(source, create_state.IOSCreateState) and isinstance(work, create_work.IOSCreateWork)
             and isinstance(ui, IOSCreateUI) and isinstance(normal, NativeUI) and isinstance(inputs, CreateActionOwner)
             and isinstance(cleanup_inputs, CreateActionOwner) and isinstance(files, OwnedCreateFiles)
             and isinstance(rez, CreateRezClient) and isinstance(phase, PhaseFixtureReader) and isinstance(geometry, OriginalGeometry)
             and all(callable(fn) for fn in (world_factory, monotonic, sleep)))
        need(isinstance(marker_scope,PreparedCreateMarker) and marker_scope.state['phase']=='ready'
             and same(marker_scope.binding,binding) and marker_scope.run==run and marker_scope.fixture_url==fixture_url)
        self.store, self.lock, self.binding = store, lock, deepcopy(context(binding))
        self.run, self.fixture_url, self.guard = identifier(run), fixture_url, guard
        self.source, self.work, self.scripts_root, self.ui, self.normal = source, work, scripts_root, ui, normal
        self.inputs, self.cleanup_inputs, self.files, self.rez, self.phase = inputs, cleanup_inputs, files, rez, phase
        self.geometry, self.world_factory, self.monotonic, self.sleep = geometry, world_factory, monotonic, sleep
        self.marker_scope=marker_scope
        need(str(source.pid) == str(work.pid) == binding['processIdentity'] and phase.run == run and phase.area == 'create'
             and same(inputs.binding, binding) and same(cleanup_inputs.binding, binding) and same(files.binding, binding)
             and same(rez.binding, binding) and rez.config['domainId'] != '00000000-0000-0000-0000-000000000000')
        lock.assert_held(); self.previous = store.read(); self.state = None if self.previous is None else self.decode(self.previous)
        inputs.load(); cleanup_inputs.load()
        if self.state is not None:
            packets = [call['after'] for call in self.state['calls'] if call['after'] is not None]
            last = packets[-1] if packets else self.state['baseline']['create']
            if source.last is None: source.last = deepcopy(last)
            if work.last is None: work.last = deepcopy(self.state['baseline']['work'])

    def envelope(self):
        return dict(iosCreateActionsVersion=VERSION, binding=self.binding, runId=self.run,
                    fixtureUrl=self.fixture_url, scriptsRoot=self.scripts_root, payload=pack([self.state]))

    def decode(self, value):
        exact(value, {'iosCreateActionsVersion','binding','runId','fixtureUrl','scriptsRoot','payload'})
        need(type(value['iosCreateActionsVersion']) is int and value['iosCreateActionsVersion'] == VERSION
             and same(value['binding'], self.binding) and value['runId'] == self.run and value['fixtureUrl'] == self.fixture_url
             and value['scriptsRoot'] == self.scripts_root)
        entries = unpack(value['payload']); need(len(entries) == 1); state = entries[0]
        exact(state, {'phase','baseline','editorBaseline','owned','voxelBaseline','voxelOriginal','picker','calls','cleanup'})
        need(state['phase'] in ('active','cleaning','retired') and type(state['calls']) is list and len(state['calls']) <= 64
             and type(state['owned']) is list and len(state['owned']) <= 8)
        create_state.original(state['baseline']['create']); create_work.admit(state['baseline']['work'], self.scripts_root, quiet=True)
        exact(state['baseline'],{'create','work','geometry','rez','marker'})
        need(state['baseline']['create']['runId'] == self.run and state['baseline']['create']['processId'] == int(self.binding['processIdentity']))
        ids = set()
        for owned in state['owned']:
            exact(owned, {'id','role','ticket','before','after','deleted'})
            identifier(owned['ticket']); need(owned['role'] in ('model','cube','voxel') and type(owned['deleted']) is bool and owned['id'] not in ids)
            ids.add(owned['id']); original = adopt_created(owned['before'],owned['after'],list(ids-{owned['id']}),self.run)
            need(original['id'] == owned['id'])
        tickets = set()
        for index, call in enumerate(state['calls']):
            exact(call, {'query','phase','before','after','auxInputs','creationBefore'})
            query = call['query']; arguments('feature.create.act',query); need(query['runId'] == self.run and query['fixtureUrl'] == self.fixture_url
                and query['ticket'] not in tickets and call['phase'] in ('acting','acknowledged') and type(call['auxInputs']) is list)
            tickets.add(query['ticket']); create_state.original(call['before'])
            if call['after'] is not None: create_state.original(call['after'])
            need(call['phase'] != 'acknowledged' or call['after'] is not None)
            if index < len(state['calls'])-1: need(call['phase'] == 'acknowledged')
        if state['voxelBaseline'] is not None:
            create_state.original(state['voxelOriginal']);baseline=state['voxelBaseline'];exact(baseline,{'id','source'})
            rows=[row for row in state['voxelOriginal']['source']['entities'] if row['id']==baseline['id']]
            need(len(rows)==1 and rows[0]['type']=='PolyVox' and rows[0]['voxels']['ready'] and same(rows[0]['voxels'],baseline['source']))
        else:need(state['voxelOriginal'] is None)
        if state['picker'] is not None:
            exact(state['picker'],{'role','rootId','ticket'});need(state['picker']['role'] in ('import','export'))
            create_state.uuid(state['picker']['rootId']);identifier(state['picker']['ticket'])
        if state['cleanup'] is not None:
            cleanup=state['cleanup'];exact(cleanup,{'query','phase','before','after','auxInputs','creationBefore','steps'})
            need(state['phase'] in ('cleaning','retired') and cleanup['phase'] in ('acting','acknowledged'))
            names=[]
            for step in cleanup['steps']:
                exact(step,{'name','after'});need(step['name'] in ('rez','pickers','entities','editor'));names.append(step['name'])
                if step['after'] is not None:create_state.original(step['after'])
            need(len(names)==len(set(names)))
        return state

    def bound(self):
        self.lock.assert_held(); need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound(); value = self.envelope(); self.decode(value); self.store.write(value,self.previous)
        need(same(self.store.read(),value)); self.previous = deepcopy(value)

    def read(self,*,allow_new=False):
        self.bound(); packet = self.source.read(self.run); source = create_state.live(packet)
        need(packet['iosCreateStateVersion'] >= 2 and source['domainId'] == self.rez.config['domainId'])
        if self.state is not None:
            actual = semantic_map(packet,[row['id'] for row in self.state['owned']]); baseline = semantic_map(self.state['baseline']['create'])
            need(same({id_:actual[id_] for id_ in baseline if id_ in actual},baseline)
                 and (allow_new or set(actual) == set(baseline)))
        return packet

    def wait(self,predicate,*,allow_new=False):
        started = previous = self.monotonic()
        for attempt in range(121):
            packet = self.read(allow_new=allow_new)
            if predicate(create_state.live(packet)): return packet
            now = self.monotonic(); need(previous <= now < started+12); previous = now
            if attempt < 120: self.sleep(.1)
        raise NativeUIError('Original Create effect did not settle; input remains owned')

    def prepare(self):
        self.bound(); need(self.state is None)
        packet = self.read(); geometry = self.geometry.capture(); work = self.work.read(self.run)
        create_work.admit(work,self.scripts_root,quiet=True); source = create_state.live(packet)
        owned_marker=self.marker_scope.state['admission']['marker']
        markers=[row for row in source['entities'] if row['id']==owned_marker['id']]
        need(len(markers)==1 and same(markers[0],owned_marker))
        need(not source['tabletShown'] and not any(not row['destroyed'] and row['kind'] != 'editor' for row in source['roots'])
             and not any(row['name'].startswith('e2e-'+self.run+'-') and row['id']!=owned_marker['id'] for row in source['entities'])
             and geometry['observation']['nativeUi']['keyboardVisible'] is False
             and geometry['observation']['nativeUi']['imeInsetBottom'] == 0)
        original_editor = editor(packet)
        # An already instantiated editor may contain a search draft which the
        # passive State3 source does not expose. Preserve it by refusing setup
        # before any input; never invent an empty original search value.
        need(original_editor is None)
        initial_rez = self.rez.request('observe')
        self.state = dict(phase='active',baseline=dict(create=packet,work=work,geometry=geometry,rez=initial_rez,marker=owned_marker),
                          editorBaseline=original_editor,owned=[],voxelBaseline=None,voxelOriginal=None,picker=None,calls=[],cleanup=None); self.save()
        return deepcopy(self.state)

    def current_call(self):
        return self.state['cleanup'] if self.state['phase'] == 'cleaning' else self.state['calls'][-1]

    def tablet(self,shown):
        packet = self.read()
        if packet['source']['tabletShown'] == shown: return packet
        call = self.current_call(); event = dict(kind='tablet',shown=shown,before=packet,after=None)
        call['auxInputs'].append(event); self.save()
        self.normal.click(Locator('accessibility id','OverteTabletOpen' if shown else 'OverteTabletClose'))
        after = self.wait(lambda source:source['tabletShown'] == shown); event['after'] = after; self.save(); return after

    def active_owned(self,role=None):
        rows = [row for row in self.state['owned'] if not row['deleted'] and (role is None or row['role'] == role)]
        need(len(rows) <= 1); return None if not rows else rows[0]

    def create(self,role,callback,ticket):
        need(self.active_owned() is None)
        before = self.read(); call = self.current_call(); call['creationBefore'] = before; self.save()
        callback()
        after = self.wait(lambda source: bool(selected(source)) and any(row['id'] not in {old['id'] for old in before['source']['entities']} for row in source['entities']),allow_new=True)
        owned = adopt_created(before,after,[row['id'] for row in self.state['owned']],self.run)
        need(owned['type'] == ('Model' if role == 'model' else 'PolyVox' if role == 'voxel' else 'Shape')
             or role == 'cube' and owned['type'] == 'Box')
        record = dict(id=owned['id'],role=role,ticket=ticket,before=before,after=after,deleted=False)
        self.state['owned'].append(record); self.save()  # Ownership precedes the next edit.
        self.ui.name_and_size(owned['id'],'e2e-'+self.run+'-'+role)
        if role == 'voxel':
            # The real detailed dialog initially places its 8-voxel volume
            # 12.8m ahead of the avatar. Move only this admitted owned UUID via
            # ordinary position fields into the measured current camera view.
            view = self.read()['source']['view']; offset = rotate([0,0,-3],view['rotation'])
            self.ui.position(owned['id'],[a+b for a,b in zip(view['position'],offset)])
        self.wait(lambda source:any(row['id'] == owned['id'] and row['name'] == 'e2e-'+self.run+'-'+role
            and all(abs(size-1)<.0001 for size in row['dimensions']) for row in source['entities']))
        if role == 'model':
            self.wait(lambda source:any(row['id'] == owned['id'] and row['model']['loaded']
                and row['model']['addedToScene'] and not row['model']['failed'] for row in source['entities']))
        if role == 'voxel':
            packet = self.wait(lambda source:any(row['id'] == owned['id'] and row['voxels'].get('ready') and row['voxels'].get('onCount',0)>0 for row in source['entities']))
            row = next(row for row in packet['source']['entities'] if row['id'] == owned['id'])
            self.state['voxelBaseline'] = dict(id=row['id'],source=deepcopy(row['voxels']))
            self.state['voxelOriginal']=deepcopy(packet);self.save()

    def delete(self):
        owned = self.active_owned(); need(owned is not None)
        packet = self.read(); rows = [row for row in packet['source']['entities'] if row['id'] == owned['id']]
        if rows:
            need(rows[0]['lastEditedBy'] == packet['source']['localSessionId'] and rows[0]['hostType'] == 'domain' and not rows[0]['locked'])
            self.ui.select_entity(owned['id']); self.ui.delete_entity()
        self.wait(lambda source:not any(row['id'] == owned['id'] for row in source['entities']))
        owned['deleted'] = True; self.save()

    def act(self,query):
        arguments('feature.create.act',query); self.bound()
        need(query['runId'] == self.run and query['fixtureUrl'] == self.fixture_url and self.state is not None and self.state['phase'] == 'active')
        active = self.phase.read(); need(active['ticket'] == query['ticket'] and active['verb'] == query['verb'] and same(active['inputs'],query['inputs']))
        if any(call['query']['ticket'] == query['ticket'] for call in self.state['calls']):
            raise CreateInputPending('Create ticket already owns its original recipe; no replay is permitted')
        need(not self.state['calls'] or self.state['calls'][-1]['phase'] == 'acknowledged')
        before = self.read(); self.state['calls'].append(dict(query=deepcopy(query),phase='acting',before=before,after=None,auxInputs=[],creationBefore=None)); self.save()
        self.inputs.begin(query)
        verb, supplied = query['verb'], query['inputs']
        if verb == 'open':
            self.tablet(True); self.ui.open_create()
            original = editor(self.read()); need(original is not None)
            if self.state['editorBaseline'] is None: self.state['editorBaseline'] = original; self.save()
        else:
            self.tablet(True)
            if verb == 'import-picker-open':
                if self.files.state is None: self.files.reserve(query['ticket']); self.files.stage()
                need(self.files.state['phase'] == 'staged'); self.ui.open_import()
                picker = self.ui.picker_state('import'); self.state['picker'] = dict(role='import',rootId=picker['rootId'],ticket=query['ticket']); self.save()
            elif verb == 'import-picker-cancel':
                need(self.state['picker'] is not None); self.ui.cancel_import(self.state['picker']['rootId']); self.state['picker'] = None; self.save()
            elif verb == 'model-create':
                url = self.fixture_url+'tickets/'+query['ticket']+'/'+supplied['resource']
                self.create('model',lambda:self.ui.create_domain('model',resource=url),query['ticket'])
            elif verb == 'apply-texture':
                owned = self.active_owned('model'); need(owned is not None); self.ui.select_entity(owned['id'])
                self.ui.texture(owned['id'],self.fixture_url+'tickets/'+query['ticket']+'/'+supplied['resource'])
            elif verb == 'export-selection':
                owned = self.active_owned('model'); need(owned is not None and self.files.state is not None)
                self.ui.select_entity(owned['id']); self.ui.export(owned['id']); picker = self.ui.picker_state('export')
                self.state['picker'] = dict(role='export',rootId=picker['rootId'],ticket=query['ticket']); self.save()
                self.ui.accept_file('export',picker['rootId'],self.files.recover_stage(),self.run)
                self.state['picker'] = None; self.save()
            elif verb == 'import-picker-accept':
                picker = self.state['picker']; need(picker is not None and picker['role'] == 'import' and self.files.state['phase'] == 'staged')
                self.create('model',lambda:self.ui.accept_file('import',picker['rootId'],self.files.recover_stage(),self.run),query['ticket'])
                self.state['picker'] = None; self.save()
            elif verb == 'voxel-create': self.create('voxel',self.ui.create_polyvox,query['ticket'])
            elif verb == 'voxel-edit':
                need(supplied == dict(mode='remove',brushMeters=.5)); owned = self.active_owned('voxel'); need(owned is not None)
                self.ui.select_entity(owned['id']); self.ui.voxel_settings(mode=1,shape=2,remove=True,dynamics=0,pointer=0,diameter=.5,reach=.5)
                root = editor(self.read()); need(root is not None); self.tablet(False)
                world = self.world_factory(query['ticket']); need(isinstance(world,CreateWorldInput))
                world.tap(owned['id'],root['id'],active['afterEpochMs']); self.tablet(True)
            elif verb == 'delete-owned': self.delete()
            elif verb == 'set-rez-permission':
                self.rez.request('set',allowed=supplied['allowed'])
                self.wait(lambda source:(source['canRez'] or source['canRezTmp']) == supplied['allowed'])
            elif verb == 'create-denied':
                need(not before['source']['canRez'] and not before['source']['canRezTmp']); self.ui.create_domain('cube')
            elif verb == 'create-retry': self.create('cube',lambda:self.ui.create_domain('cube'),query['ticket'])
            elif verb == 'close': self.restore_editor(); self.ui.close(); self.tablet(False)
            else: need(False)
        after = self.read(); call = self.state['calls'][-1]; call['after'] = after
        self.inputs.finish(); call['phase'] = 'acknowledged'; self.save(); return {'performed':True}

    def restore_editor(self):
        original = self.state['editorBaseline']; need(original is not None)
        settings = original['voxelSettings']; maps = dict(createAppMode=['object','voxel'],voxelEditMode=['single','sphere','cube'],
            voxelEditDynamics=['click','continuous'],voxelPointerMode=['laser','brush'])
        self.ui.voxel_settings(mode=maps['createAppMode'].index(settings['createAppMode']),shape=maps['voxelEditMode'].index(settings['voxelEditMode']),
            remove=settings['voxelRemove'],dynamics=maps['voxelEditDynamics'].index(settings['voxelEditDynamics']),
            pointer=maps['voxelPointerMode'].index(settings['voxelPointerMode']),diameter=settings['voxelSphereSize'],reach=settings['voxelBrushLength'])
        self.ui.replace('create.property-search',''); self.ui.tab(original['page']['tab'])

    def cleanup(self,cleanup_ticket):
        """Normal cleanup inputs only; final paired original retirement is separate.

        Each stage is recorded before any call. Interrupted input is never
        repeated automatically. Recovery can continue only after independently
        proving the stage's actual postcondition.
        """
        identifier(cleanup_ticket); self.bound(); need(self.state is not None and self.state['phase'] in ('active','cleaning'))
        if self.state['cleanup'] is None:
            self.state['phase'] = 'cleaning'
            self.state['cleanup'] = dict(query=dict(runId=self.run,ticket=cleanup_ticket,fixtureUrl=self.fixture_url,verb='cleanup',inputs={}),
                phase='acting',before=None,after=None,auxInputs=[],creationBefore=None,steps=[])
            self.save()
        plan = self.state['cleanup']; need(plan['query']['ticket'] == cleanup_ticket)
        owned_calls = self.cleanup_inputs.state['calls']
        if not owned_calls:
            # The whole-plan reservation is durable before the input-journal
            # reservation. A crash in between owns no input and can safely
            # finish this reservation without delivering any command.
            self.cleanup_inputs.begin(plan['query'])
        else:
            need(len(owned_calls) == 1 and same(owned_calls[0]['arguments'],plan['query']))
        if plan['phase'] == 'acknowledged':
            fresh = self.read(); need(self.cleanup_restored(fresh)); return fresh
        # Retain the old action journal unchanged, including uncertain inputs.
        # New cleanup events consume strictly current normal input sequences.
        self.ui.io.owner = self.cleanup_inputs
        def step(name,perform,observed):
            existing = [row for row in plan['steps'] if row['name'] == name]
            if existing:
                row = existing[0]
                if row['after'] is not None: return
                actual = self.read()
                if not observed(actual): raise CreateInputPending('Uncertain Create cleanup stage requires its original outcome; input will not be repeated')
                row['after'] = actual; self.save(); return
            row = dict(name=name,after=None); plan['steps'].append(row); self.save()
            perform(); actual = self.read(); need(observed(actual)); row['after'] = actual; self.save()
        if self.rez.state is not None and self.rez.state['commands'] and self.rez.state['commands'][-1]['original'] is None:
            self.rez.recover()  # This has its own explicit read-only wire operation.
        # The only possible unadopted creation belongs to the retained last
        # create input. Admission still demands actual selection/new UUID/creator.
        if self.state['calls']:
            last = self.state['calls'][-1]
            if last['creationBefore'] is not None and self.active_owned() is None:
                packet = self.read(allow_new=True)
                added = set(semantic_map(packet))-set(semantic_map(self.state['baseline']['create']))-{row['id'] for row in self.state['owned']}
                if added:
                    original = adopt_created(last['creationBefore'],packet,[row['id'] for row in self.state['owned']],self.run)
                    role = 'voxel' if original['type'] == 'PolyVox' else 'model' if original['type'] == 'Model' else 'cube'
                    self.state['owned'].append(dict(id=original['id'],role=role,ticket=last['query']['ticket'],before=last['creationBefore'],after=packet,deleted=False)); self.save()
        def restore_rez():
            self.rez.request('restore')
            self.wait(lambda source:all(source[key]==self.state['baseline']['create']['source'][key] for key in ('canRez','canRezTmp')))
        step('rez',restore_rez,lambda value:
            all(value['source'][key] == self.state['baseline']['create']['source'][key] for key in ('canRez','canRezTmp')))
        # Any current actual file/detailed dialog must be the exact root born
        # during this run. Ordinary Cancel releases its original callback.
        def cancel_pickers():
            packet = self.read()
            if not any(not row['destroyed'] and row['kind'] != 'editor' for row in packet['source']['roots']): return
            self.tablet(True); packet = self.read(); baseline_ids = {row['id'] for row in self.state['baseline']['create']['source']['roots']}
            for root in packet['source']['roots']:
                if root['destroyed'] or root['kind'] == 'editor': continue
                need(root['id'] not in baseline_ids)
                if not root['active'] or root.get('picker',{}).get('closing'):
                    self.wait(lambda source:any(row['id']==root['id'] and row['destroyed'] for row in source['roots'])); continue
                if root['kind'] in ('import','export'):
                    need(self.ui.picker_state(root['kind'])['rootId'] == root['id']); self.ui.input('create.'+root['kind']+'.cancel')
                else:
                    need(root['kind'] == 'polyvox'); self.ui.input('create.polyvox.cancel')
            self.state['picker'] = None; self.save()
        step('pickers',cancel_pickers,lambda value:not any(not row['destroyed'] and row['kind'] != 'editor' for row in value['source']['roots']))
        step('entities',lambda:self.delete() if self.active_owned() is not None else None,
             lambda value:not set(row['id'] for row in self.state['owned']) & set(row['id'] for row in value['source']['entities']))
        def restore():
            original = editor(self.read())
            if original is None: self.tablet(False); return
            if self.state['editorBaseline'] is None:
                need(not original['numericFocus'] and not original['changed'] and not original['page']['selectedIds'])
                self.state['editorBaseline']=original; self.save()
            self.tablet(True)
            current = self.ui.capture()
            if self.ui.row(current,'create.page',enabled=False) is None: self.ui.open_create()
            self.restore_editor(); self.ui.close(); self.tablet(False)
        step('editor',restore,lambda value:not value['source']['tabletShown'] and selected(value['source']) == []
             and all(row['destroyed'] or row['kind'] != 'editor' or not row['numericFocus'] and not row['changed']
                     for row in value['source']['roots']))
        self.normal.release_actions()
        if self.cleanup_inputs.state['calls'][-1]['phase'] == 'acting': self.cleanup_inputs.finish()
        plan['after'] = self.read(); need(self.cleanup_restored(plan['after']))
        plan['phase'] = 'acknowledged'; self.save()
        # File release, retained image/GPU lease removal and both independent
        # actor quiet windows are still owned by CreateObservation/Feature.
        return deepcopy(plan['after'])

    def cleanup_restored(self, packet):
        """Current app restoration only; no callback/GPU/file drain claim."""
        source = create_state.live(packet); baseline = self.state['baseline']['create']['source']
        need(not source['tabletShown'] and selected(source) == []
             and all(source[key] == baseline[key] for key in ('canRez','canRezTmp'))
             and not {row['id'] for row in self.state['owned']} & {row['id'] for row in source['entities']}
             and not any(not row['destroyed'] and row['kind'] != 'editor' for row in source['roots']))
        current = editor(packet); original = self.state['editorBaseline']
        if current is not None:
            need(original is not None and not current['active']
                 and not current['numericFocus'] and not current['changed']
                 and same(current['voxelSettings'],original['voxelSettings'])
                 and current['page']['tab'] == original['page']['tab'])
        return True
