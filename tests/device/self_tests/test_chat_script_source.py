"""Actual Python source transactions with synthetic native/V8 packet seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.script_source import ChatScriptSource,identity,pins
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_native_script_observation import Boundary,code_source,effect_source
from self_tests.test_native_script_roots import RootBoundary
from self_tests.test_native_script_membership import membership_source,manager

RUN='e'*32
BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:original-start',
    sessionId='actual-binding',generation=1,targetFingerprint='c'*64)


class CompiledBoundary:
    def __init__(self,root='file:///actual/configured/cache/scripts'):
        self.roots=RootBoundary();self.roots.root=root;self.script=Boundary();self.mutate=None
        self.physical=root.rstrip('/')+'/communityScripts/armored-chat/armored_chat.js'
        if root.startswith('qrc:'):self.physical='qrc:/scripts/communityScripts/armored-chat/armored_chat.js'
        self.script.engine['url']='file:///~//communityScripts/armored-chat/armored_chat.js' if root.startswith('file:') else self.physical
        self.script.engine['required']['modules']=[];self.script.engine['required']['sequence']=0
        self.script.mutate=self.full
    def full(self,value):
        value['instance']=self.roots.instance
        raw=(Path(__file__).resolve().parents[3]/pins()['path']).read_text()
        code_source(value,raw);effect_source(value)
        membership_source(value,[manager(url=self.physical)])
        value['source'].update(loadSourceVersion=1,loads=dict(complete=True,instance='d'*32,sequence=0,events=[]),compiledSourceVersion=1)
        for engine in value['source']['engines']:
            engine['compiled']=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=17,
                resourceName=engine['url'],encoding='utf-16le-code-units',codeUnits=pins()['codeUnits'],
                sha256=pins()['sha256'],compiledEpochMs=19000)])
        if self.mutate:self.mutate(value)
    def readers(self):
        scripts=self.script.reader();scripts.monotonic=lambda:self.roots.clock;scripts.sleep=self.roots.sleep
        return self.roots.reader(),scripts
    def owner(self,directory,role='primary'):
        roots,scripts=self.readers()
        lock=ScriptSourceLock(Path(directory)/'script-sources.lock')
        with lock.held():
            return ChatScriptSource(RUN,role,BINDING,roots,scripts,PrivateFeatureState(Path(directory)/f'{role}-code.json'),
                lock,monotonic=lambda:self.roots.clock)
    def packets(self):
        roots,scripts=self.readers();before=roots.read(0)
        observed=scripts.read(0,require_code_identity=True,require_membership=True)
        return before,observed,roots.read(before['sequence'])


class ChatScriptSourceTests(unittest.TestCase):
    def test_fixed_phone_chat_bytes_are_reused_with_actual_pico_assignment_and_compilation(self):
        source=CompiledBoundary();before,scripts,after=source.packets()
        selected=identity(before,scripts,after,pid=31,epoch=20000)
        self.assertEqual(source.physical,selected['assignedUrl']);self.assertEqual(source.script.engine['url'],selected['url'])
        self.assertEqual(17,selected['compilation']['scriptId']);self.assertEqual(18706,selected['code']['codeUnits'])
        self.assertEqual('a'*32,selected['manager']);self.assertNotEqual(selected['url'],selected['assignedUrl'])
        self.assertTrue(all(set(row)=={'schemaVersion','commandId','action'} for row in source.roots.commands+source.script.commands))

    def test_actual_qrc_and_physical_file_engine_keys_are_supported_without_basename_fallback(self):
        for root,physical_key in (('qrc:/scripts',False),('file:///actual/configured/cache/scripts',True)):
            source=CompiledBoundary(root)
            if physical_key:source.script.engine['url']=source.physical
            before,scripts,after=source.packets()
            with self.subTest(root=root):self.assertEqual(source.physical,identity(before,scripts,after,pid=31,epoch=20000)['assignedUrl'])

    def test_pending_duplicate_manager_or_unknown_native_extensions_never_supply_identity(self):
        faults=('pending-duplicate','unassigned','foreign-assignment','incomplete-membership','missing-code','missing-compiled',
            'incomplete-compiled','stopping','foreign-key','compile-name','compile-hash','late-assignment','early-compilation','second-compilation','foreign-compiled-copy')
        for fault in faults:
            source=CompiledBoundary();before,scripts,after=source.packets();value=deepcopy(scripts)
            data=value['source'];engine=data['engines'][0];member=data['membership']['managers'][0];compiled=engine['compiled']['compilations'][0]
            if fault=='pending-duplicate':
                data['membership']['managers'].append(manager(instance='f'*32,url=source.physical));data['membership']['revision']=2
            elif fault=='unassigned':member.update(assigned=False,url='',loadGeneration=0,assignedEpochMs=0)
            elif fault=='foreign-assignment':member['url']='file:///foreign/scripts/communityScripts/armored-chat/armored_chat.js'
            elif fault=='incomplete-membership':data['membership']={'complete':False}
            elif fault=='missing-code':
                del data['sourceIdentityVersion'];del engine['code']
            elif fault=='missing-compiled':
                del data['compiledSourceVersion'];del engine['compiled']
            elif fault=='incomplete-compiled':engine['compiled']=dict(compiledSourcesVersion=1,complete=False)
            elif fault=='stopping':engine['stopping']=True
            elif fault=='foreign-key':engine['url']='file:///foreign/scripts/communityScripts/armored-chat/armored_chat.js'
            elif fault=='compile-name':compiled['resourceName']='qrc:/foreign/armored_chat.js'
            elif fault=='compile-hash':compiled['sha256']='f'*64
            elif fault=='late-assignment':member['assignedEpochMs']=16000
            elif fault=='early-compilation':compiled['compiledEpochMs']=14000
            elif fault=='second-compilation':engine['compiled']['compilations'].append(dict(compiled,scriptId=18))
            else:
                other=deepcopy(engine);other['url']='file:///other.js';other['required']['instance']='f'*32
                data['engines'].append(other);data['membership']['managers'].append(manager(instance='f'*32,url='file:///other.js'));data['membership']['revision']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):identity(before,value,after,pid=31,epoch=20000)

    def test_original_pid_birth_roots_order_and_total_native_age_remain_required(self):
        for fault in ('pid','birth','root','root-nonce','root-sequence','order','old-barrier'):
            source=CompiledBoundary();before,scripts,after=source.packets()
            if fault=='pid':scripts['processId']=32
            elif fault=='birth':scripts['instance']='f'*32
            elif fault=='root':after['source']['defaultScriptsUrl']='file:///foreign/scripts'
            elif fault=='root-nonce':after['commandId']=before['commandId']
            elif fault=='root-sequence':after['sequence']=before['sequence']
            elif fault=='order':scripts['requestedEpochMs']=19999
            else:before['requestedEpochMs']=18499;before['capturedEpochMs']=18500
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):identity(before,scripts,after,pid=31,epoch=20000)

    def test_durable_original_transactions_restore_passively_and_query_again_with_independent_role(self):
        with tempfile.TemporaryDirectory() as directory:
            source=CompiledBoundary();owner=source.owner(directory)
            first=owner.capture('1'*32,20000);self.assertEqual(1,len(owner.frames));self.assertEqual(2,owner.previous['revision'])
            commands=len(source.roots.commands)+len(source.script.commands)
            restored=source.owner(directory);self.assertEqual(commands,len(source.roots.commands)+len(source.script.commands))
            self.assertEqual(first,restored.capture('2'*32,20000));self.assertEqual(commands+3,len(source.roots.commands)+len(source.script.commands))
            actor=source.owner(directory,'actor');self.assertIsNot(actor.roots,restored.roots)
            self.assertEqual(first,actor.capture('3'*32,20000));self.assertEqual(1,len(actor.frames))
            first['code']['sha256']='f'*64;self.assertNotEqual(first['code'],restored.frames[0]['scripts']['source']['engines'][0]['code'])

    def test_lost_original_read_or_orphan_chunk_is_retained_without_query_replay_or_adoption(self):
        with tempfile.TemporaryDirectory() as directory:
            source=CompiledBoundary();owner=source.owner(directory);source.script.ignore=True
            with self.assertRaises(NativeUIError):owner.capture('1'*32,20000)
            self.assertEqual('reading',owner.store.read()['phase']);commands=len(source.roots.commands)+len(source.script.commands)
            with self.assertRaises(NativeUIError):owner.capture('2'*32,20000)
            with self.assertRaises(NativeUIError):source.owner(directory)
            self.assertEqual(commands,len(source.roots.commands)+len(source.script.commands))
        with tempfile.TemporaryDirectory() as directory:
            source=CompiledBoundary();owner=source.owner(directory);owner.capture('1'*32,20000)
            owner.store.path.unlink();commands=len(source.roots.commands)+len(source.script.commands)
            with self.assertRaises(NativeUIError):source.owner(directory)
            self.assertEqual(commands,len(source.roots.commands)+len(source.script.commands))

    def test_changed_live_manager_or_compiled_script_id_never_replaces_original_identity(self):
        for fault in ('manager','scriptId'):
            with tempfile.TemporaryDirectory() as directory:
                source=CompiledBoundary();owner=source.owner(directory);owner.capture('1'*32,20000)
                def change(value):
                    if fault=='manager':
                        value['source']['engines'][0]['required']['instance']='f'*32
                        value['source']['membership']['managers'][0]['instance']='f'*32;value['source']['membership']['revision']=2
                    else:value['source']['engines'][0]['compiled']['compilations'][0]['scriptId']=18
                source.mutate=change
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.capture('2'*32,20000)
                self.assertEqual('reading',owner.store.read()['phase']);self.assertEqual(1,len(owner.frames))

    def test_slow_final_copy_cas_and_clock_fail_under_either_frozen_clock(self):
        for location in ('copy','cas','clock'):
            for clock in ('host','native'):
                with tempfile.TemporaryDirectory() as directory:
                    source=CompiledBoundary();owner=source.owner(directory);real_write=owner.store.write
                    def advance():
                        if clock=='host':source.roots.clock+=2
                        else:source.roots.epoch+=2000
                    def write(value,previous):
                        real_write(value,previous)
                        if value['phase']=='ready' and location in ('cas','clock'):
                            if location=='cas':advance()
                            else:
                                def late_clock():
                                    old=source.roots.epoch;advance();return source.roots.epoch if clock=='native' else old
                                owner.roots.clock_ms=late_clock
                    def copy(value):
                        result=deepcopy(value)
                        if type(value) is dict and set(value)=={'ticket','afterEpochMs','before','scripts','after'}:advance()
                        return result
                    owner.store.write=write
                    with self.subTest(location=location,clock=clock),patch('adapters.chat_journey.script_source.deepcopy',copy if location=='copy' else deepcopy),self.assertRaises(NativeUIError):
                        owner.capture('1'*32,20000)
                    self.assertEqual([],owner.frames);self.assertTrue(owner.failed)


if __name__=='__main__':unittest.main()
