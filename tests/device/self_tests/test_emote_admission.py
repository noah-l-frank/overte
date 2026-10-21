"""Original all-executable/world admission joins over synthetic boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.emote_admission import catalog,executable,world,policy,KEYS
from adapters.normal_ui import NativeUIError
from self_tests.test_emote_rig_measurements import IncludedRigPackets
from self_tests.test_vertical_locomotion import snapshot

PROBE='file:///data/user/0/io.github.noah_be.overte.phone/files/overte-e2e/overte_e2e_probe.js'
DOMAIN='dddddddd-dddd-4ddd-8ddd-dddddddddddd'
POLICY=dict(domainUrl='hifi://controlled.invalid:40102/0,0,0',domainId=DOMAIN,
    domainMarkers=['OVERTE_E2E_DOMAIN_FLOOR','OVERTE_E2E_DOMAIN_ORIGIN'],probeUrl=PROBE)


def add_manager(value,url,code,*,identifier='f'*32,physical=None):
    source=value['source'];template=source['engines'][0];engine=deepcopy(template)
    engine.update(url=url,required=dict(instance=identifier,sequence=0,modules=[]),
        code=dict(submitted=True,submittedEpochMs=15000,**{key:code[key] for key in KEYS}),
        compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=11,
            resourceName=url,compiledEpochMs=15001,**{key:code[key] for key in KEYS})]))
    source['engines'].append(engine);source['membership']['revision']+=1
    source['membership']['managers'].append(dict(instance=identifier,assigned=True,url=physical or url,
        assignedEpochMs=14900,loadGeneration=1));return engine


def original_group():
    boundary=IncludedRigPackets();value=boundary.group(boundary.native(20000,baseline=True))
    value['script']['source']['engines'][0]['required'].update(sequence=0,modules=[])
    add_manager(value['script'],PROBE,catalog()['probe']);return value


def probe(sequence=10,epoch=20000):
    value=snapshot();value.update(sampleSequence=sequence,sampleEpochMs=epoch)
    value['domain'].update(connected=True,serverless=False,protocol='hifi',hostname='controlled.invalid',id=DOMAIN)
    value['scene'].update(url=POLICY['domainUrl'],domainMarkerCount=2,domainMarkers=deepcopy(POLICY['domainMarkers']),
        fixtureMarkerCount=0,fixtureMarkers=[],collisionWall=None)
    return value


class EmoteAdmissionTests(unittest.TestCase):
    def test_pins_reproduce_fixed_commit_and_current_repository_executable_sources(self):
        from generate_phone_emote_admission_catalog import generate,pin,JSON_MODULE,ROOT,BOUND
        pins=catalog();self.assertEqual(generate(),pins)
        for row in pins['files']:
            expected=pin(JSON_MODULE if row['kind']=='json-module' else (ROOT/row['path']).read_bytes().decode('utf-8'))
            self.assertEqual(expected,{key:row[key] for key in KEYS})
        self.assertEqual(pin((ROOT/pins['probe']['path']).read_bytes().decode('utf-8')),{key:pins['probe'][key] for key in KEYS})
        self.assertEqual(pin(BOUND),{key:pins['native'][0][key] for key in KEYS})
        self.assertIn('"'+BOUND+'"',(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text())

    def test_actual_default_and_pinned_probe_membership_are_independent_originals(self):
        group=original_group();selected,actual,proof=executable(group,pid=31,epoch=20000,probe_url=PROBE)
        self.assertEqual('phone-one-shot-hide-v1',selected['profile']['id']);self.assertEqual(PROBE,actual['url'])
        self.assertEqual(2,len(proof));proof[0]['code']['sha256']='f'*64
        self.assertNotEqual(proof[0]['code'],group['script']['source']['engines'][0]['code'])

    def test_normal_optional_child_managers_and_native_require_compilations_use_fixed_actual_bytes(self):
        group=original_group();root=group['rootsBefore']['source']['defaultScriptsUrl'].rstrip('/')+'/'
        pins=catalog();code=next(row for row in pins['files'] if row['runtimePath']=='system/create/edit.js')
        child=add_manager(group['script'],'file:///~//system/create/edit.js',code,identifier='c'*32,physical=root+'system/create/edit.js')
        child['compiled']['compilations'].append(dict(scriptId=12,compiledEpochMs=15002,**pins['native'][0]))
        self.assertEqual(3,len(executable(group,pid=31,epoch=20000,probe_url=PROBE)[2]))

    def test_unknown_manager_even_with_valid_compiled_emote_or_known_bytes_is_rejected(self):
        for url in ('https://foreign.invalid/a.js','file:///foreign/scripts/defaultScripts.js'):
            group=original_group();add_manager(group['script'],url,catalog()['probe'],identifier='c'*32)
            with self.subTest(url=url),self.assertRaises(NativeUIError):executable(group,pid=31,epoch=20000,probe_url=PROBE)

    def test_foreign_included_bytes_unknown_path_and_native_helper_substitution_are_rejected(self):
        for fault in ('bytes','path','helper'):
            group=original_group();row=group['script']['source']['engines'][0]['compiled']['compilations'][1]
            if fault=='bytes':row['sha256']='f'*64
            elif fault=='path':row['resourceName']=row['resourceName'].replace('phoneEmote.js','foreign-poll.js')
            else:
                row=deepcopy(row);row.update(scriptId=24,resourceName='(boundRequire)',sha256='f'*64)
                group['script']['source']['engines'][0]['compiled']['compilations'].append(row)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):executable(group,pid=31,epoch=20000,probe_url=PROBE)

    def test_missing_unassigned_nonrunning_duplicate_and_incomplete_membership_do_not_disappear(self):
        for fault in ('missing-probe','unassigned','finished','unlisted','incomplete','duplicate'):
            group=original_group();source=group['script']['source']
            if fault=='missing-probe':source['engines'].pop();source['membership']['managers'].pop()
            elif fault=='unassigned':source['membership']['managers'].append(dict(instance='c'*32,assigned=False,url='',assignedEpochMs=0,loadGeneration=0));source['membership']['revision']+=1
            elif fault=='finished':source['engines'][1].update(running=False,finished=True)
            elif fault=='unlisted':source['engines'].pop()
            elif fault=='incomplete':source['membership']=dict(complete=False)
            else:add_manager(group['script'],PROBE,catalog()['probe'],identifier='c'*32)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):executable(group,pid=31,epoch=20000,probe_url=PROBE)

    def test_probe_same_filename_or_submitted_bytes_without_original_compilation_cannot_qualify(self):
        for fault in ('foreign-url','code','compiled'):
            group=original_group();source=group['script']['source'];engine=source['engines'][1]
            if fault=='foreign-url':engine['url']=source['membership']['managers'][1]['url']='file:///tmp/overte_e2e_probe.js'
            elif fault=='code':engine['code']['sha256']='f'*64
            else:engine['compiled']['compilations']=[]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):executable(group,pid=31,epoch=20000,probe_url=PROBE)

    def test_required_modules_must_be_actual_loaded_bundled_sources(self):
        for fault in ('foreign','unloaded'):
            group=original_group();engine=group['script']['source']['engines'][0]
            root=group['rootsBefore']['source']['defaultScriptsUrl'].rstrip('/')
            engine['required'].update(sequence=1,modules=[dict(url=root+'/modules/appUi.js',loaded=True,cached=True,sequence=1,capturedEpochMs=17000)])
            if fault=='foreign':engine['required']['modules'][0]['url']='https://foreign.invalid/appUi.js'
            else:engine['required']['modules'][0]['loaded' if fault=='unloaded' else 'cached']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):executable(group,pid=31,epoch=20000,probe_url=PROBE)

    def test_successful_first_instantiation_is_valid_without_a_later_require_cache_hit(self):
        group=original_group();engine=group['script']['source']['engines'][0]
        root=group['rootsBefore']['source']['defaultScriptsUrl'].rstrip('/')
        engine['required'].update(sequence=1,modules=[dict(url=root+'/modules/appUi.js',loaded=True,cached=False,sequence=1,capturedEpochMs=17000)])
        expected=next(row for row in catalog()['files'] if row['runtimePath']=='modules/appUi.js')
        engine['compiled']['compilations'].append(dict(scriptId=24,resourceName=root+'/modules/appUi.js',compiledEpochMs=16000,
            **{key:expected[key] for key in KEYS}))
        self.assertEqual(2,len(executable(group,pid=31,epoch=20000,probe_url=PROBE)[2]))

    def test_loaded_module_ack_without_the_actual_compilation_is_rejected(self):
        group=original_group();engine=group['script']['source']['engines'][0]
        root=group['rootsBefore']['source']['defaultScriptsUrl'].rstrip('/')
        engine['required'].update(sequence=1,modules=[dict(url=root+'/modules/appUi.js',loaded=True,cached=False,sequence=1,capturedEpochMs=17000)])
        with self.assertRaises(NativeUIError):executable(group,pid=31,epoch=20000,probe_url=PROBE)

    def test_world_returns_actual_original_domain_scene_and_advancing_probe_cursor(self):
        value=probe();actual=world(value,POLICY,epoch=20000,after_sequence=9,after_epoch=15000)
        self.assertEqual(value['domain'],actual['domain']);self.assertEqual(value['scene'],actual['scene'])
        actual['domain']['id']='foreign';self.assertEqual(DOMAIN,value['domain']['id'])

    def test_stale_foreign_serverless_missing_marker_and_unready_world_fail(self):
        for fault in ('stale','domain','host','port','serverless','markers','unready','background','sequence','prior-code','empty-entities'):
            value=probe()
            if fault=='stale':value['sampleEpochMs']=18000
            elif fault=='domain':value['domain']['id']='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
            elif fault=='host':value['domain']['hostname']='foreign.invalid'
            elif fault=='port':value['scene']['url']='hifi://controlled.invalid:9999/'
            elif fault=='serverless':value['domain'].update(connected=False,serverless=True,protocol='file')
            elif fault=='markers':value['scene'].update(domainMarkers=[],domainMarkerCount=0)
            elif fault=='unready':value['scene']['ready']=False
            elif fault=='background':value['application']['foreground']=False
            elif fault=='empty-entities':value['scene']['entityCount']=0
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                world(value,POLICY,epoch=20000,after_sequence=10 if fault=='sequence' else 0,after_epoch=21000 if fault=='prior-code' else 0)

    def test_policy_disallows_remote_probe_credentials_implicit_port_and_ambiguous_markers(self):
        self.assertEqual(POLICY,policy(POLICY))
        for change in (dict(probeUrl='https://foreign.invalid/overte_e2e_probe.js'),dict(domainUrl='hifi://user@controlled.invalid:40102/'),
            dict(domainUrl='hifi://controlled.invalid/'),dict(domainId='bad'),dict(domainId='00000000-0000-0000-0000-000000000000'),
            dict(domainMarkers=['OVERTE_E2E_DOMAIN_ORIGIN']*2),dict(extra=True)):
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):policy(POLICY|change)


if __name__=='__main__':unittest.main()
