"""Actual Emote QML and extracted original Pico pointer/scroll input bodies.

The offscreen surface hosting boundary is explicit; this is not a full native
application, Android, OpenXR runtime or actual animation qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class EmoteNativeUITests(unittest.TestCase):
    def test_actual_emote_uses_original_pico_pointer_and_surface_scroll(self):
        environment=dict(os.environ);prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
        glm=Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)
        self.assertTrue((glm/'glm/glm.hpp').is_file())
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt5'+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
        surface=(ROOT/'libraries/ui/src/ui/OffscreenQmlSurface.cpp').read_text()
        header=(ROOT/'libraries/ui/src/ui/OffscreenQmlSurface.h').read_text()
        pointer=(ROOT/'libraries/script-engine/src/PointerEvent.cpp').read_text()
        bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
        native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
        controls=(ROOT/'tests/device/native/NormalControlUi.h').read_text()
        first=header.index('    struct TouchState {');last=header.index('std::map<uint32_t, TouchState> _activeTouchPoints;',first)
        state=header[first:last+len('std::map<uint32_t, TouchState> _activeTouchPoints;')]
        hosting='''class OffscreenQmlSurface:public QObject {public:
OffscreenQmlSurface(QQuickItem* root,QQuickWindow* window):root(root),window(window){}
QQuickItem* getRootItem(){return root;} QQuickWindow* getWindow(){return window;}bool isPaused()const{return false;}
void hoverBeginEvent(const PointerEvent&,QTouchDevice&);void hoverEndEvent(const PointerEvent&,QTouchDevice&);
bool handlePointerEvent(const PointerEvent&,QTouchDevice&,bool release=false);
QQuickItem* root;QQuickWindow* window;
STATE
};'''.replace('STATE',state)
        original=[function(pointer,signature) for signature in ('PointerEvent::PointerEvent(EventType type, uint32_t id) :',
            'PointerEvent::PointerEvent(EventType type, uint32_t id, const glm::vec2& pos2D, Button button,')]
        original.append(hosting)
        original += [function(surface,signature) for signature in ('void OffscreenQmlSurface::hoverBeginEvent(',
            'void OffscreenQmlSurface::hoverEndEvent(','bool OffscreenQmlSurface::handlePointerEvent(')]
        original += [function(bridge,signature) for signature in ('bool effectiveVisible(', 'QTouchDevice& bridgeTouchDevice(',
            'bool sendPointerAt(','bool sendPointerClick(','bool sendPointerScroll(')]
        geometry=function(controls,'    static QRectF visibleRect(')+'\n'+function(controls,'    static bool ownsPoint(')
        original.append('namespace overte::e2e {class NormalControlUi {public:\n'+geometry+'\n};}\n')
        # Select this original branch by its own braces. Other feature branches
        # may be inserted before Chat without becoming part of this harness.
        branch=function(native,'    } else if (controlId.startsWith("emote.")) {').split('{',1)[1].rsplit('}',1)[0]
        original.append('''QJsonObject originalEmoteInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,
const QString& action,const QJsonObject& command,const std::function<bool(QQuickItem*)>& pointerClick,
const std::function<bool(QQuickItem*,const QPointF&,int)>& pointerScroll){
QJsonObject result{{"performed",false}},current{{"emoteControlsVersion",2}};bool delivered=false;
struct {QQuickItem* item;}control{item};
'''+branch+'\nresult["performed"]=delivered;return result;}\n')
        with tempfile.TemporaryDirectory(prefix='pico-emote-native-ui-') as directory:
            path=Path(directory);(path/'ActualEmoteInput.inc').write_text('\n'.join(original));binary=path/'test'
            built=subprocess.run(['c++','-std=c++17','-UNDEBUG','-fPIC','-DOVERTE_E2E_FEATURE_TESTS',
                '-I'+directory,'-I'+str(ROOT/'tests/device/native'),'-I'+str(ROOT/'libraries/script-engine/src'),
                '-isystem',str(glm),str(HERE/'emote-ui-native.cpp'),'-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],
                capture_output=True,text=True,timeout=60,env=environment)
            self.assertEqual(0,built.returncode,built.stderr[:6000])
            ran=subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),'--testScript',
                str(ROOT/'scripts/system/+android_phoneInterface/PhoneEmote.qml')],capture_output=True,text=True,timeout=20,
                env={**environment,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
            self.assertEqual(0,ran.returncode,ran.stdout+ran.stderr)
            print(ran.stderr.strip())


if __name__=='__main__':unittest.main()
