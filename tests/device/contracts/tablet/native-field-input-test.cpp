// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeFieldInput.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QtTest/QTest>
#include <cstdio>
#include <functional>
#include <thread>

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    QQmlEngine engine;
    QQmlComponent component(&engine);
    // Real Quick Controls native key/IME implementations; no fake field API.
    component.setData(R"QML(
import QtQuick 2.12
import QtQuick.Controls 2.5
Item {
    width: 640; height: 260
    TextField {
        id: first; objectName: "first"; x: 10; y: 10; width: 420; height: 60
        property int acceptedCount: 0
        property int changedCount: 0
        property bool divertFocus: false
        onAccepted: acceptedCount++
        onTextChanged: changedCount++
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
            if (divertFocus && event.matches(StandardKey.SelectAll)) {
                second.forceActiveFocus();
                event.accepted = true;
            }
        }
    }
    TextField { id: second; objectName: "second"; x: 10; y: 100; width: 420; height: 60 }
})QML", QUrl("file:///native-field-fixture.qml"));
    auto root = qobject_cast<QQuickItem*>(component.create());
    if (!root) { qFatal("%s", qPrintable(component.errorString())); }
    QQuickWindow window;
    window.resize(640, 260);
    root->setParentItem(window.contentItem());
    window.show();
    window.requestActivate();
    QTest::qWait(30);
    auto first = root->findChild<QQuickItem*>("first");
    auto second = root->findChild<QQuickItem*>("second");
    int checks { 0 };
    auto check = [&](bool value, const char* label) {
        if (!value) { qFatal("native field input failed: %s", label); }
        ++checks;
    };
    auto focusFirst = [&] {
        QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier,
                         first->mapToScene(QPointF(30, 30)).toPoint());
        QCoreApplication::processEvents();
        if (!first->hasActiveFocus()) { qFatal("real pointer did not focus the field"); }
    };
    check(first && second, "actual Qt fields loaded");
    focusFirst();
    check(overte::ui::replaceFocusedField(first, &window, "initial text"), "empty field accepts native IME input");
    const QString unicode = QString::fromUtf8("Grüße 🌍");
    check(overte::ui::replaceFocusedField(first, &window, unicode), "replacement inputs delivered");
    check(first->property("text").toString() == unicode, "native Select All and IME actually replace Unicode text");
    check(first->property("changedCount").toInt() >= 2, "actual native text notifications occurred");
    check(overte::ui::submitFocusedField(first, &window), "normal Return delivered");
    check(first->property("acceptedCount").toInt() == 1, "actual Qt accepted signal occurred once");
    check(overte::ui::replaceFocusedField(first, &window, QString()), "empty replacement inputs delivered");
    check(first->property("text").toString().isEmpty(), "normal clear actually removed selected text");
    check(overte::ui::replaceFocusedField(first, &window, QString(4096, QChar('a'))), "maximum bounded native text accepted");
    const auto stable = first->property("text").toString();
    for (const QString& invalid : {QString(4097, QChar('a')), QString("line\nbreak"),
                                  QString(1, QChar(0)), QString(1, QChar(0xd800)), QString(1, QChar(0xdc00))}) {
        check(!overte::ui::replaceFocusedField(first, &window, invalid), "invalid literal input rejected");
        check(first->property("text").toString() == stable, "invalid input left actual text unchanged");
    }
    check(!overte::ui::replaceFocusedField(second, &window, "private input"), "unfocused field rejected");
    check(second->property("text").toString().isEmpty(), "private input did not reach the other field");
    QQuickWindow foreignWindow;
    check(!overte::ui::replaceFocusedField(first, &foreignWindow, "private input"), "foreign surface rejected");
    first->setProperty("readOnly", true);
    check(!overte::ui::replaceFocusedField(first, &window, "private input"), "read-only field rejected");
    check(!overte::ui::submitFocusedField(first, &window), "read-only submit rejected");
    first->setProperty("readOnly", false);
    first->setEnabled(false);
    check(!overte::ui::replaceFocusedField(first, &window, "private input"), "disabled field rejected");
    first->setEnabled(true);
    root->setOpacity(0.0);
    check(!overte::ui::replaceFocusedField(first, &window, "private input"), "transparent ancestor rejected");
    root->setOpacity(1.0);
    first->setX(1000);
    check(!overte::ui::replaceFocusedField(first, &window, "private input"), "field outside actual surface rejected");
    first->setX(10);
    focusFirst();
    first->setProperty("divertFocus", true);
    check(!overte::ui::replaceFocusedField(first, &window, "private input"), "focus takeover during Select All rejected");
    check(second->hasActiveFocus() && second->property("text").toString().isEmpty(), "new focus owner received no private text");
    first->setProperty("divertFocus", false);
    focusFirst();
    bool foreignThreadAccepted { true };
    std::thread worker([&] { foreignThreadAccepted = overte::ui::replaceFocusedField(first, &window, "private input"); });
    worker.join();
    check(!foreignThreadAccepted, "non-GUI thread rejected before UI access");
    check(!overte::ui::replaceFocusedField(nullptr, &window, "private input"), "missing field rejected");
    check(!overte::ui::submitFocusedField(first, nullptr), "missing surface rejected");
    check(first->property("acceptedCount").toInt() == 1, "rejected operations never submitted the field");
    delete root;
    if (argc != 2) { qFatal("the in-tree tablet page fixture is required"); }
    QQmlComponent pages(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])));
    std::function<QQuickItem*(QQuickItem*, const QString&)> visualItem = [&](QQuickItem* item, const QString& name) -> QQuickItem* {
        if (item->objectName() == name) { return item; }
        for (auto child : item->childItems()) {
            if (auto match = visualItem(child, name)) { return match; }
        }
        return nullptr;
    };
    for (bool touch : { false, true }) {
        auto pager = qobject_cast<QQuickItem*>(pages.create());
        if (!pager) { qFatal("%s", qPrintable(pages.errorString())); }
        pager->setProperty("directTouch", touch);
        pager->setParentItem(window.contentItem());
        QCoreApplication::processEvents();
        auto page1 = visualItem(pager, "tabletPage.1");
        auto page2 = visualItem(pager, "tabletPage.2");
        check(page1 && page2, "actual repeated page handlers expose distinct native identities");
        check(pager->property("currentPage").toInt() == 0, "actual tablet pager starts on first page");
        QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier, page2->mapToScene(QPointF(30, 30)).toPoint());
        check(pager->property("currentPage").toInt() == 1, "original page handler changes actual SwipeView on native pointer");
        QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier, page1->mapToScene(QPointF(30, 30)).toPoint());
        check(pager->property("currentPage").toInt() == 0, "original first-page handler restores actual SwipeView");
        delete pager;
    }
    std::printf("Native field/page input: %d actual Qt checks passed (Qt %s).\n", checks, QT_VERSION_STR);
}
