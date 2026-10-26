"""Fresh whole Emote sources joined to real installed/Stop/end host owners.

WDA, native and OS producers are explicit host models. Candidate preflight is
an explicit seam; structural ZIP and independent installed tree hashes are
actual. Release/SBOM verification and device acceptance are not exercised.
No feature seal, fence, process/SDK end constructor or authorization is patched.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from argparse import Namespace
from copy import copy,deepcopy
import base64
import hashlib
import json
from pathlib import Path
import plistlib
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit
import zipfile

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import check as transport_check
from adapters.script_feature.history import same
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.bundle_identity import artifact_bundle,root_digest
from ios.adapters.installed_adapter import create_physical_adapter
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_terminal import IOSEmoteTerminal
from ios.adapters import emote_operation
from ios.self_tests.emote_active_actor_fixture import ACTOR
from ios.self_tests.emote_rooted_whole_fixture import paired
from ios.self_tests.test_ios_bundle_observation import Boundary as BundleBoundary
from ios.self_tests.test_ios_emote_sources import BINDING
from ios.self_tests.test_ios_retired_process import Boundary as OSBoundary
from self_tests.test_native_feature_observation import Boundary as ClockBoundary


def installed_tree(root):
    """Measure independent installed-model files, never the candidate answer."""
    entries={}
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root).as_posix()
        if path.is_dir():entries[relative]=('D',0,hashlib.sha256(b'').digest())
        else:
            raw=path.read_bytes();entries[relative]=('F',len(raw),hashlib.sha256(raw).digest())
    info=plistlib.loads((root/'Info.plist').read_bytes());executable=(root/info['CFBundleExecutable']).read_bytes()
    return dict(bundleContractVersion=1,bundleId=info['CFBundleIdentifier'],executableSha256=hashlib.sha256(executable).hexdigest(),**root_digest(entries))


class OriginalProducer:
    """Declared raw boundary with original cursor restoration, no expected facts."""
    def __init__(self,read,guard):self.raw,self.guard,self.last=read,guard,None
    def read(self,*args):
        self.guard();value=self.raw(*args);self.guard();self.last=deepcopy(value);return value
    def restore(self,value):self.last=deepcopy(value[-1] if type(value) is list else value)


class RoleOS(OSBoundary):
    def __init__(self,domain,pid):
        self.domain=None;super().__init__();self.domain=domain;self.pid=pid
        self.anchor.update(pid=pid,bundlePids=[pid,pid],
            clockBefore=dict(epochMs=self.node_epoch()-5000,monotonicMs=1000),
            clockAfter=dict(epochMs=self.node_epoch()-4990,monotonicMs=1010))
    @property
    def clock(self):return self.local_clock if self.domain is None else self.domain.time
    @clock.setter
    def clock(self,value):
        if self.domain is None:self.local_clock=value
        else:self.domain.time=value
    def epoch(self):return 90000+round(self.clock*1000)


class WholeRootedEndFixture:
    def __init__(self,test,*,retain_originals=False):
        self.test=test;temporary=tempfile.TemporaryDirectory();test.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.artifacts=self.root/'candidate';self.artifacts.mkdir(mode=0o700)
        self.trees={};self.targets={};self.bindings={};self.alive=dict(primary=True,actor=True);self.deleted=set()
        self.stops=[];self.calls=[];self.native_reads=[];self.source_factories=[];self.fault='';self.sessions={}
        self.foreground=dict(primary=True,actor=True);self.lifecycle_inputs=[]
        self.fresh_roles=set();self.fresh_starts={};self.real_fence_to_stop={}
        files={'Info.plist':plistlib.dumps(dict(CFBundleIdentifier='org.example.overte',CFBundleExecutable='Overte',
            OverteE2ETestBuildContractVersion=1,UIFileSharingEnabled=True)),
            'Overte':b'Explicit synthetic host app bytes; no Mach-O, compilation or device acceptance',
            'assets/source.txt':b'Independent installed-tree source bytes'}
        self.ipa=self.artifacts/'Overte.ipa'
        with zipfile.ZipFile(self.ipa,'w') as archive:
            for name,raw in files.items():archive.writestr('Payload/Overte.app/'+name,raw)
        self.ipa.chmod(0o600);self.sha=hashlib.sha256(self.ipa.read_bytes()).hexdigest()
        for role,port in (('primary',49121),('actor',49122)):
            tree=self.root/(role+'-installed');tree.mkdir(mode=0o700);self.trees[role]=tree
            for name,raw in files.items():
                path=tree/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o600)
            self.targets[role]=dict(platform='ios',physical=True,appId='org.example.overte',
                artifactMode='personal-team-preinstalled',_artifactMode='personal-team-preinstalled',probe={'kind':'ios-documents'},
                serverUrl='http://127.0.0.1:9/'+role,testBuild=dict(resultsDirectory='owned-results',
                    fixtureOrigin='http://native-model.invalid:'+str(port),scenePath='/scene.json'),capabilities={})
            binding=BINDING if role=='primary' else ACTOR
            fingerprint=hashlib.sha256(json.dumps(self.targets[role],sort_keys=True,separators=(',',':')).encode()).hexdigest()
            test.enterContext(patch.dict(binding,artifactSha256=self.sha,targetFingerprint=fingerprint))
            self.bindings[role]=deepcopy(binding)
        original_init=BundleBoundary.__init__;current=self
        def native_init(boundary):original_init(boundary);boundary.bundle=installed_tree(current.trees['primary'])
        test.enterContext(patch.object(BundleBoundary,'__init__',native_init))
        self.normal=f=paired(test,retain_originals=retain_originals)
        self.roles=dict(primary=f,actor=f.actor);self.domains={role:item.target.domain for role,item in self.roles.items()}
        self.installations=dict(primary=f.primary_installed,actor=f.installed)
        self.os={role:RoleOS(self.domains[role],int(self.bindings[role]['processIdentity'])) for role in self.roles}
        self.clocks={role:ClockBoundary() for role in self.roles}
        for role,clock in self.clocks.items():clock.mutate=lambda value,role=role:value.update(processId=int(self.bindings[role]['processIdentity']))
        self.summary=dict(physicalHandoffVersion=1,bundleIdentity=artifact_bundle(self.ipa,self.sha),
            artifactIdentity=dict(sourceRevision=BINDING['sourceRevision'],artifactSha256=self.sha))
        class SDK:
            def __init__(_self,role):_self.role=role
            def call(_self,method,path,body=None):
                transport_check();role=_self.role;current.calls.append((role,method,path));session=current.bindings[role]['sessionId']
                need(path=='/session/'+session)
                if role in current.deleted:raise WebDriverRequestError(404,'Original modeled SDK absence')
                if method=='DELETE':
                    if current.fault!='ignored-sdk':current.deleted.add(role)
                    if current.fault=='lost-sdk':raise OSError('Original modeled lost SDK DELETE reply')
                else:need(method=='GET')
                return {}
            def execute(_self,session,operation,values):
                transport_check();role=_self.role;need(session==current.bindings[role]['sessionId'] and role not in current.deleted)
                current.calls.append((role,operation,deepcopy(values)));installation=current.installations[role]
                if operation=='mobile: overteProcessSourceInfo':return deepcopy(installation.source)
                if operation=='mobile: overteProcessInfo':
                    return dict(bundleId='org.example.overte',pid=int(current.bindings[role]['processIdentity']),foreground=current.foreground[role]) if current.alive[role] else None
                if operation=='mobile: terminateApp':
                    need(current.base._binding_store(role).read()['phase']=='retiring' and role not in current.stops)
                    if role in current.fresh_starts:current.real_fence_to_stop[role]=time.monotonic()-current.fresh_starts[role]
                    current.stops.append(role)
                    if current.fault!='ignored-stop':current.alive[role]=False
                    if current.fault=='lost-stop':raise OSError('Original modeled lost terminateApp reply')
                    return True
                if operation=='mobile: overteRetiredProcessInfo':
                    os=current.os[role];alive=current.alive[role];os.states=[4 if alive else 1]*2;os.pids=[os.pid if alive else 0]*2;os.running=[alive]*2
                    return os.send(values)
                if operation=='mobile: pullFile':
                    need(current.alive[role]);path=values['remotePath'];current.native_reads.append((role,path))
                    if path.endswith('/ios-installed-bundle-observation.json'):
                        installation.native.bundle=installed_tree(current.trees[role]);raw=installation.native.original()
                    elif path.endswith('/feature-native-observation.json'):raw=json.dumps(current.clocks[role].sample)
                    else:need(False)
                    return base64.b64encode(raw.encode()).decode()
                need(False)
        self.clients={role:SDK(role) for role in self.roles}
        class Base:
            def __init__(_self,platform):need(platform=='ios');_self.platform=platform;_self.adapter_id='appium-ios'
            @classmethod
            def advertised_capabilities(cls,target):return ['app.stop','app.process','app.foreground','app.launch','lifecycle.background']
            def target(_self,selector):need(selector in current.roles);return deepcopy(current.targets[selector])
            def state_path(_self,selector):return current.roles[selector].target.root/'session.json'
            def read_session(_self,selector):return PrivateFeatureState(_self.state_path(selector)).read()
            def save_session(_self,selector,state):
                store=PrivateFeatureState(_self.state_path(selector));old=store.read()
                if not same(old,state):store.write(state,old)
            def ensure_session(_self,selector):
                state=_self.read_session(selector);need(state is not None and selector not in current.deleted)
                return current.clients[selector],state['sessionId'],deepcopy(state)
            def query_app_state(_self,client,session,target):
                role=client.role;need(session==current.bindings[role]['sessionId'] and current.alive[role])
                return 4 if current.foreground[role] else 3
            def invoke(_self,selector,operation,values):
                # Declared WDA/OS lifecycle producer only. The physical adapter
                # still surrounds these ordinary deliveries with its actual
                # candidate, SDK, installed-source and same-process checks.
                transport_check();need(selector=='primary' and current.alive[selector] and values=={}
                    and operation in ('lifecycle.background','app.launch'))
                current.lifecycle_inputs.append(operation);counters=current.normal.target.rig.lifecycle
                if operation=='lifecycle.background':
                    need(current.foreground[selector]);current.foreground[selector]=False;counters['backgrounds']+=1
                else:
                    need(not current.foreground[selector]);current.foreground[selector]=True;counters['activations']+=1
                return {'backgrounded':True} if operation=='lifecycle.background' else {'launched':True}
        def preflight(_args):
            # Explicit candidate release/SBOM seam. IPA hashing and bundle tree
            # comparison below remain actual independent byte operations.
            need(artifact_bundle(current.ipa,current.sha)==current.summary['bundleIdentity']);return deepcopy(current.summary)
        self.base=create_physical_adapter(Namespace(artifact_root=str(self.artifacts)),Base,preflight)
        for role,item in self.roles.items():
            state={key:self.bindings[role][key] for key in ('sessionId','generation','targetFingerprint','processIdentity')}
            state.update(iosE2ELaunchCompleted=True,iosE2ESceneUrl=item.flow.phase.fixture_url)
            PrivateFeatureState(self.base.state_path(role)).write(state,None)
            store=self.base._binding_store(role);store.write(self.installations[role].store.read(),None)
        class Response:
            status=200
            def __init__(_self,raw):_self.raw=raw
            def __enter__(_self):return _self
            def __exit__(_self,*args):return False
            def read(_self,_limit):return _self.raw
        def native_post(request,timeout):
            port=urlsplit(request.full_url).port;role='primary' if port==49121 else 'actor';need(port in (49121,49122) and current.alive[role])
            query=json.loads(request.data);current.native_reads.append((role,query['action']))
            if query['action']=='ios-bundle-observe':current.installations[role].native.send(query)
            elif query['action']=='feature-native-observe':current.clocks[role].send(query)
            else:need(False)
            return Response(request.data)
        test.enterContext(patch('ios.adapters.feature_observation.post_request',side_effect=native_post))
        test.enterContext(patch('ios.adapters.appium_adapter.WebDriver',side_effect=lambda url:self.clients[url.rsplit('/',1)[-1]]))
        original_sources={role:item.runtime._sources for role,item in self.roles.items()}
        original_source_factories={role:item.runtime._emote_sources for role,item in self.roles.items()}
        class Runtime(IOSEmoteRuntime):
            def _sources(runtime,selector):
                need(selector in current.roles and current.alive[selector]);current.source_factories.append(selector)
                client,session,state,target,scope=runtime._existing(selector);gate=current.base._binding(selector,client,session,state,target)
                gate.verify();actual=gate.continuity();result=copy(original_sources[selector](selector));observer=copy(result['observer'])
                need(same(result['binding'],dict(scope,processIdentity=str(actual['pid']))))
                def guard():
                    emote_operation.check(runtime);current.base._candidate_guard()
                    need(current.alive[selector] and same(gate.continuity(),actual));emote_operation.check(runtime);return True
                result['check']=guard;domain=current.domains[selector];item=current.roles[selector]
                native_factory=observer.bound_native_observer
                def original_native(clock_source):
                    reader=native_factory(clock_source);send=reader.send
                    old_guard=reader.guard
                    def native_guard():need(old_guard() is not False);return guard()
                    reader.guard=native_guard
                    def sending(query):
                        # Observe actual elapsed time from the first original
                        # native query in a fresh fence. This does not change
                        # any callback, packet, acquisition clock or guard.
                        if selector in current.fresh_roles and selector not in current.fresh_starts:
                            current.fresh_starts[selector]=time.monotonic()
                        return send(query)
                    reader.send=sending;return reader
                observer.bound_native_observer=original_native
                result['native']=SimpleNamespace(capture=lambda:(guard(),domain.widgets())[1]);result['observer']=observer
                observer.script_terminal=lambda _:OriginalProducer(domain.terminal,guard)
                observer.script_work=lambda _:OriginalProducer(domain.work,guard)
                observer.script_dialogs=lambda _:OriginalProducer(domain.dialogs,guard)
                observer.web_closures=lambda:OriginalProducer(domain.web,guard)
                observer.script_fixture_files=lambda:item.target.scope.files.native
                return result
            def _emote_sources(runtime,selector,client,run,role,root,lock):
                return original_source_factories[role](selector,client,run,role,root,lock)
            def _emote_actions(runtime,selector,sources):
                actions=super()._emote_actions(selector,sources)
                # The actual action and NativeUI constructors/gates ran. Only
                # the declared producer's wait clock is supplied to this host
                # transport before its first input, as for the native readers.
                actions.sdk.sleep=current.domains[selector].sleep
                actions.sdk.monotonic=lambda:current.domains[selector].time
                return actions
            def _avatar_receive(runtime,selector):need(selector=='actor');return f.actor.target.receive_reader()
        self.runtime=Runtime(self.base)
        # Select the same real runtime and gates before any normal input or
        # marker WAL exists. Only declared producer assembly remains supplied
        # by the fixture; the end facades use the actual components method.
        for role,item in self.roles.items():
            scope=item.parts['scope'];need(item.flow.state is None and item.flow.store.read() is None
                and scope.previous is None and scope.store.read() is None and not scope.frames)
            baseline=item.target.phase.previous;need(baseline['active'] and baseline['activations'][-1]['stimulus']==dict(verb='baseline',inputs={}))
            scope.ticket=baseline['activations'][-1]['ticket']
            own=self.runtime._sources(role);primary=own if role=='primary' else self.runtime._sources('primary')
            item.parts.update(own=own,primary=primary);item.flow.runtime=self.runtime
            scope.guard=own['check'];scope.originals.guard=own['check']
            native_guard=scope.native.guard
            def guarded_native(native_guard=native_guard,guard=own['check']):need(native_guard() is not False);return guard()
            scope.native.guard=guarded_native
            sources=item.parts['sources'];sources.guard=primary['check'];sources.originals.guard=primary['check']
            item.parts['observer'].guard=own['check']
            peers=item.parts['peers']
            if peers is not None:peers.runtime=self.runtime;peers.guard=own['check'];peers.originals.guard=own['check']
            for key in ('samples','restoration'):
                item.parts[key].runtime=self.runtime;item.parts[key].selector=role
        self.facades={}
        for role,item in self.roles.items():
            flow=item.flow
            facade=IOSEmoteRootedFeature(self.runtime,role,flow.client,flow.run,role,flow.root,flow.policy,
                actor_selector='actor' if role=='primary' else None,primary_selector='primary' if role=='actor' else None,
                epoch_ms=flow.epoch_ms,monotonic=flow.monotonic,sleep=flow.sleep)
            facade.lock=flow.lock;facade.primary_lock=f.flow.lock;self.facades[role]=facade
        self.terminal=IOSEmoteTerminal(self.facades['primary'],self.facades['actor'])
