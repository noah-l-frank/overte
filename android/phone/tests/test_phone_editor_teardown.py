"""Exercise the actual Phone focus transition with real Qt widgets."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class EditorTeardownTest(unittest.TestCase):
    def test_world_ime_idle_keeps_owned_editor_and_expires_other_focus(self):
        source = (ROOT / 'interface/src/Application.cpp').read_text()
        marker = 'const quint64 LOSE_FOCUS_AFTER_ELAPSED_TIME'
        timer = marker + source.split(marker, 1)[1].split('            } else {', 1)[0] + '\n}'
        graphics = (ROOT / 'interface/src/Application_Graphics.cpp').read_text()
        helper = graphics.split('void Application::updatePhoneInputMethodEnabled(bool focusText) {', 1)[1].split('\n}', 1)[0]
        entities = (ROOT / 'interface/src/Application_Entities.cpp').read_text()
        setter = entities.split('        _keyboardFocusedEntity.set(id);', 1)[1].split('        auto entityScriptingInterface', 1)[0]
        fixture = r'''
#include <QApplication>
#include <QLineEdit>
#include <QHBoxLayout>
#include <QInputMethodQueryEvent>
#include <QVariantMap>
#include <QUuid>
#include <cassert>
constexpr quint64 USECS_PER_SECOND = 1000000;
static quint64 clockNow = 31 * USECS_PER_SECOND;
quint64 usecTimestampNow() { return clockNow; }
const QUuid UNKNOWN_ENTITY_ID;
struct TabletScriptingInterface {
    QVariantMap metrics {{"valid",true},{"keyboardVisible",true}};
    QVariantMap getTouchUiRuntimeMetrics() const { return metrics; }
} tablet;
struct DependencyManager {
    template<class T> static T* get() { return &tablet; }
};
struct Receiver {
    QWidget* _primaryWidget;
    quint64 _lastAcceptedKeyPress = 0;
    struct Focus { QUuid value; QUuid get() const { return value; } void set(QUuid id) { value=id; } } _keyboardFocusedEntity;
    struct Surface { bool isFocusText() const { return false; } } ui;
    struct Camera { int getProjection() const { return 0; } } _myCamera;
    bool editorOwnerAllowed = true;
    Surface* getOffscreenUI() { return &ui; }
    QRectF getPhoneWorldInputRectangle(int) const {
        if (!editorOwnerAllowed) return {};
        QInputMethodQueryEvent query(Qt::ImEnabled | Qt::ImCursorRectangle);
        QCoreApplication::sendEvent(_primaryWidget,&query);
        return query.value(Qt::ImEnabled).toBool() ? query.value(Qt::ImCursorRectangle).toRectF() : QRectF();
    }
    void updatePhoneInputMethodEnabled(bool focusText) {
HELPER
    }
    void setKeyboardFocusEntity(QUuid id) {
        _keyboardFocusedEntity.set(id);
SETTER
    }
    void idle() {
TIMER
    }
};
int main(int argc,char** argv) {
    QApplication app(argc,argv);
    QWidget window; QHBoxLayout layout(&window);
    QLineEdit editor("owned world editor"), other("other native editor");
    layout.addWidget(&editor); layout.addWidget(&other);
    window.show(); window.activateWindow(); editor.setFocus(); app.processEvents();
    assert(editor.hasFocus());
    Receiver receiver{&editor};
    auto begin=[&] {
        receiver.editorOwnerAllowed=true;
        tablet.metrics={{"valid",true},{"keyboardVisible",true}};
        editor.setFocus(); app.processEvents();
        receiver.setKeyboardFocusEntity(QUuid::createUuid());
    };
    begin(); receiver.idle();
#if defined(ANDROID_APP_PHONE_INTERFACE) && defined(USE_GL)
    assert(!receiver._keyboardFocusedEntity.get().isNull() && "Visible owned Phone IME must survive the idle deadline");
    assert(editor.testAttribute(Qt::WA_InputMethodEnabled));
#else
    assert(receiver._keyboardFocusedEntity.get().isNull()); // Preserve other clients' expiration.
#endif
    begin(); tablet.metrics["keyboardVisible"]=false; receiver.idle();
    assert(receiver._keyboardFocusedEntity.get().isNull());
    begin(); tablet.metrics["valid"]=false; receiver.idle();
    assert(receiver._keyboardFocusedEntity.get().isNull());
    begin(); receiver.editorOwnerAllowed=false; receiver.idle();
    assert(receiver._keyboardFocusedEntity.get().isNull());
    begin(); other.setFocus(); app.processEvents(); receiver.idle();
    assert(receiver._keyboardFocusedEntity.get().isNull() && other.hasFocus());
    begin(); tablet.metrics["keyboardVisible"]=false; clockNow=15*USECS_PER_SECOND; receiver.idle();
    assert(!receiver._keyboardFocusedEntity.get().isNull());
}
'''.replace('HELPER', helper).replace('SETTER', setter).replace('TIMER', timer)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
        with tempfile.TemporaryDirectory(prefix='phone-world-ime-idle-') as directory:
            p = Path(directory)
            (p / 'test.cpp').write_text(fixture)
            for name, defines in [('phone', ['-DANDROID_APP_PHONE_INTERFACE', '-DUSE_GL']), ('other', [])]:
                subprocess.run(['c++', '-std=c++17', '-fPIC', *defines, str(p / 'test.cpp'),
                                '-o', str(p / name), *flags], check=True, timeout=30)
                subprocess.run([str(p / name)], check=True, timeout=10,
                               env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})

    def test_cursor_handle_context_orders_before_qt_callback_and_resets(self):
        source = (ROOT / 'android/phone/apps/phoneInterface/src/PhoneEmbeddedWeb.cpp').read_text()
        body = source.split('JNIEnv*, jclass, jint handle) {', 1)[1].split('\n}', 1)[0]
        fixture = r'''
#include <PhoneApplicationOwner.h>
#include <QPointer>
#include <QVariant>
#include <QObject>
#include <cassert>
#include <thread>
void publishHandle(int handle) {
BODY
}
int main(int argc, char** argv) {
    publishHandle(2); // No owner exists yet.
    {
        QGuiApplication app(argc, argv);
        QObject receiver;
        int observed = 0;
        assert(!app.property("_overtePhoneNativeCursorHandle").isValid());
        std::thread androidUi([&] {
            for (int handle : {1,2,3}) {
                publishHandle(handle);
                QMetaObject::invokeMethod(&receiver, [&] {
                    assert(app.property("_overtePhoneNativeCursorHandle").toInt() == handle);
                    ++observed;
                }, Qt::BlockingQueuedConnection);
                publishHandle(0);
                QMetaObject::invokeMethod(&receiver, [&] {
                    assert(app.property("_overtePhoneNativeCursorHandle").toInt() == 0);
                    ++observed;
                }, Qt::BlockingQueuedConnection);
            }
            publishHandle(-1); publishHandle(4);
            QMetaObject::invokeMethod(&app, [&] {
                assert(app.property("_overtePhoneNativeCursorHandle").toInt() == 0);
                app.quit();
            }, Qt::QueuedConnection);
        });
        app.exec(); androidUi.join();
        assert(observed == 6);
    }
    publishHandle(1); // Destruction cannot leave a live owner.
}
'''.replace('BODY', body)
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt6Gui'], text=True))
        with tempfile.TemporaryDirectory(prefix='phone-cursor-owner-context-') as directory:
            p = Path(directory)
            (p / 'test.cpp').write_text(fixture)
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-pthread',
                            '-I' + str(ROOT / 'android/phone/apps/phoneInterface/src'),
                            str(p / 'test.cpp'), '-o', str(p / 'test'), *flags], check=True, timeout=30)
            subprocess.run([str(p / 'test')], check=True, timeout=10,
                           env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})

    def test_world_editor_queries_precede_unfocused_tablet(self):
        source = (ROOT / 'libraries/ui/src/OffscreenUi.cpp').read_text()
        marker = 'bool OffscreenUi::eventFilter(QObject* originalDestination, QEvent* event) {'
        prefix = source.split(marker, 1)[1].split("    // let the parent class do it's work", 1)[0]
        fixture = r'''
#include <QApplication>
#include <QInputMethodQueryEvent>
#include <InputMethodQueryEventWithArgument.h>
#include <QWidget>
#include <cassert>
struct WorldApplication : QApplication {
    using QApplication::QApplication;
    bool worldFocused = true;
    int worldQueries = 0;
    int positionalRequests = 0;
    bool positionalOwner = false;
    bool event(QEvent* event) override {
        if (auto* point = dynamic_cast<InputMethodQueryEventWithArgument*>(event)) {
            ++positionalRequests;
            if (worldFocused && positionalOwner && point->argument == QVariant(QPointF(20, 30))) {
                point->accept(); // The browser acknowledges asynchronously; no guessed synchronous index.
                return true;
            }
            point->ignore();
            return false;
        }
        if (worldFocused && event->type() == QEvent::InputMethodQuery) {
            ++worldQueries;
            auto* query = static_cast<QInputMethodQueryEvent*>(event);
            query->setValue(Qt::ImCursorPosition, 7);
            query->setValue(Qt::ImSurroundingText, QString("abcdefg"));
            query->accept();
            return true;
        }
        return QApplication::event(event);
    }
};
struct OffscreenUi : QObject {
    bool tabletEditor = false;
    bool filterEnabled(QObject*, QEvent*) { return true; }
    bool isFocusText() const { return tabletEditor; }
    bool eventFilter(QObject* originalDestination, QEvent* event) override {
PREFIX
        if (event->type() == QEvent::InputMethodQuery) {
            auto* query = static_cast<QInputMethodQueryEvent*>(event);
            query->setValue(Qt::ImCursorPosition, tabletEditor ? 3 : 0);
            query->accept();
            return true;
        }
        return false;
    }
};
int main(int argc, char** argv) {
    WorldApplication app(argc, argv);
    QWidget viewport;
    OffscreenUi tablet;
    viewport.installEventFilter(&tablet);
    QInputMethodQueryEvent world(Qt::ImCursorPosition | Qt::ImSurroundingText);
    QCoreApplication::sendEvent(&viewport, &world);
    assert(world.value(Qt::ImCursorPosition).toInt() == 7);
    assert(world.value(Qt::ImSurroundingText).toString() == "abcdefg");
    assert(app.worldQueries == 1);
    InputMethodQueryEventWithArgument point(Qt::ImCursorPosition, QPointF(20, 30));
    QCoreApplication::sendEvent(&viewport, &point);
    assert(!point.value(Qt::ImCursorPosition).isValid());
    assert(!point.isAccepted());
    assert(app.worldQueries == 1); // An unowned native point never reaches world coordinates.
    assert(app.positionalRequests == 1); // The explicit world mapper can reject it.
    app.positionalOwner = true;
    InputMethodQueryEventWithArgument mapped(Qt::ImCursorPosition, QPointF(20, 30));
    QCoreApplication::sendEvent(&viewport, &mapped);
    assert(mapped.isAccepted());
    assert(!mapped.value(Qt::ImCursorPosition).isValid()); // No stale selection follows the request.
    assert(app.positionalRequests == 2 && app.worldQueries == 1);
    tablet.tabletEditor = true;
    QInputMethodQueryEvent own(Qt::ImCursorPosition);
    QCoreApplication::sendEvent(&viewport, &own);
    assert(own.value(Qt::ImCursorPosition).toInt() == 3);
    assert(app.worldQueries == 1);
    assert(app.positionalRequests == 2); // A native tablet editor keeps priority.
    tablet.tabletEditor = false;
    app.worldFocused = false;
    QInputMethodQueryEvent idle(Qt::ImCursorPosition);
    QCoreApplication::sendEvent(&viewport, &idle);
    assert(idle.value(Qt::ImCursorPosition).toInt() == 0);
}
'''.replace('PREFIX', prefix)
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
        with tempfile.TemporaryDirectory(prefix='phone-world-editor-query-') as directory:
            p = Path(directory)
            (p / 'test.cpp').write_text(fixture)
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-DANDROID_APP_PHONE_INTERFACE',
                            '-I' + str(ROOT / 'libraries/shared/src'),
                            str(p / 'test.cpp'), '-o', str(p / 'test'), *flags],
                           check=True, timeout=30)
            subprocess.run([str(p / 'test')], check=True, timeout=10,
                           env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})

    def test_focus_transition_and_no_focus_stealing(self):
        source = (ROOT / 'interface/src/Application_Graphics.cpp').read_text()
        marker = 'connect(offscreenUi.data(), &OffscreenUi::focusTextChanged, _primaryWidget, [this](bool focusText) {'
        begin = source.index(marker) + len(marker)
        body = source[begin:source.index('\n    });', begin)]
        helper_marker = 'void Application::updatePhoneInputMethodEnabled(bool focusText) {'
        helper = source.split(helper_marker, 1)[1].split('\n}', 1)[0] if helper_marker in source else ''
        entities = (ROOT / 'interface/src/Application_Entities.cpp').read_text()
        setter = entities.split('        _keyboardFocusedEntity.set(id);', 1)[1].split(
            '        auto entityScriptingInterface', 1)[0]
        events = (ROOT / 'interface/src/Application_Events.cpp').read_text()
        touch = events.split('bool Application::handlePhoneWebTouchEvent(', 1)[1]
        focus_call = touch[touch.index('    const auto target ='):touch.index('    const bool captured =')]
        renderer = (ROOT / 'libraries/entities-renderer/src/EntityTreeRenderer.cpp').read_text()
        dispatch = renderer.split('QUuid EntityTreeRenderer::webTouchEvent(', 1)[1].split(
            '    if (kind == PointerEvent::Press) {', 1)[1].split(
            '    } else if (kind == PointerEvent::Release)', 1)[0]
        pan_marker = 'static qreal phoneWorldKeyboardPan('
        if pan_marker in source:
            pan = pan_marker + source.split(pan_marker, 1)[1].split('\n}', 1)[0] + '\n}'
        else:
            pan = '''static qreal phoneWorldKeyboardPan(const QRectF&, const QVariantMap&,
                qreal, bool) { return 0; }'''
        fixture = r'''
#include <QApplication>
#include <QWidget>
#include <QInputMethod>
#include <QUuid>
#include <cassert>
#include <functional>
#include <QRectF>
#include <QVariantMap>
#include <cmath>
WORLD_PAN_FN
const QUuid UNKNOWN_ENTITY_ID;
struct Receiver {
    QWidget* _primaryWidget;
    struct Focus { QUuid value; QUuid get() const { return value; } void set(QUuid id) { value = id; } } _keyboardFocusedEntity;
    struct Surface { bool text = false; bool isFocusText() const { return text; } } ui;
    Surface* getOffscreenUI() { return &ui; }
    void updatePhoneInputMethodEnabled(bool focusText) {
HELPER
    }
    void worldChanged(bool active) {
        const QUuid id = active ? QUuid::createUuid() : UNKNOWN_ENTITY_ID;
        _keyboardFocusedEntity.set(id);
SETTER
    }
    void changed(bool focusText) {
        ui.text = focusText;
BODY
    }
};
struct PointerEvent {};
struct TouchRenderer {
    QUuid id = QUuid::createUuid();
    bool focused = false;
    struct Signals {
        std::function<void()> press;
        void mousePressOnEntity(const QUuid&, const PointerEvent&) { press(); }
        void clickDownOnEntity(const QUuid&, const PointerEvent&) {}
    } signalSink;
    QUuid webTouchEvent(QEvent::Type, const QPointF&,
                       const std::function<void(const QUuid&)>& beforePress = {}) {
        const auto target = id;
        PointerEvent pointer;
        auto scripting = &signalSink;
DISPATCH
        return target;
    }
};
struct TouchApplication {
    TouchRenderer renderer;
    TouchRenderer* getEntities() { return &renderer; }
    void setKeyboardFocusEntity(const QUuid& id) {
        assert(id == renderer.id);
        renderer.focused = true;
    }
    void begin() {
        auto type = QEvent::TouchBegin;
        QPointF mapped;
FOCUS_CALL
    }
};
int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QWidget window;
    QWidget viewport(&window), other(&window);
    viewport.setFocusPolicy(Qt::StrongFocus);
    other.setFocusPolicy(Qt::StrongFocus);
    window.show(); window.activateWindow(); viewport.setFocus(); app.processEvents();
    assert(viewport.hasFocus());
    Receiver receiver { &viewport };
    int transitions = 0;
    int nativeTransitions = 0;
    QObject::connect(&app, &QGuiApplication::focusObjectChanged, [&](QObject*) { ++nativeTransitions; });
    QObject::connect(&app, &QApplication::focusChanged, [&](QWidget*, QWidget*) { ++transitions; });
    receiver.changed(true);
    assert(viewport.testAttribute(Qt::WA_InputMethodEnabled));
    assert(transitions == 0);
    receiver.changed(false);
    assert(!viewport.testAttribute(Qt::WA_InputMethodEnabled));
    assert(viewport.hasFocus());
    assert(transitions >= 2);
    assert(nativeTransitions >= 2); // The platform receives the focus-object transition.
    other.setFocus(); app.processEvents();
    transitions = 0;
    receiver.changed(false);
    assert(other.hasFocus());
    assert(transitions == 0); // Never steal focus from another window/editor.
    viewport.setFocus(); app.processEvents();
    receiver.worldChanged(true);
    assert(viewport.testAttribute(Qt::WA_InputMethodEnabled) && "World focus must enable the actual GL viewport input connection");
    receiver.changed(false);
    assert(viewport.testAttribute(Qt::WA_InputMethodEnabled)); // Closing a tablet editor retains world routing.
    receiver.worldChanged(false);
    assert(!viewport.testAttribute(Qt::WA_InputMethodEnabled));
    receiver.changed(true);
    receiver.worldChanged(true);
    receiver.worldChanged(false);
    assert(viewport.testAttribute(Qt::WA_InputMethodEnabled)); // Clearing world focus retains a real tablet editor.
    TouchApplication touch;
    bool delivered = false;
    touch.renderer.signalSink.press = [&] {
        assert(touch.renderer.focused && "First press must establish world focus before editor delivery");
        delivered = true;
    };
    touch.begin();
    assert(delivered);
    QVariantMap metrics { {"valid", true}, {"surfaceHeight", 1080},
        {"keyboardVisible", true}, {"imeInsetBottom", 775},
        {"safeInsetTop", 0}, {"density", 2.625} };
    const QRectF field(880, 415, 650, 16);
    const qreal pan = phoneWorldKeyboardPan(field, metrics, 0, false);
    assert(pan > 0 && "World editor must move above the native keyboard");
    assert(field.bottom() - pan <= 305 - 12);
    assert(field.top() - pan >= 0);
    assert(phoneWorldKeyboardPan(QRectF(880, 100, 650, 16), metrics, 0, false) == 0);
    assert(phoneWorldKeyboardPan(field, metrics, 75, true) == 75); // Preserve pointer coordinates until release.
    metrics["keyboardVisible"] = false;
    assert(phoneWorldKeyboardPan(field, metrics, pan, false) == 0); // Back restores the original projection.
    assert(phoneWorldKeyboardPan(field, metrics, 75, true) == 75);
    metrics["keyboardVisible"] = true;
    metrics["imeInsetBottom"] = 0; // A floating keyboard does not consume a bottom inset.
    assert(phoneWorldKeyboardPan(field, metrics, 0, false) == 0);
    metrics["imeInsetBottom"] = 775;
    metrics["valid"] = false;
    assert(phoneWorldKeyboardPan(field, metrics, 0, false) == 0);
    metrics["valid"] = true;
    assert(phoneWorldKeyboardPan(QRectF(), metrics, 0, false) == 0);
    assert(phoneWorldKeyboardPan(QRectF(NAN, 415, 650, 16), metrics, 0, false) == 0);
}
'''.replace('BODY', body).replace('HELPER', helper).replace('SETTER', setter).replace(
            'DISPATCH', dispatch).replace('FOCUS_CALL', focus_call).replace('WORLD_PAN_FN', pan)
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
        with tempfile.TemporaryDirectory(prefix='phone-editor-teardown-') as directory:
            p = Path(directory)
            (p / 'test.cpp').write_text(fixture)
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-DANDROID_APP_PHONE_INTERFACE', '-DUSE_GL', str(p / 'test.cpp'),
                            '-o', str(p / 'test'), *flags], check=True, timeout=30)
            subprocess.run([str(p / 'test')], check=True, timeout=10,
                           env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})


if __name__ == '__main__':
    unittest.main()
