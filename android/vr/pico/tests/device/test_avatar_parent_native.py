"""Common-v16/OverteSession parent over live original Qt/Settings owners.

The frozen package/Android SDK and scene/OS boundaries remain explicit actors.
The default profile also declares Model/geometry; the separate original-model
profile joins actual selected Model/Watcher/FST/FBX/Baker/HFM sources. Normal QML/input/JS/native preference persistence and Qt
callbacks execute now; no archived native frame is returned as a fresh source.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import select
import shutil
import hashlib
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
from test_avatar_people_controls_native import native_ui_binary
import test_avatar_urls_owner as boundary
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import avatar_state,avatar_preferences,avatar_bookmarks,avatar_bookmark_loads,avatar_model_connections
from adapters.pico4.navigation import PicoNavigation,NativeNavigationIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.script_journey.history import unpack
from feature_journeys.engine import Journey

RUN='a'*32


class LiveOriginalUI:
    def __init__(self,test,stage,environment,binary,selector_deadline,*,original_model=False):
        self.test,self.stage=test,stage;self.rows=[];self.last={};self.sequence={};self.version=2 if original_model else 1
        self.started=time.monotonic();self.budget_ms=min(60000,int((selector_deadline-self.started)*1000));need(self.budget_ms>0)
        self.deadline=min(selector_deadline,self.started+self.budget_ms/1000)
        environment=dict(environment,OVERTE_AVATAR_NATIVE_TRACE=str(stage/'live-originals'),
            OVERTE_AVATAR_PARENT_SERVICE_BUDGET_MS=str(self.budget_ms))
        self.stderr=(stage/'live.stderr').open('wb')
        self.process=subprocess.Popen(['unshare','--user','--map-root-user','--net',str(binary),'--testScript',str(ROOT),str(stage/'imports')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,env=environment,bufsize=0)
        self.pid=self.process.pid
        self.identity=str(self.pid)+':'+Path('/proc/'+str(self.pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
        self.record=(stage/'live-transport.jsonl').open('xb');os.chmod(self.record.name,0o600)
    def guard(self):
        need(self.process.poll() is None and time.monotonic()<self.deadline
            and self.identity==str(self.pid)+':'+Path('/proc/'+str(self.pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]);return True
    def call(self,kind,command=None):
        self.guard();request=dict(avatarParentServiceVersion=self.version,requestId=uuid.uuid4().hex,kind=kind,command=command or {})
        raw=json.dumps(request,separators=(',',':')).encode()+b'\n';need(len(raw)<=65536)
        self.process.stdin.write(raw);self.process.stdin.flush();remaining=self.deadline-time.monotonic()
        need(bool(select.select([self.process.stdout],[],[],min(5,remaining))[0]))
        reply=self.process.stdout.readline(1024*1024+1);need(reply.endswith(b'\n') and len(reply)<=1024*1024)
        received=time.monotonic_ns();epoch=int(time.time()*1000)
        event=dict(avatarParentTransportVersion=1,request=request,raw=reply.decode(),hostReceivedNs=received,hostEpochMs=epoch)
        line=json.dumps(event,separators=(',',':')).encode()+b'\n';need(len(self.rows)<512 and self.record.tell()+len(line)<=16*1024*1024)
        self.record.write(line);self.record.flush();os.fsync(self.record.fileno());self.rows.append(event)
        value=json.loads(reply);self.test.assertEqual({'avatarParentServiceVersion','requestId','kind','processId','nativeMonotonicNs','source'},set(value))
        self.test.assertEqual(self.version,value['avatarParentServiceVersion']);self.test.assertEqual(request['requestId'],value['requestId'])
        self.test.assertEqual(kind,value['kind']);self.test.assertEqual(self.pid,value['processId'])
        if len(self.rows)>1:self.test.assertGreaterEqual(value['nativeMonotonicNs'],json.loads(self.rows[-2]['raw'])['nativeMonotonicNs'])
        self.last[kind]=value['source'];return deepcopy(value['source'])
    def stop(self):
        # Failure cleanup ends only this declared host fixture. It never serves
        # as evidence of product owner/cache/request retirement.
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
        self.process.stdin.close();self.process.stdout.close()
        self.record.close();self.stderr.close()


class AvatarParentNativeTests(unittest.TestCase):
    def test_common_v16_parent_cached_favorite_live_preferences_and_retained_normal_return(self):
        self._run_original_parent(False)

    def test_common_v16_parent_real_fst_fbx_loader_and_original_geometry_return(self):
        self._run_original_parent(True)

    def _run_original_parent(self,original_model):
        selector_deadline=time.monotonic()+120
        if 'OVERTE_AVATAR_PARENT_SELECTOR_DEADLINE_NS' in os.environ:
            selector_deadline=min(selector_deadline,int(os.environ['OVERTE_AVATAR_PARENT_SELECTOR_DEADLINE_NS'])/1e9)
        with native_ui_binary(True,parent=True,original_model=original_model) as (stage,environment,binary):
            if original_model:
                from feature_journeys.fixtures import pinned_resource
                inventory=json.loads((ROOT/'tests/device/feature_journeys/resource-pins.v1.json').read_text())['resources']
                names=['avatar-a.fst','mannequin/mannequin.fbx']+[name for name in inventory if name.startswith('mannequin/') and name.endswith('.png')]
                entries=[]
                for name in names:
                    raw=pinned_resource(name);entries.append(dict(relative=name,path=str(ROOT/inventory[name]['source']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                inputs=stage/'avatar-model-inputs.json';inputs.write_text(json.dumps(dict(avatarOriginalModelInputsVersion=1,
                    fixtureBase='http://controlled.test/feature-fixture/v1/runs/'+RUN+'/',files=entries),sort_keys=True)+'\n')
                environment['OVERTE_AVATAR_MODEL_INPUTS']=str(inputs)
                for variable in ('XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'):
                    directory=stage/variable;directory.mkdir(mode=0o700);environment[variable]=str(directory)
            live=LiveOriginalUI(self,stage,environment,binary,selector_deadline,original_model=original_model);self.addCleanup(live.stop)
            system_time=time.time
            # All session environment belongs to the cold candidate admission;
            # the original full environment seal must never be changed warm.
            self.enterContext(patch.dict(os.environ,dict(OVERTE_PICO_AVATAR_PARENT_SOURCE='1',
                OVERTE_DEVICE_ADAPTER_MANIFEST=str(stage/'session.json'),
                OVERTE_DEVICE_TARGET_SELECTOR=boundary.sources.existing.FakeAdb.target,
                OVERTE_DEVICE_ARTIFACT_DIR=str(stage/'artifacts'))))
            self.enterContext(patch.object(boundary,'RUN',RUN))
            fixture=boundary.AvatarUrlsTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
            self.enterContext(patch("adapters.common.time.time",side_effect=system_time))
            f=fixture;f.journal.clock=lambda:time.time_ns()//1000000
            def retain_owned_state():
                identities={}
                for path in f.root.rglob('*'):
                    if path.is_file() and not path.is_symlink():
                        info=path.lstat();identities[str(path.relative_to(f.root))]=dict(device=info.st_dev,inode=info.st_ino,mode=info.st_mode,
                            bytes=info.st_size,modifiedNs=info.st_mtime_ns,changedNs=info.st_ctime_ns,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                shutil.copytree(f.root,stage/'retained-owner-state',symlinks=True)
                (stage/'retained-owner-identities.json').write_text(json.dumps(identities,sort_keys=True)+'\n')
            self.addCleanup(retain_owned_state)
            snapshot=live.call('widgets');original_preferences=live.call('preferences',dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=avatar_preferences.ACTION))
            original_callbacks=live.call('callbacks',dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=avatar_model_connections.ACTION))
            native=original_preferences['source']['snapshot']['cache']['native'];f.source['avatarEntityStorage']['rows']=[]
            f.source['modelInstance']=native['modelInstance'];f.source['avatarLoads']['instance']=original_callbacks['source']['avatarInstance']
            f.source['modelName']=native['live']['modelName'];f.source['sessionId']=native['sessionId']
            binding=deepcopy(f.binding);binding.update(processIdentity=live.identity,sessionId=snapshot['bridgeId'])
            packets={};state_sequence=0;source_sequences={}
            def clock():return time.time_ns()//1000000
            def send(request):
                nonlocal state_sequence
                action=request['action']
                for key,module in (('preferences',avatar_preferences),('callbacks',avatar_model_connections)):
                    if action==module.ACTION:
                        packets[module.FILE]=json.dumps(live.call(key,request),separators=(',',':'));return
                if action==avatar_state.ACTION:
                    # The default profile declares Model/HFM/Avatar loading.
                    # The separate model profile replaces only those actual
                    # getter fields; Rig/scene/EntityTree remain declared.
                    model_original=live.call('model') if original_model else None
                    observed=live.call('preferences',dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=avatar_preferences.ACTION))
                    actual=observed['source']['snapshot']['cache']['native'];values=actual['live'];f.epoch=clock()
                    if f.source['requestedUrl']!=values['preferenceUrl']:f.effect(values['preferenceUrl'])
                    f.source.update(preferenceUrl=values['preferenceUrl'],modelName=values['modelName'],scale=values['scale'],targetScale=values['targetScale'])
                    value=deepcopy(f.source)
                    if original_model:
                        self.assertEqual(2,model_original['avatarOriginalModelObservationVersion'])
                        for key in ('avatarLoads','modelLoads','modelInstance','modelUrl','loaded'):value[key]=deepcopy(model_original[key])
                        actual_geometry=model_original['geometry']
                        value['geometry']=None if actual_geometry is None else dict(instance=actual_geometry['instance'],url=actual_geometry['url'])
                    else:
                        for key in ('avatarLoads','modelLoads'):
                            f.source[key]['sequence']+=1;value[key]['sequence']=f.source[key]['sequence'];value[key]['capturedEpochMs']=f.epoch
                    state_sequence+=1;packets[avatar_state.FILE]=json.dumps(dict(schemaVersion=1,requestId=request['commandId'],instance=observed['instance'],
                        sequence=state_sequence,processId=live.pid,requestedEpochMs=f.epoch,capturedEpochMs=f.epoch,source=value));return
                for key,module,member in (('bookmarks',avatar_bookmarks,'storage'),('loads',avatar_bookmark_loads,'loads')):
                    if action==module.ACTION:
                        requested=clock();original=live.call(key);source_sequences[key]=source_sequences.get(key,0)+1
                        source={('picoAvatarBookmarksVersion' if key=='bookmarks' else 'picoAvatarBookmarkLoadsVersion'):1,
                            'instance':('6' if key=='bookmarks' else '7')*32,member:original}
                        packets[module.FILE]=json.dumps(dict(schemaVersion=1,requestId=request['commandId'],instance=original_preferences['instance'],
                            sequence=source_sequences[key],processId=live.pid,requestedEpochMs=requested,capturedEpochMs=clock(),source=source));return
                raise AssertionError('Unregistered readonly native source')
            def reader():
                return avatar_state.NativePicoAvatarState(send,lambda:packets[avatar_state.FILE],clock,live.guard,live.pid,monotonic=time.monotonic,sleep=time.sleep)
            def read(_target,_package,path,**kwargs):
                self.assertEqual('org.overte.pico',_package)
                if path.endswith('/navigation-ui-observation.json'):return json.dumps(live.call('widgets'))
                if path.endswith('/navigation-ui-status.json'):return json.dumps(live.last['input'])
                return packets[path.rsplit('/',1)[-1]]
            def write(_target,_package,path,raw):
                self.assertEqual('files/overte-e2e/navigation-ui-command.json',path);live.call('input',json.loads(raw))
            def runtime(_target):
                identity=f.instance._installation(f.target)
                channel=NativeNavigationIO(f.instance,f.target,live.identity,lambda op:dict(performed=False))
                navigation=PicoNavigation(channel,f.root/'live-normal-navigation.json',identity,live.identity,
                    'http://controlled.invalid/scene.json',monotonic=time.monotonic,sleep=time.sleep)
                return SimpleNamespace(io=PicoScriptIO(navigation),monotonic=time.monotonic,sleep=time.sleep),None,deepcopy(binding)
            for seam in (patch.object(f.instance,'_script_runtime',side_effect=runtime),patch.object(f.instance,'_native_feature_observer',side_effect=lambda _target:reader()),
                patch.object(f.instance,'require_same_process',side_effect=lambda _target,identity,_label:self.assertEqual(live.identity,identity) or live.guard()),
                patch.object(f.instance,'require_pico_session_identity',side_effect=lambda _target:live.identity),
                patch.object(f.native,'read_debug_app_file',side_effect=read),patch.object(f.native,'write_debug_app_file',side_effect=write),
                patch.object(f.native,'epoch_milliseconds',side_effect=lambda _target:clock())):
                seam.start();self.addCleanup(seam.stop)
            support=importlib.import_module('module_support');session_module=importlib.import_module('overte_session')
            calls=[]
            def adapter_rpc(_manifest,target,operation,arguments):
                self.assertEqual(f.target,target);calls.append(operation);return f.instance.invoke(target,operation,arguments)
            with patch.object(support,'TARGET',f.target),patch.object(support,'invoke',side_effect=adapter_rpc):
                session=session_module.OverteSession()
                def invoke(operation,fields):return session.feature_operation('avatar-people',operation.rsplit('.',1)[1],fields)
                journey=Journey('avatar-people',RUN,f.phase.fixture_url,invoke=invoke,witness=lambda:None,activate=lambda *_args:None,
                    read_artifact=lambda _:None,image_policy={},continuity=lambda *_args:live.guard(),monotonic=time.monotonic,
                    epoch_ms=clock,sleep=time.sleep,report=lambda _:None)
                exceptions=[]
                def diagnose(frame,event,arg):
                    frame.f_trace_lines=False
                    if event=='exception' and '/tests/device/' in frame.f_code.co_filename:
                        exceptions.append(dict(path=frame.f_code.co_filename,line=frame.f_lineno,function=frame.f_code.co_name,
                            kind=type(arg[1]).__name__,message=str(arg[1])))
                        del exceptions[:-512]
                    return diagnose
                sys.settrace(diagnose)
                try:
                    with f.lock.held():f.instance._avatar_parent(f.target,RUN,source_lock=f.lock).prepare()
                finally:
                    sys.settrace(None);(stage/'source-exceptions.json').write_text(json.dumps(exceptions,sort_keys=True)+'\n')
                actions=[('avatar-url',dict(resource='avatar-a.fst'))]
                if not original_model:actions.append(('avatar-bookmark-save',dict(name='e2e-'+RUN)))
                actions.append(('avatar-restore',{}))
                for verb,inputs in actions:
                    ticket=uuid.uuid4().hex;f.journal.activate(RUN,ticket,verb,inputs)
                    self.assertEqual(dict(performed=True),journey.call('act',dict(verb=verb,inputs=inputs,ticket=ticket,fixtureUrl=f.phase.fixture_url)))
                f.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
                if not original_model:
                    with f.lock.held():f.instance._avatar_favorites(f.target,RUN,source_lock=f.lock).invoke('cleanup')
                for kind,fields in (('observe',dict(afterSequence=0)),('cleanup',{})):
                    with self.assertRaises((ValueError,RuntimeError)):journey.call(kind,fields)
            result=live.call('close');live.process.wait(timeout=min(2,max(.001,live.deadline-time.monotonic())));self.assertEqual(0,live.process.returncode)
            native_elapsed=time.monotonic()-live.started;self.assertLessEqual(native_elapsed,live.budget_ms/1000)
            self.assertEqual(2 if original_model else 3,calls.count('feature.avatar-people.act'));self.assertTrue(f.instance._avatar_parent_owned(f.target))
            from adapters.pico4.avatar_favorite_effect import original_preferences as same_data,unchanged_preferences
            same_data(result['originalPreferences']['packet'],result['restoredPreferences']['packet'])
            cached=[row for row in result['originalFavoritePreferences'] if row['cached']]
            if original_model:
                self.assertFalse(cached);actual=result['actualModel'];self.assertTrue(actual['loaded']);self.assertIsNotNone(actual['geometry'])
                self.assertEqual(boundary.FBX,actual['geometry']['url']);self.assertGreater(actual['geometry']['meshes'],0);self.assertGreater(actual['geometry']['joints'],0)
                self.assertEqual(3,len(actual['geometryOwners']));self.assertEqual([False,False,True],[row['alive'] for row in actual['geometryOwners']])
                self.assertEqual(actual['resources'][0]['instance'],actual['resources'][-1]['instance'])
                self.assertTrue(all(row['qObjectAlive'] for row in actual['resources']))
                self.assertEqual([False,False,True],[row['originalWeakHandleAlive'] for row in actual['resources']])
                self.assertGreaterEqual(actual['cache']['numCached'],1);self.assertGreaterEqual(actual['cache']['numTotal'],2)
                self.assertGreater(actual['cache']['unusedLimit'],0)
                for entry in entries:self.assertEqual(pinned_resource(entry['relative']),Path(entry['path']).read_bytes())
            else:
                self.assertEqual(1,len(cached));unchanged_preferences(cached[0]['before']['packet'],cached[0]['after']['packet'])
                self.assertEqual(1,cached[0]['afterLoads']['rows'][-1]['dispatches']);self.assertFalse(cached[0]['afterLoads']['rows'][-1]['captureAlive'])
            (stage/'parent-result.json').write_text(json.dumps(dict(kind='partial-common-v16-native-avatar-parent',calls=calls,
                native=result,transportQueries=len(live.rows),nativeServiceBudgetMs=live.budget_ms,nativeElapsedSeconds=native_elapsed,
                completeFeature=False,modelGeometryActor=not original_model,rigSceneEntityTreeActor=True),sort_keys=True)+'\n')


if __name__=='__main__':unittest.main()
