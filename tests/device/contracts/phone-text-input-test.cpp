// Exercise the product control, native accessibility editing, and real key events.
#include <QAccessible>
#include <QCoreApplication>
#include <QGuiApplication>
#include <QJsonArray>
#include <QKeyEvent>
#include <QInputMethodEvent>
#include <QLocale>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickWindow>
#include <cassert>
#include "PhoneAccessibilityTree.h"
#include "PhoneTextInputFixture.h"

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    QAccessible::setActive(true);
    assert(argc == 2);
    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[1]) + "/interface/resources/qml");
    QQmlComponent component(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])
        + "/tests/device/fixture/ControlledTextInput.qml"));
    auto panel = qobject_cast<QQuickItem*>(component.create());
    if (!panel) { qWarning() << component.errors(); }
    assert(panel);
    QQuickWindow window;
    window.resize(640, 360);
    panel->setParentItem(window.contentItem());
    window.show();
    QCoreApplication::processEvents();
    PhoneTextInputFixture fixture;
    assert(fixture.focus(panel));
    QCoreApplication::processEvents();
    const auto empty = fixture.snapshot(app.inputMethod()->isVisible());
    assert(empty.value("value").toString().isEmpty());
    assert(empty.value("focused").toBool());
    const auto beforeSubmit = empty.value("submittedCount").toInt();
    PhoneAccessibilityTree bridge;
    const auto nodes = bridge.snapshot(panel, QSize(640, 360)).value("nodes").toArray();
    int editor = -1;
    for (auto node : nodes) {
        if (node.toObject().value("semanticId").toString() == "controlled.text") {
            assert(editor == -1);
            editor = node.toObject().value("id").toInt();
        }
    }
    assert(editor != -1);
    assert(bridge.action(editor, "set-text", QString::fromUtf8("Overte E2E äöüX")));
    assert(fixture.snapshot(false).value("value").toString() == QString::fromUtf8("Overte E2E äöüX"));
    QKeyEvent backspace(QEvent::KeyPress, Qt::Key_Backspace, Qt::NoModifier);
    QCoreApplication::sendEvent(&window, &backspace);
    QKeyEvent backspaceUp(QEvent::KeyRelease, Qt::Key_Backspace, Qt::NoModifier);
    QCoreApplication::sendEvent(&window, &backspaceUp);
    QKeyEvent enter(QEvent::KeyPress, Qt::Key_Return, Qt::NoModifier);
    QCoreApplication::sendEvent(&window, &enter);
    QKeyEvent enterUp(QEvent::KeyRelease, Qt::Key_Return, Qt::NoModifier);
    QCoreApplication::sendEvent(&window, &enterUp);
    const auto edited = fixture.snapshot(false);
    assert(edited.value("value").toString() == QString::fromUtf8("Overte E2E äöü"));
    assert(edited.value("submittedCount").toInt() == beforeSubmit + 1);
    assert(fixture.dismiss());
    assert(!fixture.snapshot(false).value("focused").toBool());
    assert(!panel->isVisible());
    delete panel;
    assert(fixture.snapshot(false).isEmpty());
    assert(!fixture.dismiss());

    // The wearable editor uses this real shared control with a separate
    // realFrom/realTo range. Exercise an actual IME commit and Return.
    for (const char* localeName : { "en_US", "de_DE" }) {
        QLocale::setDefault(QLocale(localeName));
        QQmlComponent spinComponent(&engine);
        spinComponent.setData(R"(
            import QtQuick 2.7
            import controlsUit 1.0 as Controls
            Controls.SpinBox {
                width: 250
                realFrom: -10
                realTo: 10
                realStepSize: 0.01
                realValue: 0.01
            }
        )", QUrl());
        auto spin = qobject_cast<QQuickItem*>(spinComponent.create());
        if (!spin) { qWarning() << spinComponent.errors(); }
        assert(spin);
        spin->setParentItem(window.contentItem());
        auto numericInput = qobject_cast<QQuickItem*>(spin->property("contentItem").value<QObject*>());
        assert(numericInput);
        numericInput->forceActiveFocus();
        QCoreApplication::processEvents();
        QInputMethodEvent numericCommit;
        numericCommit.setCommitString("0.50", -numericInput->property("cursorPosition").toInt(),
                                     numericInput->property("text").toString().size());
        QCoreApplication::sendEvent(numericInput, &numericCommit);
        assert(numericInput->property("text").toString() == "0.50");
        QCoreApplication::sendEvent(&window, &enter);
        QCoreApplication::sendEvent(&window, &enterUp);
        QCoreApplication::processEvents();
        assert(qAbs(spin->property("realValue").toDouble() - 0.5) < 0.00001);
        for (const auto& input : { QString("12.50"), QString("-12.50") }) {
            QInputMethodEvent boundaryCommit;
            boundaryCommit.setCommitString(input, -numericInput->property("cursorPosition").toInt(),
                                          numericInput->property("text").toString().size());
            QCoreApplication::sendEvent(numericInput, &boundaryCommit);
            QCoreApplication::sendEvent(&window, &enter);
            QCoreApplication::sendEvent(&window, &enterUp);
            QCoreApplication::processEvents();
            assert(qAbs(spin->property("realValue").toDouble() - (input.startsWith('-') ? -10.0 : 10.0)) < 0.00001);
        }
        delete spin;
    }
}
