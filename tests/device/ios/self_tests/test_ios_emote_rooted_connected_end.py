"""Connected paired finish with actual process/SDK/OS/archive transactions.

The frozen native live graph, fresh fence/Stop authorization and reopening
constructors are explicit models. Real process WALs, both OS stages, SDK cuts,
once-only DELETE/GET404, ordered metadata retirement and terminal projection
are connected here. This does not qualify whole Emote or a physical device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.retirement_receipts import binding_from_context
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_rooted_finish import IOSEmoteRootedFinish
from ios.adapters.emote_rooted_sdk_cut import IOSEmoteRootedSDKCut
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_terminal import IOSEmoteTerminal
from ios.adapters.installed_code import VERSION
from ios.self_tests import test_ios_emote_rooted_end_archive as archive_fixture
from ios.self_tests.test_ios_bundle_observation import Boundary as BundleBoundary
from ios.self_tests.test_ios_retired_process import Boundary,SOURCE,BUNDLE


class RootedConnectedEndModelTests(unittest.TestCase):
    def setUp(self):
        self.f=archive_fixture.RootedEndArchiveStorageTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        for session in self.f.sessions.values():session.store.discard(session.previous)
        self.os={role:Boundary() for role in ('actor','primary')};self.stops=[];self.calls=[];self.live=[];self.deleted=set();self.fault=''
        self.sdk={};self.installed={};self.flows={};case=self
        def forbidden_binding(*args,**kwargs):self.fail('Unmodeled binding/native getter reached by connected end model')
        base=SimpleNamespace(target=lambda selector:dict(appId=BUNDLE),_candidate_guard=lambda **kwargs:None,_binding=forbidden_binding)
        self.runtime=IOSEmoteRuntime(base)
        self.runtime._sources=lambda *args:self.fail('No unmodeled native factory is authorized in this end model')
        for role,process in self.f.processes.items():
            os=self.os[role];os.pid=int(process.binding['processIdentity']);os.anchor['pid']=os.pid;os.anchor['bundlePids']=[os.pid,os.pid]
            self.sdk[role]=PrivateFeatureState(self.f.sdk[role]/'session.json')
            self.sdk[role].write({key:process.binding[key] for key in ('sessionId','generation','targetFingerprint')},None)
            bundle=BundleBoundary();bundle.mutate=lambda packet,pid=os.pid:packet.update(processId=pid)
            bundle.send(dict(schemaVersion=1,commandId='ios-'+'a'*32,action='ios-bundle-observe'));observed=json.loads(bundle.original())
            self.installed[role]=PrivateFeatureState(self.f.sdk[role]/'installed-code-binding.json')
            self.installed[role].write(dict(bindingVersion=VERSION,phase='retired',scope={key:value for key,value in process.binding.items() if key!='processIdentity'},
                source=deepcopy(SOURCE),process=dict(bundleId=BUNDLE,pid=os.pid,foreground=True),observation=observed,previousInstance=None,recovery=None),None)
            phase=SimpleNamespace(status=lambda phase=deepcopy(self.f.archive.state['phaseOriginal']):deepcopy(phase))
            def components(role=role):
                need(role not in case.stops);case.live.append(role);return dict(scope=dict(explicitFreshScopeModel=True))
            flow=SimpleNamespace(selector=role,actor_selector='actor',run=process.run,state=dict(binding=deepcopy(process.binding),phaseInstance=phase.status()['instance']),
                phase=phase,epoch_ms=os.epoch,components=components,pointers=lambda parts:dict(explicitPointerModel=True),keys=lambda parts:dict(explicitKeyModel=True))
            self.flows[role]=flow;process.flow=flow;process.runtime=self.runtime;process.primary_lock=self.f.locks['primary']
            process.monotonic=lambda os=os:os.clock;process.last_clock=process.deadline=None;process.phase=phase;process.seal=None
            process.peer=None if role=='actor' else self.f.processes['actor']
        description=dict(featureTerminalVersion=1,profile='ios-native-process-end-v1',area='emotes',runId=self.flows['primary'].run,ticket='8'*32,
            roles={role:dict(binding=binding_from_context(process.binding),heldResources=[],originalSha256=('a' if role=='actor' else 'b')*64)
                for role,process in self.f.processes.items()})
        self.f.seal=dict(featureTerminalSealVersion=1,description=description,windowSha256='c'*64,liveOriginalSha256='f'*64)
        for role,process in self.f.processes.items():
            process.seal=deepcopy(self.f.seal)
            # The actual immutable fence file remains independently read. Only
            # its native/freshness authorization is modeled at this seam.
            body=process.fence_original();ref=process.model_fence
            def fence_validate(process=process):
                value=process.fence_original();metadata={}
                for key,tail in (('scope','marker'),('keys','keys'),('pointers','pointers')):
                    path=process.lock.path.with_name('ios-emote-'+process.role+'-'+tail+'.json')
                    store=PrivateFeatureState(path) if process.retirement is None else process.retirement.store_for(path,value[key])
                    need(same(store.read(),value[key]));metadata[path]=deepcopy(value[key])
                return dict(metadata=metadata)
            process.fence_validate=fence_validate
            del process.completed
            process.state=dict(phase='prepared',source=deepcopy(SOURCE),bundleId=BUNDLE,peer=None if role=='actor' else dict(explicitDeferredActorModel=True),
                fence=ref,pending=None,processSha256=None)
            # Actual primary decode binds the completed Actor envelope later;
            # defer writing the primary prepared WAL until its first Stop.
            old=process.store.read();process.store.discard(old);process.previous=None
            if role=='actor':process.save()
            def stop(scope,pointers,keys,process=process):
                need(process.role not in case.stops)
                if process.role=='primary':
                    need(case.f.processes['actor'].state['phase']=='complete')
                    process.state['peer']=deepcopy(case.f.processes['actor'].previous)
                process.state['phase']='stop-issued';process.save();case.stops.append(process.role)
                if case.fault=='lost-stop' and process.role=='actor':case.fault='';raise RuntimeError('Explicit lost canonical Stop reply')
            process.stop=stop
        base.read_session=lambda selector:self.sdk[selector].read()
        base._binding_store=lambda selector:self.installed[selector]
        base.state_path=lambda selector:self.sdk[selector].path
        base._retired_candidate_scope=lambda selector,scope:dict(serverUrl='http://127.0.0.1:9/'+selector,appId=BUNDLE)
        class SDK:
            def __init__(_self,server):_self.role=server.rsplit('/',1)[-1]
            def call(_self,method,path):
                role=_self.role;case.calls.append((role,method));case.assertEqual('/session/'+case.f.processes[role].binding['sessionId'],path)
                if role in case.deleted:raise WebDriverRequestError(404,'Explicit independent SDK404')
                if method=='DELETE':
                    if case.fault=='ignored-sdk':return {}
                    case.deleted.add(role)
                else:case.assertEqual('GET',method)
                return {}
        self.enterContext(patch('ios.adapters.appium_adapter.WebDriver',side_effect=SDK))
        self.enterContext(patch('ios.adapters.emote_rooted_process_end.retired_process_observer',side_effect=lambda runtime,selector,*args:self.os[selector].reader()))
        self.enterContext(patch('ios.adapters.emote_rooted_session_end.retired_process_observer',side_effect=lambda runtime,selector,*args:self.os[selector].reader()))
        self.enterContext(patch('ios.adapters.emote_rooted_process_end.mark_stopped',side_effect=lambda *args:None))
        self.controller=object.__new__(IOSEmoteTerminal);self.controller.flow=self.flows['primary'];self.controller.actor=self.flows['actor']
        self.controller.clock=lambda:max(os.clock for os in self.os.values())
        def process_factory(flow,ownership,archive,seal,*,peer=None,retirement=None):
            process=self.f.processes[flow.selector];process.retirement=retirement
            # Model only constructor admission. Its actual private WAL and
            # all issued recovery paths still use the real process owner.
            if process.role=='primary' and process.previous is None:process.state['phase']='prepared'
            return process
        self.enterContext(patch('ios.adapters.emote_rooted_finish.IOSEmoteRootedProcessEnd',side_effect=process_factory))
        self.enterContext(patch.object(IOSEmoteRootedFinish,'freeze',return_value=(self.f.archive,self.f.ownership)))
    def invoke(self):return IOSEmoteRootedFinish(self.controller,self.f.seal).invoke()
    def complete(self):
        for _ in range(30):
            try:return self.invoke()
            except EmoteObservationPending:
                for os in self.os.values():os.clock+=1.6
        self.fail('Bounded paired end model did not complete')
    def test_connected_actor_primary_os_sdk_and_metadata_end_then_pure_historical_retry(self):
        result=self.complete();self.assertEqual('finish',result['stage']);self.assertEqual(['actor','primary'],self.stops)
        self.assertEqual(['actor','primary'],self.live);self.assertEqual({'actor','primary'},self.deleted)
        for role in ('actor','primary'):self.assertEqual(1,self.calls.count((role,'DELETE')))
        self.assertTrue(all(path.read() is None for path in self.f.paths));self.assertEqual(self.f.frozen,self.f.archive.store.read())
        calls,queries=deepcopy(self.calls),{role:deepcopy(os.queries) for role,os in self.os.items()}
        self.assertEqual(result,self.invoke());self.assertEqual(calls,self.calls);self.assertEqual(queries,{role:os.queries for role,os in self.os.items()})
    def test_lost_actor_stop_reply_continues_real_os_owners_without_a_second_stop(self):
        self.fault='lost-stop'
        with self.assertRaises(RuntimeError):self.invoke()
        self.assertEqual('stop-issued',self.f.processes['actor'].state['phase'])
        result=self.complete();self.assertEqual('finish',result['stage']);self.assertEqual(['actor','primary'],self.stops)
    def test_ignored_sdk_delete_retains_all_scene_metadata_and_never_resends(self):
        self.fault='ignored-sdk'
        with self.assertRaises(NativeUIError):self.complete()
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.invoke()
        self.assertEqual(1,self.calls.count(('actor','DELETE')));self.assertEqual(0,self.calls.count(('primary','DELETE')))
        self.assertTrue(all(path.read() is not None for path in self.f.paths));self.assertEqual(['actor','primary'],self.stops)
    def test_new_unknown_carrier_after_full_sdk_cut_blocks_dispatch_and_retirement(self):
        issued=IOSEmoteRootedSDKCut.issued
        def new_carrier(cut,reads):
            path=self.f.artifacts['actor']/'emote-late-unowned-model.json';store=PrivateFeatureState(path)
            if store.read() is None:store.write(dict(unknown=True),None)
            return issued(cut,reads)
        with patch.object(IOSEmoteRootedSDKCut,'issued',new_carrier),self.assertRaises(NativeUIError):self.complete()
        self.assertFalse(any(method=='DELETE' for _role,method in self.calls));self.assertTrue(all(path.read() is not None for path in self.f.paths))
    def test_same_byte_original_replacement_during_sdk_cut_decode_blocks_delete(self):
        original_init=IOSEmoteRootedSDKCut.__init__;completed=self.f.processes['actor'].completed;active=[];changed=[]
        def cut_init(cut,session):
            active.append(True)
            try:return original_init(cut,session)
            finally:active.pop()
        def interrupted():
            value=completed()
            if active and not changed:
                changed.append(True);prior=self.f.proof.read();self.f.proof.write(prior,prior)
            return value
        with (patch.object(IOSEmoteRootedSDKCut,'__init__',cut_init),
                patch.object(self.f.processes['actor'],'completed',interrupted),self.assertRaises(NativeUIError)):
            self.complete()
        self.assertTrue(changed);self.assertFalse(any(method=='DELETE' for _role,method in self.calls))
        self.assertTrue(all(path.read() is not None for path in self.f.paths))


if __name__=='__main__':unittest.main()
