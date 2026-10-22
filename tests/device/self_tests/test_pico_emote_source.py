"""Actual Pico bootstrap semantics with synthetic original native packets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess
import unittest

from adapters.emote_source_profile import pins, select_from_roots
from adapters.normal_ui import NativeUIError
from self_tests import test_emote_source_profile as profiles
from self_tests.test_native_feature_observation import probe_source

ROOT = Path(__file__).resolve().parents[3]


def pico_sources():
    packet, before, after = profiles.EmoteSourceProfileTests().rooted()
    root = before['source']['defaultScriptsUrl']
    engine = packet['source']['engines'][0]
    # Select from the actual Pico file bytes rather than its Phone-derived name.
    raw = (ROOT / 'scripts/system/+android_phoneInterface/phoneEmote.js').read_text().encode('utf-16-le')
    pin = next(p for p in pins() if p['sha256'] == hashlib.sha256(raw).hexdigest())
    engine['code'].update({key: pin[key] for key in ('encoding', 'codeUnits', 'sha256')})

    def compiled(identifier, resource, code):
        return dict(scriptId=identifier, resourceName=resource, compiledEpochMs=15001,
            **{key: code[key] for key in ('encoding', 'codeUnits', 'sha256')})

    packet['source']['compiledSourceVersion'] = 1
    engine['compiled'] = dict(compiledSourcesVersion=1, complete=True,
        compilations=[compiled(8, engine['url'], engine['code'])])
    bootstrap = deepcopy(engine)
    bootstrap['url'] = 'file:///~//defaultScripts.js'
    bootstrap['required'].update(instance='c' * 32, sequence=0, modules=[])
    raw = (ROOT / 'scripts/+android_picoInterface/defaultScripts.js').read_text().encode('utf-16-le')
    bootstrap['code'].update(codeUnits=len(raw) // 2, sha256=hashlib.sha256(raw).hexdigest())
    bootstrap['compiled']['compilations'] = [compiled(91, bootstrap['url'], bootstrap['code'])]
    packet['source']['engines'].append(bootstrap)
    packet['source']['membership'].update(revision=2)
    packet['source']['membership']['managers'].append(dict(instance='c' * 32, assigned=True,
        url=root + '/defaultScripts.js', loadGeneration=1, assignedEpochMs=14000))
    return packet, before, after, pin


class PicoEmoteSourceTests(unittest.TestCase):
    def test_pico_separate_emote_and_unrelated_actual_default_manager_are_distinct(self):
        packet, before, after, pin = pico_sources()
        originals = deepcopy((packet, before, after))
        selected = select_from_roots(packet, before, after, pid=31, epoch=20000)
        self.assertEqual('touch-one-shot-chooser-v1', pin['id'])
        self.assertEqual(pin, selected['profile'])
        self.assertEqual('retained', selected['profile']['chooserAfterPlay'])
        self.assertEqual(8, selected['compilation']['scriptId'])
        self.assertNotIn('managerProfile', selected)
        self.assertEqual(originals, (packet, before, after))

    def test_default_filename_cannot_hide_unknown_missing_or_incomplete_compilation(self):
        for fault in ('missing', 'incomplete', 'no-top', 'changed-top', 'future-top', 'foreign-assignment'):
            packet, before, after, _pin = pico_sources()
            bootstrap = packet['source']['engines'][1]
            if fault == 'missing': bootstrap.pop('compiled')
            elif fault == 'incomplete': bootstrap['compiled'] = dict(compiledSourcesVersion=1, complete=False)
            elif fault == 'no-top': bootstrap['compiled']['compilations'] = []
            elif fault == 'changed-top': bootstrap['compiled']['compilations'][0]['sha256'] = 'f' * 64
            elif fault == 'future-top': bootstrap['compiled']['compilations'][0]['compiledEpochMs'] = 20001
            else: packet['source']['membership']['managers'][1]['url'] = 'file:///foreign/defaultScripts.js'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                select_from_roots(packet, before, after, pid=31, epoch=20000)

    def test_an_additional_compiled_emote_origin_cannot_be_ignored_with_the_default_manager(self):
        for fault in ('same-name', 'same-bytes', 'same-name-foreign-bytes'):
            packet, before, after, _pin = pico_sources()
            emote, bootstrap = packet['source']['engines']
            duplicate = deepcopy(emote['compiled']['compilations'][0])
            duplicate.update(scriptId=92, resourceName=before['source']['defaultScriptsUrl'] + '/system/+android_phoneInterface/phoneEmote.js')
            if fault == 'same-bytes': duplicate['resourceName'] = 'qrc:/foreign/renamed.js'
            elif fault == 'same-name-foreign-bytes': duplicate['sha256'] = 'f' * 64
            bootstrap['compiled']['compilations'].append(duplicate)
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                select_from_roots(packet, before, after, pid=31, epoch=20000)

    def test_separate_pico_caller_never_borrows_the_other_manager_compilation(self):
        from adapters.native_animation_caller import selected as join
        packet, before, after, _pin = pico_sources()
        selected = select_from_roots(packet, before, after, pid=31, epoch=20000)
        member = packet['source']['membership']['managers'][0]
        caller = dict(callerVersion=2, method='overrideAnimation', sequence=1, invokedEpochMs=19000,
            manager=deepcopy(member), code=deepcopy(selected['code']), compilation=deepcopy(selected['compilation']))
        event = dict(kind='override', capturedEpochMs=19010, caller=caller)
        self.assertEqual(caller, join(event, selected, after_epoch=18999))
        caller['compilation'] = deepcopy(packet['source']['engines'][1]['compiled']['compilations'][0])
        with self.assertRaises(NativeUIError): join(event, selected)

    def test_private_probe_preserves_original_root_and_refuses_requested_paths(self):
        from fixture.serve import FixtureState
        fixture = FixtureState()
        command = dict(schemaVersion=1, commandId='ios-' + 'a' * 32, action='feature-script-roots-observe')
        self.assertEqual(command, fixture.set_client_command(command))
        for edit in (dict(root='qrc:/expected/scripts'), dict(expected=True), dict(sourceUrl='qrc:/emote.js')):
            with self.subTest(edit=edit), self.assertRaises(ValueError): fixture.set_client_command(command | edit)
        program = '''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];
const Test={featureScriptRoots:command=>{calls++;return {scriptRootsVersion:1,commandId:command.commandId,
 source:{defaultScriptsUrl:"file:///actual/configured/scripts"}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const command={schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-roots-observe"};
applyAndroidControlCommand(command);applyAndroidControlCommand(command);
if(calls!==1||files[0].name!=="feature-script-roots.json"||files[0].v.source.defaultScriptsUrl!=="file:///actual/configured/scripts")throw Error("original root");
for(const edit of [{root:"qrc:/expected/scripts"},{sourceUrl:"qrc:/emote.js"},{expected:true},{commandId:"b".repeat(32)+"\\n"}])applyAndroidControlCommand({...command,...edit});
if(calls!==1||files.length!==1)throw Error("requested root admitted");
delete Test.featureScriptRoots;
applyAndroidControlCommand({...command,commandId:"c".repeat(32)});
if(files.length!==2||files[1].v.available!==false||files[1].v.source)throw Error("missing source green");
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__': unittest.main()
