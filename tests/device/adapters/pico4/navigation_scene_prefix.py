"""One pre-setup lease and scene ledger around the original Navigation parent.

The normal Go To A belongs to PrimaryPrepare. Its pre-input user origin never
becomes the later A baseline. This owner adds no recipe, image policy, camera
input, restart, or replacement Parent. Failed warm owners are not adoptable.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import time
from urllib.parse import urlsplit

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_navigation_environment import NativeNavigationEnvironment,logged_out
from adapters.navigation_arrival import NavigationArrival,pose_packet
from adapters.navigation_stereo import NavigationStereo
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import state as original_state,raw_file
from adapters.owned_world_render import OwnedWorldRenderCapture
from adapters.pico4.audio_raw_archive import AudioRawArchive,AudioRawSourceLock
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.navigation_originals import read_original,signature
from adapters.pico4.navigation_prefix import NavigationPrefix
from adapters.pico4.navigation_scene_metadata import NavigationMetadataSeal
from adapters.pico4.navigation_scene_store import NavigationSceneRootState
from adapters.pico4.normal_login import PicoLoginIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.history import canonical,same,unpack,MAX_FRAMES,MAX_RAW
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_login_ui import TokenLoginUI
from feature_journeys.navigation_fixture import validate_status
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader
from navigation_observation import viewpoint_urls,owned_scene
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope

VERSION=2
ROLE_NAMES=('primary','actor')


class NavigationSceneIO(NativeNavigationIO):
    """Seal ordinary callbacks once with the original enclosing clock.

    Construction precedes the normal Parent's bind APIs. A sealed callback is
    never replaced, cleared or adopted. The same callbacks run completely,
    including their final source/phase/Session fences and durable intent.
    """
    def __init__(self,adapter,target,process_identity,controller,owner):
        need(isinstance(owner,NavigationScenePrefix));self.scene_owner=owner
        self.scene_qml=self.scene_controller=None
        super().__init__(adapter,target,process_identity,controller)

    def wrapped(self,callback):
        owner=self.scene_owner
        def dispatch(*args,**kwargs):
            need(self.scene_owner is owner);owner.publish_bound()
            result=callback(*args,**kwargs)
            # Host-only, after ALL original preparation and immediately before
            # the actual Native writer / Session stage or publish continues.
            owner.publish_bound();return result
        return dispatch

    def guard(self):
        self.scene_owner.bound();result=super().guard();self.scene_owner.bound();return result

    def bind_input(self):
        self.scene_owner.bound();result=super().bind_input();self.scene_owner.bound();return result

    def bind_before_send(self,callback):
        need(callable(callback))
        if self.scene_qml is None:self.scene_qml=(callback,self.wrapped(callback))
        need(callback is self.scene_qml[0]);super().bind_before_send(self.scene_qml[1])

    def bind_controller_admission(self,callback,*,intent,before_publish=None):
        need(all(callable(value) for value in (callback,intent,before_publish)))
        originals=(callback,intent,before_publish)
        if self.scene_controller is None:self.scene_controller=(originals,tuple(self.wrapped(value) for value in originals))
        need(all(a is b for a,b in zip(originals,self.scene_controller[0])))
        admission,stage,publish=self.scene_controller[1]
        super().bind_controller_admission(admission,intent=stage,before_publish=publish)


class NavigationScenePrefix:
    """Warm gap journal; all feature actions remain in the original parent.

    Factories resolve fresh, distinct original readers. ``stereo`` returns an
    existing NavigationStereo, using the already enumerated role render store.
    Its caller supplies no expected location, pixel verdict, or marker policy.
    """
    def __init__(self,path,normal,environment,arrival,home,phase,session,lock,
                 binding,inputs,provider_instance,status,parent_factory,stereo,
                 *,monotonic=time.monotonic,probe_factory=None):
        context(binding)
        need(type(normal) is PicoNavigation and type(normal.io) is NativeNavigationIO
            and isinstance(environment,NativeNavigationEnvironment) and isinstance(arrival,NavigationArrival)
            and isinstance(home,PicoTabletHome) and isinstance(phase,PhaseFixtureReader)
            and isinstance(session,PicoOpenXrAdapterSession) and type(lock) is ScriptSourceLock
            and all(callable(f) for f in (status,parent_factory,stereo,monotonic))
            and (probe_factory is None or callable(probe_factory)))
        self.store=PrivateFeatureState(path);self.path=self.store.path;self.root=self.path.parent
        need(self.path.name=='navigation-scene-owner.json' and lock.path.parent==self.root
            and normal.path.parent==self.root and normal.state is None
            and normal.io._before_send is normal.io._before_controller is None
            and phase.area=='world-navigation' and phase.run==arrival.run
            and same(arrival.binding,binding) and arrival.scene_url==inputs['sceneUrl']
            and normal.io.identity==binding['processIdentity']
            and normal.process_id==environment.pid==home.source.pid==int(binding['processIdentity'].split(':',1)[0])
            and normal.context['sourceRevision']==binding['sourceRevision']
            and normal.context['artifactSha256']==binding['artifactSha256']
            and normal.context['sceneSha256']==hashlib.sha256(inputs['sceneUrl'].encode()).hexdigest())
        self.run=arrival.run;self.binding=deepcopy(binding);self.inputs=deepcopy(inputs)
        self.normal,self.environment,self.arrival,self.home,self.phase,self.session,self.lock=normal,environment,arrival,home,phase,session,lock
        self.status,self.parent_factory,self.stereo_factory,self.monotonic=status,parent_factory,stereo,monotonic
        self.probe_factory=self.original_probe_factory=probe_factory
        self.probe_bindings=self.original_probe_bindings=()
        self.original_dependencies=(normal,environment,arrival,home,phase,session,lock,status,parent_factory,stereo,monotonic)
        self.provider_instance=provider_instance;self.host=host_identity();self.started=self.previous=monotonic();self.archive_previous=self.started
        need(number(self.started,0,1e15));self.deadline=self.started+120
        self.scope=dict(navigationScenePrefixVersion=VERSION,runId=self.run,binding=self.binding,inputs=self.inputs,
            providerInstance=provider_instance,fixtureUrl=phase.fixture_url,path=str(self.path),sourceLock=str(lock.path),
            normalPath=str(normal.path),hostProcessIdentity=self.host,startedMonotonic=self.started,deadlineMonotonic=self.deadline)
        if probe_factory is not None:self.scope['probeOriginalsVersion']=1
        self.scope_sha=json_digest(self.scope);self.disk=self.state=self.physical=None
        self.metadata_seals=self.original_metadata_seals=()
        self.seal_metadata('scope',self.scope)
        self.root_raw=self.root_seal=self.original_root_seal=None
        self.outer_guard=self.original_outer_guard=self.publish_bound
        # The original strict canonical admission remains BEFORE opening the
        # directory. Its held original supplies every subsequent _parent proof.
        self.store._parent()
        self.directory=OriginalDescriptor(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.store=self.original_store=NavigationSceneRootState(self.path,self.directory)
        self.root_parent_guard=self.store._parent
        self.archive_directory=self.directory;self.archive_root=self.root;self.archive_host=self.host
        self.archive_monotonic=self.monotonic
        self.parents={};self.parent_pins={};self.observers={};self.original_guards={};self.anchor=self.controller_kind=None;self.setup_io=None
        self.capture_fences=[];self.read_fences=[];self.fixed_originals={}
        self.raw_references=[];self.environment_pending=None;self.environment_request=None;self.status_pending=None
        self.journal=ChatSourceChunks(self.store,self.scope)
        with lock.held():
            self.identity();need(self.store.read() is None
                and not any(p.name.startswith(('navigation-scene-owner.json.','navigation-scene-raw.json')) for p in self.root.iterdir()))
            self.save(dict(navigationSceneOwnerVersion=VERSION,scope=deepcopy(self.scope),phase='admission',chunks=[],pending=None,lease=None,fixture=None,commands=[],controllers=[],
                home=None,entry=None,parent=None,bridge=None,scenes=[],restoration=None))
        # The literal container is shared format, with Navigation-only scope.
        # It contributes to this SAME aggregate bill; side_bytes is always 0.
        self.raw=AudioRawArchive(self.root/'navigation-scene-raw.json',self.scope,AudioRawSourceLock(lock),
            self.archive_identity,self.other_bill,self.archive_clock)
        self.bind_originals()
        if self.probe_factory is not None:
            self.bind_probe(self.arrival,self.normal.io.adapter,self.normal.io.target,self.guard,'primary')

    def now(self):
        value=self.monotonic();need(number(value,self.previous,self.deadline));self.previous=value;return value

    def archive_clock(self):
        # An already issued original must still be durably retained when its
        # return arrives after the input/query deadline. This host-only clock
        # records that late return; every NEW send/getter still uses bound().
        value=self.archive_monotonic();need(number(value,self.archive_previous,1e15))
        self.archive_previous=value;return value

    def archive_identity(self):
        # A returned literal's already issued reservation belongs to its own
        # original raw root, directory/OFD and host. Loss of business Parent
        # authority must not turn a valid reserved return into discarded bytes.
        need(host_identity()==self.archive_host and self.archive_monotonic is self.original_dependencies[-1])
        require_directory(self.archive_directory,self.archive_root)

    def identity(self):
        self.archive_identity()
        need(host_identity()==self.host and self.path==self.store.path and self.root==self.path.parent
            and self.store is self.original_store and type(self.store) is NavigationSceneRootState
            and self.store._parent is self.root_parent_guard
            and self.outer_guard is self.original_outer_guard
            and self.probe_factory is self.original_probe_factory
            and self.probe_bindings is self.original_probe_bindings and type(self.probe_bindings) is tuple
            and (self.normal,self.environment,self.arrival,self.home,self.phase,self.session,self.lock,self.status,
                 self.parent_factory,self.stereo_factory,self.monotonic)==self.original_dependencies)
        self.require_metadata('scope',self.scope,self.scope_sha)
        require_directory(self.directory,self.root)
        need(all(target.guard is wrapped for target,_original,wrapped in self.capture_fences))
        need(all(getattr(target,name) is wrapped for target,name,_original,wrapped in self.read_fences))
        for arrival,reader,callback,guard,adapter,target,role in self.probe_bindings:
            need(arrival.probe is callback and reader.archive is self.raw and reader.guard is guard
                and reader.monotonic is self.monotonic and reader.adapter is adapter and reader.target==target
                and reader.role==role and not reader.failed)
        for parent,transport,adapter,target,identity,scope_sha in self.parent_pins.values():
            need(parent.transport is transport and transport.scene_owner is self and transport.adapter is adapter
                and transport.target==target and transport.identity==identity and parent.outer_guard is self.outer_guard
                and parent.original_outer_guard is self.outer_guard)
            self.require_metadata('parent:'+parent.role,parent.scope(),scope_sha)
        for name,(reader,reference,digest) in self.fixed_originals.items():
            self.require_metadata('original:'+name,reference,digest)
            need(str(reader.path)==reference['path'] and reader.stamp==reference['signature'])
        if self.disk is not None:
            seal=self.root_seal
            need(seal is self.original_root_seal and type(seal) is tuple and len(seal)==3
                and self.disk is self.state is seal[0] and self.root_raw is seal[1]
                and type(self.root_raw) is bytes and type(self.physical) is list
                and tuple(self.physical)==seal[2] and canonical(self.state)+b'\n'==self.root_raw)
            # Reuse only the exact JSON interpretation admitted by the original
            # successful CAS readback. Every access still opens the actual
            # current original OFD pair, rereads ALL bytes and its full stamp,
            # and checks the private canonical root before and after the read.
            raw,pin=raw_file(self.store)
            need(raw==self.root_raw and pin==self.physical)
        else:need(self.root_seal is self.original_root_seal is self.root_raw is None)

    def seal_metadata(self,name,value):
        need(self.metadata_seals is self.original_metadata_seals
            and not any(key==name for key,_seal in self.metadata_seals))
        seal=NavigationMetadataSeal(value)
        self.metadata_seals=self.original_metadata_seals=self.metadata_seals+((name,seal),)

    def require_metadata(self,name,value,expected):
        need(self.metadata_seals is self.original_metadata_seals and type(self.metadata_seals) is tuple)
        matches=[seal for key,seal in self.metadata_seals if key==name]
        need(len(matches)==1 and type(matches[0]) is NavigationMetadataSeal)
        matches[0].require(value,expected)

    def bound(self):
        self.identity();self.now()
        for reader,reference,_digest in self.fixed_originals.values():
            raw,pin=reader.read();need(pin==reference['signature'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])

    def publish_bound(self):
        self.bound()
        if hasattr(self,'raw'):self.raw.verify()
        self.bound()

    def pin(self,name,path):
        need(name not in self.fixed_originals)
        reader=ClosedOriginalFile(path,0o600,self.identity);raw,physical=reader.read();reference=read_original(path)
        need(reference['present'] and reference['signature']==physical and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        self.seal_metadata('original:'+name,reference)
        self.fixed_originals[name]=(reader,reference,json_digest(reference));return deepcopy(reference)

    def save(self,value):
        self.lock.assert_held();self.bound()
        exact(value,{'navigationSceneOwnerVersion','scope','phase','chunks','pending','lease','fixture','commands','controllers',
            'home','entry','parent','bridge','scenes','restoration'})
        need(type(value['navigationSceneOwnerVersion']) is int and value['navigationSceneOwnerVersion']==VERSION
            and same(value['scope'],self.scope) and value['phase'] in
            ('admission','lease-reading','goto','arrival','home','entry','parent','closing','ready','opening','acting',
             'generation','restoring','directory-restored','retiring','retired','uncertain'))
        need(len(canonical(value))+1<=65536)
        self.store.write(value,self.disk)
        self.seal_root(value)

    def seal_root(self,value):
        """Only the just-written original CAS can establish a new root seal."""
        actual,raw,pin=original_state(self.store);need(same(actual,value))
        self.disk=self.state=deepcopy(value);self.physical=pin;self.root_raw=raw
        self.root_seal=self.original_root_seal=(self.state,raw,tuple(pin))

    def change(self,**updates):
        value=deepcopy(self.state);value.update(updates);self.save(value)

    def other_bill(self):
        """Fresh complete family inventory, physical bytes and decoded packs.

        No cached namespace verdict. Raw's own bounded parts/index are billed
        by its original owner exactly once. Everything else in this root,
        including both role images, Parent copies and original fragments, is
        charged here. A foreign symlink/nonregular node refuses admission.
        """
        self.identity();paths=[];stack=[self.root];stored=decoded=parts=0
        while stack:
            directory=stack.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    path=Path(entry.path);info=entry.stat(follow_symlinks=False)
                    need(len(paths)+len(stack)<4096 and not stat.S_ISLNK(info.st_mode))
                    if stat.S_ISDIR(info.st_mode):
                        need(info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700);stack.append(path);continue
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid())
                    paths.append((path,signature(info)))
                    if path.parent==self.root and (path.name=='navigation-scene-raw.json' or path.name.startswith('navigation-scene-raw.json.')):continue
                    stored+=info.st_size;parts+=int('.frame-' in path.name or '.part-' in path.name or path.suffix=='.png')
                    if path.suffix=='.json' and info.st_size<=65536:
                        raw=path.read_bytes();need(signature(path.lstat())==signature(info) and len(raw)==info.st_size)
                        value=json.loads(raw)
                        pending=[value]
                        while pending:
                            item=pending.pop()
                            if type(item) is dict:
                                if item.get('encoding')=='zlib-base64-json':
                                    unpack(item);decoded+=item['bytes']
                                else:pending.extend(item.values())
                            elif type(item) is list:pending.extend(item)
        need(all(signature(path.lstat())==pin for path,pin in paths))
        return dict(parts=parts,storedBytes=stored,decodedBytes=stored+decoded)

    def bill(self):
        other=self.other_bill();raw=self.raw.bill()
        result={key:other[key]+raw[key] for key in ('parts','storedBytes','decodedBytes')}
        need(result['parts']<=MAX_FRAMES and result['storedBytes']<=MAX_RAW and result['decodedBytes']<=MAX_RAW)
        return result

    def bind_originals(self):
        io=self.normal.io;old_read=io._read;old_send=self.environment.send;old_original=self.environment.original;old_controller=io.controller
        need(not hasattr(io,'_navigation_scene_owner') and not hasattr(self.environment,'_navigation_scene_owner'))
        io._navigation_scene_owner=self;self.environment._navigation_scene_owner=self
        def read(kind):
            self.bound();token=self.status_pending if kind=='status' else None
            if kind=='status':self.status_pending=None
            if token is None:token=self.raw.reserve('primary',dict(source='navigation-ui',kind=kind),262144,side_bytes=0)
            self.bound();raw=old_read(kind)
            ref=self.raw.retain(token,raw);self.raw_references.append(ref)
            self.bound();return raw
        def send(request):
            self.bound();need(self.environment_pending is None)
            token=self.raw.reserve('primary',dict(source='navigation-environment',request=deepcopy(request)),262144,side_bytes=0)
            self.environment_pending=token;self.environment_request=deepcopy(request);self.bound();return old_send(request)
        def original():
            self.bound();need(self.environment_request is not None)
            token=self.environment_pending
            if token is None:token=self.raw.reserve('primary',dict(source='navigation-environment',request=self.environment_request),262144,side_bytes=0)
            self.environment_pending=None;self.bound();raw=old_original()
            ref=self.raw.retain(token,raw);self.raw_references.append(ref)
            self.bound();return raw
        def controller(operation):
            # Keep the complete original Session route; require actual neutral
            # consumption before the NEXT ordinary Qt snapshot/input starts.
            result=old_controller(operation);self.neutral();return result
        io._read=read;self.environment.send=send;self.environment.original=original
        io.controller=controller;self.raw_bindings=(read,send,original,controller)
        self.qml_callback=self.before_send;self.controller_callback=self.before_controller
        self.intent_callback=self.controller_intent;self.publish_callback=self.before_publish
        io.bind_before_send(self.qml_callback)
        io.bind_controller_admission(self.controller_callback,intent=self.intent_callback,before_publish=self.publish_callback)
        self.read_fence(self.home.source,'guard')

    def read_fence(self,target,name):
        original=getattr(target,name);need(callable(original))
        def guarded(*args,**kwargs):
            self.bound();result=original(*args,**kwargs);self.bound();return result
        setattr(target,name,guarded);self.read_fences.append((target,name,original,guarded))

    def bind_probe(self,arrival,adapter,target,guard,role):
        from adapters.pico4.probe_originals import PicoProbeOriginals
        self.bound();need(self.probe_factory is not None and isinstance(arrival,NavigationArrival)
            and arrival.last is None and not arrival.requests and role in ROLE_NAMES
            and not any(value[0] is arrival for value in self.probe_bindings))
        reader=self.probe_factory(self,adapter,target,guard,role)
        need(type(reader) is PicoProbeOriginals and reader.archive is self.raw and reader.guard is guard
            and reader.monotonic is self.monotonic and reader.adapter is adapter and reader.target==target
            and reader.role==role and not reader.active and not reader.failed and not reader.receipts)
        def probe(after):
            self.bound();before=len(reader.receipts);result=reader.read(after)
            self.raw_references.extend(json.loads(reference) for reference in reader.receipts[before:])
            self.bound();return result
        arrival.probe=probe
        self.probe_bindings=self.original_probe_bindings=self.probe_bindings+((arrival,reader,probe,guard,adapter,target,role),)
        return reader

    def guard(self):
        self.bound();io=self.normal.io
        need(io._navigation_scene_owner is self and self.environment._navigation_scene_owner is self
            and (io._read,self.environment.send,self.environment.original,io.controller)==self.raw_bindings
            and io._before_send is self.qml_callback and io._before_controller is self.controller_callback
            and io._controller_intent is self.intent_callback and io._controller_publish is self.publish_callback)
        io.guard();current=self.phase.read();self.bound()
        need(current['inputs']=={} and current['status']['active'])
        if self.state['phase']=='opening':
            call=self.state['pending'];parent=self.parents['primary'];parent.load()
            need(current['verb']=='open' and current['ticket']==call['ticket'] and not parent.state['completed']
                and parent.state['phase']=='ready' and same(current['status']['activations'][:-1],parent.state['fixture']['activations']))
        else:
            need(current['verb']=='baseline'
                and (self.state['fixture'] is None or same(current['status']['activations'],self.state['fixture']['activations'])))
        fresh(current['status']['capturedEpochMs'],self.environment.clock_ms());return current

    def append(self,value):
        self.bound();self.journal.verify();self.change(pending=deepcopy(value),phase='lease-reading' if self.state['lease'] is None else self.state['phase'])
        original_phase=self.state['phase']
        # ChatSourceChunks requires its genuine pending-root phase. The public
        # gap phase remains inside pending until its exact child is committed.
        root=deepcopy(self.state);root['phase']='reading'
        self.store.write(root,self.disk);self.seal_root(root)
        chunks=self.journal.append(value,self.state['chunks'])
        root=deepcopy(self.state);root.update(phase=original_phase,chunks=chunks,pending=None);self.save(root)
        self.bill();return len(chunks)-1

    def lease(self):
        self.journal.verify();need(type(self.state['lease']) is int)
        if 'lease' in self.fixed_originals:self.fixed_originals['lease'][0].read()
        return self.journal.load(self.state['chunks'])[self.state['lease']]

    def original_lease(self):
        current=self.guard();self.change(phase='lease-reading',fixture=deepcopy(current['status']))
        provider=self.status();validate_status(provider,instance=self.provider_instance,run=self.run,inputs=self.inputs)
        need(provider['navigationProviderVersion']==2 and provider['active'] and provider['ticket']==current['ticket'])
        environment=self.environment.read(self.run);logged_out(environment)
        ui=self.normal.snapshot();pose=self.arrival.read()
        need(environment['navigationEnvironmentVersion']==2 and environment['selectedSettingPresent']
            and environment['settings']['selectedType']=='string' and not environment['environmentOverride']
            and environment['selectedServer']==environment['effectiveServer']
            and environment['ui']['bridgeId']==ui['bridgeId']==self.binding['sessionId']
            and not ui['open'] and not ui['ready'] and not environment['ui']['open']
            and not environment['ui']['loginPageAlive'])
        original_url=pose['subject']['source']['sceneUrl'];parsed=owned_scene(original_url,viewpoint_required=True)
        original_scene=parsed._replace(query='',fragment='').geturl()
        label=pose_packet(pose,self.run,self.binding,original_scene,self.environment.clock_ms())
        need(label in viewpoint_urls(original_scene) and original_url==viewpoint_urls(original_scene)[label])
        with self.session._lock():session=deepcopy(self.session._load())
        need(session is not None and session['processIdentity']==self.binding['processIdentity'])
        value=dict(navigationSceneOriginalLeaseVersion=VERSION,scopeSha256=self.scope_sha,scope=deepcopy(self.scope),environment=environment,ui=ui,pose=pose,
            originalUrl=original_url,originalSceneUrl=original_scene,session=session,fixture=deepcopy(current),provider=provider,
            raw=deepcopy(self.raw_references),hostMonotonic=self.now())
        index=self.append(value);self.pin('lease',self.journal.store(index).path);self.change(lease=index,phase='goto')

    def unchanged_settings(self,environment):
        old=self.lease()['environment'];logged_out(environment)
        need(environment['navigationEnvironmentVersion']==2 and environment['selectedSettingPresent']
            and environment['settings']['selectedType']==old['settings']['selectedType']=='string'
            and environment['settings']['rawSettingsSha256']==old['settings']['rawSettingsSha256']
            and environment['otherSettingsSha256']==old['otherSettingsSha256']
            and environment['selectedServer']==environment['effectiveServer']==old['selectedServer'])

    def before_send(self,command):
        self.lock.assert_held();self.guard();phase=self.state['phase']
        need(phase in ('goto','entry') and not any(row['commandId']==command['commandId'] for row in self.state['commands']))
        if phase=='goto':
            need(command['controlId'] in ('navigation.goto','navigation.address') or command['controlId'].startswith('tablet.page.'))
            if command['action']=='replace':need(command['controlId']=='navigation.address' and command['text']==viewpoint_urls(self.inputs['sceneUrl'])['A'])
        else:
            pending=self.state['entry'];need(pending is not None and command['controlId']=='login.entry' and command['action']=='activate'
                and command['controlToken']==pending['token'] and command['sequence']==pending['scope']['sequence']+1
                and command['bridgeId']==pending['scope']['instance'] and command['generation']==pending['scope']['generation'])
        self.change(commands=[*self.state['commands'],deepcopy(command)])
        need(self.status_pending is None)
        self.status_pending=self.raw.reserve('primary',dict(source='navigation-ui',kind='status',command=deepcopy(command)),262144,side_bytes=0)
        self.guard()

    def before_controller(self,operation):
        self.lock.assert_held();current=self.guard()
        need((self.state['phase'],operation) in (('goto','tablet.open'),('closing','tablet.close'),('opening','tablet.open')))
        need(not any(row['kind']==operation and row['phase']==self.state['phase'] for row in self.state['controllers']))
        self.controller_kind=operation;self.anchor=dict(hostMonotonic=self.now(),nativeEpochMs=self.environment.clock_ms(),fixtureEpochMs=current['status']['capturedEpochMs'])

    def input_age(self):
        self.lock.assert_held();self.bound();need(self.anchor is not None)
        now=self.now();a=self.anchor
        need(max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def controller_intent(self,envelope):
        self.input_age();validate_envelope(envelope,self.session.profile)
        need(len(envelope['commands'])==1 and envelope['commands'][0]['operation']==self.controller_kind
            and envelope['sessionNonce']==self.lease()['session']['sessionNonce'])
        self.change(controllers=[*self.state['controllers'],dict(kind=self.controller_kind,phase=self.state['phase'],envelope=deepcopy(envelope),anchor=deepcopy(self.anchor))])
        self.before_publish(envelope)

    def before_publish(self,envelope):
        self.publish_bound();self.input_age();need(self.state['controllers'] and same(self.state['controllers'][-1]['envelope'],envelope)
            and same(self.state['controllers'][-1]['anchor'],self.anchor))
        self.input_age()

    def home_intent(self,stage,before,control):
        self.guard();need(self.state['phase']=='home' and self.state['home'] is None and stage=='tablet-home-ray' and control=='tablet.home-ray')
        self.change(home=deepcopy(before));self.controller_kind='input.primary'
        current=self.guard();self.anchor=dict(hostMonotonic=self.now(),nativeEpochMs=self.environment.clock_ms(),fixtureEpochMs=current['status']['capturedEpochMs'])

    def login_intent(self,stage,before,control):
        self.guard();need(self.state['phase']=='entry' and self.state['entry'] is None and stage=='login-activate' and control=='login.entry')
        rows=[row for row in before['controls'] if row['id']==control];need(len(rows)==1)
        self.change(entry=dict(token=rows[0]['token'],scope=dict(instance=before['bridgeId'],generation=before['generation'],sequence=before['lastCommandSequence'])))

    def neutral(self,*,parent=False):
        from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
        for attempt in range(81):
            self.guard();index=len(self.state['controllers'])-1
            row=self.state['parent']['home'] if parent else self.state['controllers'][index]
            status=self.session.observe_owned_status(self.binding['processIdentity'],row['envelope'])
            value=deepcopy(self.state)
            target=value['parent']['homeStatuses'] if parent else value['controllers'][index].setdefault('statuses',[])
            target.append(dict(status=deepcopy(status),hostMonotonic=self.now()))
            self.save(value);self.guard()
            if NavigationBookmarkJoin.neutral(status,row['envelope']):return
            need(type(status) is dict and status.get('enabled') is True and status.get('state') in ('accepted','active')
                and type(status.get('acceptedSequence')) is int and status['acceptedSequence']==row['envelope']['sequence']
                and status.get('acceptedNonce')=='[redacted]' and status.get('activeCommandId')==row['envelope']['commands'][0]['id'] and attempt<80)
            self.normal.sleep(.1)
        need(False)

    def prepare(self):
        need(self.lock._owner is None)
        with self.lock.held():
            self.guard();need(self.state['phase']=='admission')  # no cold/warm replay of uncertain input
            self.original_lease();self.normal.invoke('places.goto',dict(url=viewpoint_urls(self.inputs['sceneUrl'])['A']))
            self.change(phase='arrival');started=self.now()
            for attempt in range(81):
                self.guard();pose=self.arrival.read();environment=self.environment.read(self.run);self.unchanged_settings(environment)
                prior=self.lease()['provider'];provider=self.status()
                validate_status(provider,instance=self.provider_instance,run=self.run,inputs=self.inputs,previous=prior)
                self.append(dict(kind='setup-arrival',pose=pose,environment=environment,provider=provider,raw=deepcopy(self.raw_references)))
                rows=[row for row in provider['responses'][len(prior['responses']):]
                    if row['ticket']==self.state['fixture']['activations'][-1]['ticket'] and row['kind']=='stereo-scene' and row['status']==200]
                if pose_packet(pose,self.run,self.binding,self.inputs['sceneUrl'],self.environment.clock_ms())=='A' and rows:break
                need(attempt<80 and self.now()-started<8);self.normal.sleep(.1)
            self.change(phase='home')
            self.home.ensure(self.home_intent,stream_intent=self.intent_callback,stream_publish=self.publish_callback)
            self.neutral()
            self.change(phase='entry');self.setup_io=PicoScriptIO(self.normal)
            parsed=urlsplit(self.lease()['environment']['selectedServer']);origin=parsed.scheme+'://'+parsed.netloc
            login=TokenLoginUI(PicoLoginIO(self.setup_io),self.login_intent,self.run,origin,
                monotonic=self.monotonic,sleep=self.normal.sleep)
            login._input('login.entry','activate')
            # Entry uses the ordinary token route. Its original directory may
            # legitimately include /server; Origin's existing validator owns
            # that exact endpoint instead of TokenLoginUI's origin-only policy.
            entered=self.normal.wait(lambda value:self.normal.control(value,'login.page') is not None)
            need(entered['bridgeId']==self.binding['sessionId'] and entered['lastCommandSequence']==self.state['entry']['scope']['sequence']+1)
            self.change(phase='parent');parent=self.parent_factory('primary',self)
            need(isinstance(parent,NavigationPrefix) and parent.role=='primary' and parent.lock is self.lock and parent.run==self.run
                and same(parent.binding,self.binding) and parent.transport is not self.normal.io and parent.state is None)
            self.attach(parent);self.parents['primary']=parent
            parent.prepare();self.unchanged_settings(parent.origin.state['original'])
            self.change(parent=dict(scope=parent.scope(),originalLease=self.state['lease'],origin=self.pin('origin',parent.origin.store.path),
                originPacket=self.pin('origin-packet',parent.origin.packet_store(parent.origin.disk_state['original']['sha256']).path),
                home=deepcopy(parent.state['home']),homeStatuses=[]))
            self.neutral(parent=True);self.change(phase='closing')
            # Same normal OpenXR Close route, owned by this preparation ledger.
            self.normal.io.controller('tablet.close');hidden=self.normal.wait(lambda value:not value['open'])
            self.append(dict(kind='setup-close',ui=hidden,parent=deepcopy(self.state['parent']),controllers=deepcopy(self.state['controllers'])))
            self.change(phase='ready');self.bound()
        self.bound();return dict(navigationScenePrefixVersion=VERSION,phase='ready',originalLease=self.state['lease'],fullNavigationRecipe=False)

    def attach(self,parent):
        need(isinstance(parent,NavigationPrefix) and parent.lock is self.lock and parent.run==self.run and same(parent.binding,self.binding))
        need(type(parent.transport) is NavigationSceneIO and parent.transport.scene_owner is self)
        need(parent.outer_guard is self.outer_guard and parent.original_outer_guard is self.outer_guard)
        need(parent.role not in self.parent_pins)
        transport=parent.transport
        self.seal_metadata('parent:'+parent.role,parent.scope())
        self.parent_pins[parent.role]=(parent,transport,transport.adapter,transport.target,transport.identity,json_digest(parent.scope()))
        original=parent.source.guard
        need(parent.role not in self.original_guards and all(parent.source is not owner.source for owner in self.parents.values()))
        def guarded():self.bound();result=original();self.bound();return result
        parent.source.guard=guarded;self.original_guards[parent.role]=(parent.source,original,guarded)
        for reader in (*parent.source.readers.values(),parent.source.arrival,parent.source.arrival.subject):
            self.read_fence(reader,'guard')
        if self.probe_factory is None:self.read_fence(parent.source.arrival,'probe')
        else:self.bind_probe(parent.source.arrival,transport.adapter,transport.target,parent.source.guard,parent.role)
        self.read_fence(parent.source,'status')

    def parent(self,role):
        need(role in ROLE_NAMES);self.bound()
        if role not in self.parents:
            need(role=='actor' and self.state['parent'] is not None)
            parent=self.parent_factory(role,self);need(parent.role==role and same(parent.scope(),self.parents['primary'].scope()))
            self.attach(parent);self.parents[role]=parent
        source,original,guarded=self.original_guards[role];need(self.parents[role].source is source and source.guard is guarded)
        return self.parents[role]

    def observe(self,role):
        self.bound();need(self.state['phase']=='ready');result=self.parent(role).observe();self.bound();return result

    def act(self,call):
        self.bound();need(self.state['phase']=='ready');parent=self.parent('primary')
        call=arguments('feature.world-navigation.act',call)
        need(call['runId']==self.run and call['fixtureUrl']==self.phase.fixture_url)
        with self.lock.held():
            parent.load()
            if not parent.state['completed']:
                need(call['verb']=='open' and call['inputs']=={})
                self.change(phase='opening',pending=deepcopy(call));self.guard()
                self.normal.io.controller('tablet.open');shown=self.normal.wait(lambda value:value['open'] and value['ready'])
                bridge=self.append(dict(kind='journey-open',ticket=call['ticket'],ui=shown,controller=deepcopy(self.state['controllers'][-1]),
                    controllers=deepcopy(self.state['controllers']),parentHome=deepcopy(parent.state['home']),parentOrigin=deepcopy(self.state['parent']['origin']),
                    parent=deepcopy(self.state['parent']),originalLease=self.state['lease'],scopeSha256=self.scope_sha))
                self.pin('bridge',self.journal.store(bridge).path)
                self.change(bridge=bridge)
            self.change(phase='acting',pending=deepcopy(call))
        result=parent.act(call)
        with self.lock.held():self.bound();self.change(phase='ready',pending=None)
        self.bound();return result

    def directory_bridge(self,parent):
        from adapters.pico4.navigation_scene_bridge import read_bridge
        self.bound();need(isinstance(parent,NavigationPrefix) and same(parent.scope(),self.parents['primary'].scope())
            and self.state['bridge'] is not None and parent.outer_guard is self.outer_guard)
        self.journal.verify()
        reference=dict(navigationPreparationBridgeVersion=2,scopeSha256=self.scope_sha,
            originalLease=read_original(self.journal.store(self.state['lease']).path),
            bridge=read_original(self.journal.store(self.state['bridge']).path),origin=deepcopy(self.state['parent']['origin']),
            originPacket=deepcopy(self.state['parent']['originPacket']))
        prior=read_bridge(reference,parent)
        self.journal.verify();need(same(prior,self.state['controllers'][-1]['envelope']));return deepcopy(reference),prior

    def scene(self,role,ticket):
        """Archive actual original stereo; external runner decides changed pixels."""
        self.bound();need(role in ROLE_NAMES and self.state['phase']=='ready')
        parent=self.parent(role)
        with self.lock.held():
            parent.load();parent.fence();need(ticket==parent.state['fixture']['activations'][-1]['ticket']
                and not any(row['role']==role and row['ticket']==ticket for row in self.state['scenes']))
            self.change(pending=dict(kind='scene',role=role,ticket=ticket),phase='acting')
            stereo=self.stereo_factory(parent,ticket)
            need(isinstance(stereo,NavigationStereo) and stereo.role==role and stereo.run==self.run
                and stereo.lock is self.lock and same(stereo.binding,self.binding) and stereo.arrival is parent.source.arrival)
            original_factory=stereo.capture_factory
            def capture():return self.capture(parent,original_factory())
            stereo.capture_factory=capture
            frame=stereo.acquire(ticket);self.bound()
            need(frame['phase']=='complete');reference=read_original(stereo.store.path)
            originals=[reference,read_original(stereo.images.root/frame['image']['name'])]
            need(all(row['present'] for row in originals))
            index=self.append(dict(kind='scene',role=role,ticket=ticket,originals=originals))
            self.change(phase='ready',pending=None,scenes=[*self.state['scenes'],dict(role=role,ticket=ticket,chunk=index)])
        need(all(same(read_original(row['path']),row) for row in originals));self.bound();return deepcopy(frame)

    def capture(self,parent,owned):
        """Keep each original guard; append the same parent/time fence.

        The actual Native capture has another guard AFTER durable acquisition
        intent and immediately BEFORE send. A changed phase/deadline there
        retains that intent and issues no GPU request.
        """
        need(isinstance(owned,OwnedWorldRenderCapture) and owned.owner.role==parent.role
            and same(owned.owner.binding,self.binding) and parent is self.parents[parent.role])
        objects=[owned.capture,owned.storage,owned.owner,owned.receipts.cleanup]
        for target in objects:
            original=target.guard
            def guard(original=original):
                self.bound();parent.fence();result=original();self.publish_bound();return result
            target.guard=guard;self.capture_fences.append((target,original,guard))
        return owned

    def close_host(self):
        # This releases this host's descriptors only. It is not feature cleanup,
        # original-user restoration, Parent/Actor retirement or a whole verdict.
        raw=self.raw.close_host();originals=[reader.close() for reader,_reference,_digest in self.fixed_originals.values()]
        directory=self.directory.close();return raw and all(originals) and directory
