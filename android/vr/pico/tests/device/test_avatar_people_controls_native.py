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
from test_create_polyvox_controls_native import pointer_source,original
from test_emote_ui_native import function
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
            observer='\n'.join(function(native,signature) for signature in (
                'QString token()', 'bool visible(', 'bool enabled(', 'QString controlId('))
            observer+='\nNavigationUi::NavigationUi() : _bridgeId(token()), _generation(token()) { _clock.start(); }\n'
            observer+='\n'+function(native,'QJsonObject NavigationUi::observe(')
            (stage/'actual-avatar-observe.inc').write_text('namespace overte::pico::e2e {\n'+observer+'\n}\n')
            bookmarks=(ROOT/'interface/src/Bookmarks.cpp').read_text();avatar_bookmarks=(ROOT/'interface/src/AvatarBookmarks.cpp').read_text()
            store='\n'.join(function(bookmarks,s) for s in ('void Bookmarks::insert(', 'void Bookmarks::remove(', 'bool Bookmarks::contains(', 'void Bookmarks::readFromFile(', 'void Bookmarks::persistToFile('))
            store+='\n'+'\n'.join(function(avatar_bookmarks,s) for s in ('AvatarBookmarks::AvatarBookmarks()', 'QVariantMap AvatarBookmarks::e2eBookmarkStorage(', 'QVariantMap AvatarBookmarks::e2eBookmarkLoads(', 'QVariantMap AvatarBookmarks::getBookmarks(', 'QVariantMap AvatarBookmarks::getBookmarkInternal(', 'void AvatarBookmarks::addBookmarkInternal(', 'void AvatarBookmarks::removeBookmarkInternal(', 'void AvatarBookmarks::loadBookmark(', 'void AvatarBookmarks::loadBookmarkInternal('))
            store+='\n'+'\n'.join(function((ROOT/'interface/src/avatar/MyAvatar.cpp').read_text(),signature) for signature in ('void MyAvatar::useFullAvatarURL(', 'void MyAvatar::clearWornAvatarEntities(', 'void MyAvatar::setAvatarScale('))
            (stage/'actual-avatar-bookmark-store.inc').write_text(store)
            compile_started=time.monotonic()
            subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),*definitions,*includes,'-i',str(HERE/'avatar-bookmark-store-actor.h'),'-o',str(stage/'avatar-bookmark-store-actor.moc')],check=True,timeout=min(20,max(.001,90-(time.monotonic()-compile_started))),env=environment)
            start=native.index('    } else if (controlId.startsWith("avatar.") || controlId.startsWith("people.")) {')
            end=native.index('\n    } else if (',start+10)
            branch=native[start:end].split('{',1)[1]
            (stage/'actual-avatar-input.inc').write_text(
                'QJsonObject originalAvatarInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,const QString& action,const QJsonObject& command,const std::function<bool(QQuickItem*,const QPointF&)>& pointerAt,int version=1){\n'
                'QJsonObject result{{"performed",false}},current{{"avatarPeopleControlsVersion",version}};bool delivered=false;struct {QQuickItem* item;} control{item};\n'
                +branch+'\nresult["performed"]=delivered;return result;}\n')
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
                completed=subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),*gate,str(ROOT),str(stage/'imports')],
                    text=True,capture_output=True,timeout=30,env=environment)
                label='enabled' if gate else 'disabled'
                (stage/(label+'.stdout.json')).write_text(completed.stdout)
                (stage/(label+'.stderr.txt')).write_text(completed.stderr)
                self.assertEqual(0,completed.returncode,completed.stderr[-12000:])
                result=completed.stdout
            value=json.loads(result)
            from adapters.pico4.avatar_preferences import validate as preference_validate,baseline as preference_baseline,continuity as preference_continuity
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
                self.assertEqual(command['instance'],input_row['snapshot']['instance'])
                self.assertEqual(command['generation'],input_row['snapshot']['generation'])
                self.assertEqual(1,len([row for row in controls if row['id']==command['controlId'] and row['token']==command['controlToken']]))
                actual_messages=value['normalMessageJournal'][effect['normalMessages']-1]
                self.assertTrue(actual_messages)
                self.assertTrue(all(type(message['method']) is str for message in actual_messages))
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
            self.assertTrue(value['wholeOriginalObserver'])
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
