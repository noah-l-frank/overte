"""Original Pico Avatar QML with the original normal pointer and field bodies."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import time
import base64
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(ROOT/'tests/device'))
from test_create_polyvox_controls_native import pointer_source,original,native_trace_process
from test_emote_ui_native import function
from test_assets_native_ui import navigation_source
sys.path.insert(0,str(ROOT/'tests/device/contracts/avatar'))
from native_preferences_support import prepare_ui_host,native_stage

class AvatarPeopleControlsNativeTests(unittest.TestCase):
    def test_original_avatar_loader_url_restore_and_actual_hit_ownership(self):
        environment=dict(os.environ)
        prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt5'+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
        with native_stage('pico-original-avatar-') as directory:
            stage=Path(directory);pointer_source(stage);prepare_ui_host(stage,ROOT);binary=stage/'test'
            includes=['-I'+directory,'-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src')]
            definitions=['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE']
            imports=stage/'imports/TabletScriptingInterface';imports.mkdir(parents=True)
            (imports/'qmldir').write_text('module TabletScriptingInterface\nsingleton Tablet 1.0 Tablet.qml\nsingleton TabletEnums 1.0 TabletEnums.qml\n')
            (imports/'Tablet.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject { function playSound(value) {} }\n')
            (imports/'TabletEnums.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject { readonly property int buttonClick: 1; readonly property int buttonHover: 2 }\n')
            native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
            self.assertIn('#include "../../../../../../tests/device/native/NormalAvatarPeopleControls.h"',native)
            # Compile the entire actual observer, not just isolated Avatar
            # branch fragments. Unrelated platform services are explicit seams;
            # Both the E2E and Pico observer branches compile. This does not
            # compile the full Android application or qualify other services.
            navigation_source(stage,'actual-avatar-observe.inc')
            bookmarks=(ROOT/'interface/src/Bookmarks.cpp').read_text();avatar_bookmarks=(ROOT/'interface/src/AvatarBookmarks.cpp').read_text()
            store='\n'.join(function(bookmarks,s) for s in ('void Bookmarks::insert(', 'void Bookmarks::remove(', 'bool Bookmarks::contains(', 'void Bookmarks::readFromFile(', 'void Bookmarks::persistToFile('))
            store+='\n'+'\n'.join(function(avatar_bookmarks,s) for s in ('AvatarBookmarks::AvatarBookmarks()', 'QVariantMap AvatarBookmarks::e2eBookmarkStorage(', 'QVariantMap AvatarBookmarks::e2eBookmarkLoads(', 'QVariantMap AvatarBookmarks::getBookmarks(', 'QVariantMap AvatarBookmarks::getBookmarkInternal(', 'void AvatarBookmarks::addBookmarkInternal(', 'void AvatarBookmarks::removeBookmarkInternal(', 'void AvatarBookmarks::loadBookmark(', 'void AvatarBookmarks::loadBookmarkInternal('))
            store+='\n'+'\n'.join(function((ROOT/'interface/src/avatar/MyAvatar.cpp').read_text(),signature) for signature in ('void MyAvatar::useFullAvatarURL(', 'void MyAvatar::clearWornAvatarEntities(', 'void MyAvatar::setAvatarScale('))
            (stage/'actual-avatar-bookmark-store.inc').write_text(store)
            compile_started=time.monotonic()
            subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),*definitions,*includes,'-i',str(HERE/'avatar-bookmark-store-actor.h'),'-o',str(stage/'avatar-bookmark-store-actor.moc')],check=True,timeout=min(20,max(.001,90-(time.monotonic()-compile_started))),env=environment)
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
                'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
                'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
            subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),*definitions,*includes,str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(stage/'manager.moc.cpp')],check=True,timeout=min(20,max(.001,90-(time.monotonic()-compile_started))),env=environment)
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-include','QIODevice',*definitions,*includes,
                '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
                '-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),str(HERE/'avatar-people-controls.cpp'),
                str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),
                str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(ROOT/'libraries/shared/src/SettingHelpers.cpp'),
                str(ROOT/'libraries/shared/src/SharedLogging.cpp'),str(stage/'manager.moc.cpp'),'-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],
                check=True,timeout=max(.001,90-(time.monotonic()-compile_started)),env=environment)
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1')
            for gate in ([],['--testScript']):
                command=['unshare','--user','--map-root-user','--net',str(binary),*gate,str(ROOT),str(stage/'imports')]
                if gate:
                    trace=stage/'owned-data-quiet.jsonl';environment['OVERTE_AVATAR_NATIVE_TRACE']=str(trace)
                    observed=native_trace_process(command,environment,trace)
                    completed=subprocess.CompletedProcess(command,0,observed['raw'],'')
                else:completed=subprocess.run(command,text=True,capture_output=True,timeout=30,env=environment)
                label='enabled' if gate else 'disabled'
                (stage/(label+'.stdout.json')).write_text(completed.stdout)
                (stage/(label+'.stderr.txt')).write_text(completed.stderr)
                self.assertEqual(0,completed.returncode,completed.stderr[-12000:])
                result=completed.stdout
            value=json.loads(result)
            from adapters.pico4.avatar_preferences import validate as preference_validate,baseline as preference_baseline,continuity as preference_continuity
            from adapters.pico4.avatar_favorite_effect import unchanged_preferences,original_preferences,original_bookmarks
            before_data=value['originalDataBefore'];after_data=value['originalDataAfter']
            original_preferences(before_data['preferences']['packet'],after_data['preferences']['packet'])
            original_bookmarks(before_data['bookmarks'],after_data['bookmarks'])
            self.assertEqual(before_data['settingsRawBase64'],after_data['settingsRawBase64'])
            def current_data(data,epoch):
                packet=data['preferences']['packet']
                for stamp in (packet['requestedEpochMs'],packet['capturedEpochMs'],data['bookmarks']['capturedEpochMs'],data['loads']['capturedEpochMs']):
                    self.assertGreaterEqual(epoch-stamp,0);self.assertLessEqual(epoch-stamp,1500)
                physical=packet['source']['snapshot']['writer']['physical']
                raw=base64.b64decode(data['settingsRawBase64'],validate=True)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),physical['fileSha256'])
            for data in (before_data,after_data):
                raw=base64.b64decode(data['settingsRawBase64'],validate=True)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),data['preferences']['packet']['source']['snapshot']['writer']['physical']['fileSha256'])
            trace_rows=[json.loads(line) for line in observed['traceLines']];receipts=observed['hostReceipts']
            self.assertEqual(value['originalDataQuietSamples'],len(trace_rows));self.assertEqual(len(trace_rows),len(receipts));self.assertGreaterEqual(len(trace_rows),2)
            self.assertGreaterEqual(receipts[-1]['capturedHostMonotonicNs']-receipts[0]['capturedHostMonotonicNs'],3000000000)
            self.assertGreaterEqual(trace_rows[-1]['nativeMonotonicNs']-trace_rows[0]['nativeMonotonicNs'],3000000000)
            for first,last in zip(trace_rows,trace_rows[1:]):
                self.assertGreaterEqual(last['nativeMonotonicNs']-first['nativeMonotonicNs'],0)
                self.assertGreaterEqual(last['capturedNativeEpochMs']-first['capturedNativeEpochMs'],0)
                for key in ('bookmarks','loads'):
                    self.assertGreaterEqual(last['data'][key]['capturedEpochMs']-first['data'][key]['capturedEpochMs'],0)
                    self.assertLessEqual(last['data'][key]['capturedEpochMs']-first['data'][key]['capturedEpochMs'],500)
                self.assertGreaterEqual(last['data']['preferences']['packet']['capturedEpochMs']-first['data']['preferences']['packet']['capturedEpochMs'],0)
                self.assertLessEqual(last['data']['preferences']['packet']['capturedEpochMs']-first['data']['preferences']['packet']['capturedEpochMs'],500)
                self.assertLessEqual(last['nativeMonotonicNs']-first['nativeMonotonicNs'],500000000)
            for first,last in zip(receipts,receipts[1:]):
                self.assertGreaterEqual(last['capturedHostMonotonicNs']-first['capturedHostMonotonicNs'],0)
                self.assertGreaterEqual(last['capturedHostEpochMs']-first['capturedHostEpochMs'],0)
                self.assertLessEqual(last['capturedHostMonotonicNs']-first['capturedHostMonotonicNs'],500000000)
            for index,(line,row,receipt) in enumerate(zip(observed['traceLines'],trace_rows,receipts),1):
                self.assertEqual({'avatarOriginalDataQuietVersion','sequence','nativeMonotonicNs','capturedNativeEpochMs','data'},set(row))
                self.assertIs(type(row['avatarOriginalDataQuietVersion']),int);self.assertEqual(1,row['avatarOriginalDataQuietVersion'])
                self.assertEqual({'preferences','bookmarks','loads','settingsRawBase64'},set(row['data']))
                for field in ('sequence','nativeMonotonicNs','capturedNativeEpochMs'):self.assertIs(type(row[field]),int);self.assertGreater(row[field],0)
                self.assertEqual(index,row['sequence']);self.assertEqual(index,receipt['sequence'])
                self.assertEqual(hashlib.sha256(line).hexdigest(),receipt['sourceSha256'])
                data=row['data'];packet=data['preferences']['packet'];current_data(data,row['capturedNativeEpochMs'])
                preference_validate(packet,data['preferences']['request'],value['nativeProcessId'],packet['capturedEpochMs'])
                original_preferences(before_data['preferences']['packet'],packet);original_bookmarks(before_data['bookmarks'],data['bookmarks'])
                self.assertEqual(before_data['settingsRawBase64'],data['settingsRawBase64'])
                self.assertEqual(after_data['loads']['rows'],data['loads']['rows'])
                self.assertTrue(all(event['completed'] and event['disconnected'] and not event['captureAlive'] and event['active']==0 for event in data['loads']['rows']))
                self.assertGreaterEqual(receipt['capturedHostEpochMs'],row['capturedNativeEpochMs'])
                self.assertLessEqual(receipt['capturedHostEpochMs']-row['capturedNativeEpochMs'],1500)
            # Actual earlier native originals remain historical at the later
            # measured native clock; never retime them into a fresh result.
            with self.assertRaises(AssertionError):current_data(trace_rows[0]['data'],trace_rows[-1]['capturedNativeEpochMs'])
            for key in ('bookmarks','loads'):
                self.assertGreaterEqual(trace_rows[-1]['data'][key]['capturedEpochMs']-trace_rows[0]['data'][key]['capturedEpochMs'],3000)
            self.assertGreaterEqual(trace_rows[-1]['data']['preferences']['packet']['capturedEpochMs']-trace_rows[0]['data']['preferences']['packet']['capturedEpochMs'],3000)
            effects=value['originalFavoritePreferences'];self.assertEqual(len(value['originalBookmarkLoads']),len(effects))
            previous=None
            for effect in effects:
                for side in ('before','after'):
                    original=effect[side];packet=original['packet']
                    self.assertEqual(value['nativeProcessId'],packet['processId'])
                    preference_validate(packet,original['request'],packet['processId'],packet['capturedEpochMs'])
                    preference_baseline(packet);preference_continuity(previous,packet);previous=packet
                    physical=packet['source']['snapshot']['writer']['physical']
                    disk=base64.b64decode(effect[side+'PhysicalBase64'],validate=True)
                    self.assertEqual(physical['fileSha256'],hashlib.sha256(disk).hexdigest())
                    self.assertEqual(effect['bookmarkName'],'e2e-'+'a'*32)
                self.assertGreaterEqual(effect['normalInput'],1);self.assertLessEqual(effect['normalInput'],len(value['normalInputJournal']))
                self.assertGreaterEqual(effect['normalMessages'],1);self.assertLessEqual(effect['normalMessages'],len(value['normalMessageJournal']))
                input_row=value['normalInputJournal'][effect['normalInput']-1]
                self.assertTrue(input_row['reply']['performed'])
                command=input_row['command'];controls=input_row['snapshot']['controls']
                self.assertEqual(command['bridgeId'],input_row['snapshot']['bridgeId'])
                self.assertEqual(command['generation'],input_row['snapshot']['generation'])
                self.assertEqual(1,len([row for row in controls if row['id']==command['controlId'] and row['token']==command['controlToken']]))
                actual_messages=value['normalMessageJournal'][effect['normalMessages']-1]
                self.assertTrue(actual_messages)
                self.assertTrue(all(type(message['method']) is str for message in actual_messages))
                if effect['cached']:unchanged_preferences(effect['before']['packet'],effect['after']['packet'])
                before=effect['before']['packet']['source']['snapshot'];after=effect['after']['packet']['source']['snapshot']
                self.assertEqual(before['instance'],after['instance'])
                self.assertEqual(before['mutationSequence'],after['mutationSequence'])
                for field in ('rows','encodedRows'):
                    self.assertEqual(before['cache'][field],after['cache'][field])
                    self.assertEqual(before['writer'][field],after['writer'][field])
                self.assertEqual(before['cache']['native']['handles'],after['cache']['native']['handles'])
                self.assertEqual(effect['beforePhysicalBase64'],effect['afterPhysicalBase64'])
                for field in ('fileSha256','file','rows','pathSha256'):
                    self.assertEqual(before['writer']['physical'][field],after['writer']['physical'][field])
                old=effect['beforeLoads']['rows'];new=effect['afterLoads']['rows']
                self.assertEqual(old,new[:len(old)]);self.assertEqual(len(old)+1,len(new))
                callback=new[-1]
                self.assertEqual(callback['avatarInstance'],effect['avatarInstance'])
                self.assertEqual(callback['sessionId'],after['cache']['native']['sessionId'])
                self.assertEqual(callback['nameSha256'],hashlib.sha256(effect['bookmarkName'].encode()).hexdigest())
                self.assertTrue(callback['completed'] and callback['disconnected'] and callback['ownerThreadOnly'])
                self.assertEqual(1,callback['dispatches']);self.assertEqual(0,callback['active']);self.assertFalse(callback['captureAlive'])
                self.assertGreaterEqual(callback['createdEpochMs'],effect['before']['packet']['capturedEpochMs'])
                self.assertLessEqual(callback['returnedEpochMs'],effect['after']['packet']['requestedEpochMs'])
                self.assertEqual(callback['bookmarkScale'],after['cache']['native']['live']['targetScale'])
            self.assertTrue(any(effect['cached'] for effect in effects))
            sys.path.insert(0,str(ROOT/'tests/device'))
            from adapters.pico4.avatar_people_ui import metadata
            for snapshot in value['snapshots']+value['originalSnapshots']:
                for row in snapshot['controls']:metadata(row)
            self.assertEqual(['https://controlled.invalid/owned/avatar-a.fst','qrc:/meshes/defaultAvatar_full.fst'],value['normalUrlMessages'])
            self.assertEqual(value['normalUrlMessages'],value['originalScriptAvatarCalls'])
            self.assertEqual(['uninitialized','wrong-root','moved-token','window-source','disabled','higher-overlay','outside-child','hidden-child','disabled-painted-child','clipped','negative-z'],value['counterexamples'])
            self.assertGreater(value['pointerCalls'],5)
            self.assertTrue(value['hmdActive'])
            self.assertTrue(value['wholeOriginalObserver']);self.assertTrue(value['wholeOriginalWriter'])
            self.assertEqual(['save','e2e-'+'a'*32],value['bookmarkCalls'][0])
            self.assertEqual(['delete','e2e-'+'a'*32],value['bookmarkCalls'][-1])
            self.assertTrue(1<=len(value['bookmarkCalls'][1:-1])<=8)
            self.assertTrue(all(row==['load','e2e-'+'a'*32] for row in value['bookmarkCalls'][1:-1]))
            self.assertTrue(any(abs(s-1.5)<.001 for s in value['scaleCalls']))
            self.assertEqual(1,value['scaleCalls'][-1])
            from adapters.pico4.avatar_bookmarks import storage
            physical=value['originalBookmarkStorage'];self.assertGreater(len(physical),5)
            for packet in physical:storage(packet,packet['capturedEpochMs'])
            self.assertEqual(physical[0]['bookmarks'],physical[-1]['bookmarks'])
            self.assertTrue(all('unowned' in packet['bookmarks'] for packet in physical))
            self.assertTrue(any('e2e-'+'a'*32 in packet['bookmarks'] for packet in physical))
            from adapters.pico4.avatar_bookmark_loads import loads
            work=value['originalBookmarkLoads'];self.assertGreaterEqual(len(work),2)
            for source in work:loads(source,source['capturedEpochMs'])
            self.assertGreaterEqual(value['cachedOriginalLoads'],1);self.assertGreaterEqual(value['declaredModelCompletions'],1)
            self.assertTrue(all(row['completed'] and row['disconnected'] and row['dispatches']==1 and row['active']==0
                and not row['captureAlive'] and row['ownerThreadOnly'] for row in work[-1]['rows']))

if __name__=='__main__':unittest.main()
