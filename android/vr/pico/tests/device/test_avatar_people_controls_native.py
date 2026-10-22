"""Original Pico Avatar QML with the original normal pointer and field bodies."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE))
from test_create_polyvox_controls_native import pointer_source,original
from test_emote_ui_native import function

class AvatarPeopleControlsNativeTests(unittest.TestCase):
    def test_original_avatar_loader_url_restore_and_actual_hit_ownership(self):
        environment=dict(os.environ)
        prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt5'+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-original-avatar-') as directory:
            stage=Path(directory);pointer_source(stage);binary=stage/'test'
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
            store+='\n'+'\n'.join(function(avatar_bookmarks,s) for s in ('AvatarBookmarks::AvatarBookmarks()', 'QVariantMap AvatarBookmarks::e2eBookmarkStorage(', 'QVariantMap AvatarBookmarks::getBookmarks(', 'QVariantMap AvatarBookmarks::getBookmarkInternal(', 'void AvatarBookmarks::addBookmarkInternal(', 'void AvatarBookmarks::removeBookmarkInternal('))
            (stage/'actual-avatar-bookmark-store.inc').write_text(store)
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
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
                '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
                '-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),str(HERE/'avatar-people-controls.cpp'),
                str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],
                check=True,timeout=90,env=environment)
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1')
            for gate in ([],['--testScript']):
                result=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(binary),*gate,str(ROOT),str(stage/'imports')],
                    text=True,timeout=30,env=environment)
            value=json.loads(result)
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

if __name__=='__main__':unittest.main()
