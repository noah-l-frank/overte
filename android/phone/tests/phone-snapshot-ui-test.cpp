// SPDX-License-Identifier: Apache-2.0
// Actual SNAP review through the production Android accessibility tree/actions.
#include <QBitArray>
#include <QAccessible>
#include <QEventLoop>
#include <QGuiApplication>
#include <QJsonArray>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickRenderControl>
#include <QQuickWindow>
#include <QSignalSpy>
#include <QTimer>
#include <cstdio>
#include "PhoneAccessibilityTree.h"

static void polish(QQuickRenderControl& control) {
    QEventLoop loop;
    QTimer::singleShot(25, &loop, &QEventLoop::quit);
    loop.exec();
    // The actual offscreen host polishes Controls layouts before rendering.
    // Merely waiting on a hidden QQuickWindow omits that owning host step.
    control.polishItems();
    QCoreApplication::processEvents();
    control.polishItems();
}

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    QAccessible::setActive(true);
    if (argc != 2) { return 2; }
    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    QQmlComponent component(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]) + "/ReviewHost.qml"));
    auto root = qobject_cast<QQuickItem*>(component.create());
    if (!root) { qWarning() << component.errors(); return 3; }
    QQuickRenderControl control;
    QQuickWindow window(&control);
    auto settle = [&] { polish(control); };
    window.setGeometry(0, 0, 480, 900);
    root->setParentItem(window.contentItem());
    // Keep the window hidden, matching Phone's render-control accessibility.
    auto review = root->findChild<QQuickItem*>("snapshotReview");
    if (!review) { return 4; }
    QSignalSpy messages(review, SIGNAL(sendToScript(QVariant)));
    QVariant settings = QVariantMap{{"type", "snapshot"}, {"action", "captureSettings"}, {"setting", false}};
    QMetaObject::invokeMethod(review, "fromScript", Q_ARG(QVariant, settings));
    settle(); messages.clear();
    PhoneAccessibilityTree bridge;
    QQmlComponent siblingFactory(&engine);
    siblingFactory.setData("import QtQuick 2.7\nItem {width:20; height:20; objectName:\"foreign-sibling\";"
        " Accessible.role:Accessible.Button; Accessible.name:\"Foreign sibling\"}", QUrl());
    auto sibling = qobject_cast<QQuickItem*>(siblingFactory.create());
    if (!sibling) { return 16; }
    sibling->setParentItem(window.contentItem());
    auto node = [&](const QString& name) {
        for (auto value : bridge.snapshot(root, QSize(480, 900)).value("nodes").toArray()) {
            auto row = value.toObject();
            if (row.value("semanticId").toString() == name) { return row; }
        }
        return QJsonObject();
    };
    if (!node("foreign-sibling").isEmpty()) { return 17; }
    auto press = [&](const QString& name) {
        const auto row = node(name);
        if (row.isEmpty() || !row.value("clickable").toBool()
                || !bridge.action(row.value("id").toInt(), "press")) {
            std::fprintf(stderr, "Actual Snapshot control is not pressable: %s present=%d clickable=%d\n",
                qPrintable(name), !row.isEmpty(), row.value("clickable").toBool());
            auto item = review->findChild<QQuickItem*>(name);
            auto accessible = item ? QAccessible::queryAccessibleInterface(item) : nullptr;
            if (accessible) {
                std::fprintf(stderr, "Actual role=%d actions=%s loaded=%d enabled=%d\n", int(accessible->role()),
                    qPrintable(accessible->actionInterface() ? accessible->actionInterface()->actionNames().join(',') : QString()),
                    review->property("captureSettingsLoaded").toBool(), item->isEnabled());
            }
            return false;
        }
        settle();
        return true;
    };
    if (!press("snapshotMode")) { return 5; }
    int checked = 0;
    for (const auto& value : {"still", "animated", "panorama", "cubemap"}) {
        const auto row = node(QStringLiteral("snapshotMode.option.") + value);
        if (row.isEmpty() || !row.value("checkable").toBool()) {
            std::fprintf(stderr, "Actual popup choice unavailable: %s present=%d checkable=%d\n",
                value, !row.isEmpty(), row.value("checkable").toBool());
            for (auto layer : window.contentItem()->childItems()) {
                std::fprintf(stderr, "Window child %s visible=%d size=%.0fx%.0f\n",
                    layer->metaObject()->className(), layer->isVisible(), layer->width(), layer->height());
            }
            return 6;
        }
        checked += row.value("checked").toBool() ? 1 : 0;
    }
    if (checked != 1 || !node("snapshotMode.option.still").value("checked").toBool()) { return 7; }
    const int oldOptionId = node("snapshotMode.option.panorama").value("id").toInt(-1);
    if (!press("snapshotMode.option.panorama")) { return 8; }
    if (!node("snapshotMode.option.panorama").isEmpty()
            || bridge.action(oldOptionId, "press")) { return 18; }
    if (!press("snapshotMode")) { return 8; }
    if (!node("snapshotMode.option.panorama").value("checked").toBool()) { return 9; }
    if (!press("snapshotMode.option.panorama") || !press("snapshotFormat")) { return 10; }
    if (!node("snapshotFormat.option.png").value("checked").toBool()) { return 11; }
    if (!press("snapshotFormat.option.jpg")) { return 12; }
    const auto field = node("snapshotName");
    if (!bridge.action(field.value("id").toInt(-1), "set-text", "Photo")) { return 13; }
    messages.clear();
    if (!press("snapshotCapture") || messages.count() != 1) { return 14; }
    const auto capture = messages.at(0).at(0).toMap();
    if (capture.value("action") != "takeSnapshot" || capture.value("mode") != "panorama"
            || capture.value("filename") != "Photo") { return 15; }
    QQuickRenderControl foreignControl;
    QQuickWindow foreignWindow(&foreignControl);
    foreignWindow.setGeometry(0, 0, 480, 900);
    auto foreignRoot = qobject_cast<QQuickItem*>(component.create());
    if (!foreignRoot) { return 19; }
    foreignRoot->setParentItem(foreignWindow.contentItem());
    auto foreignReview = foreignRoot->findChild<QQuickItem*>("snapshotReview");
    QMetaObject::invokeMethod(foreignReview, "fromScript", Q_ARG(QVariant, settings));
    auto foreignMode = foreignReview->findChild<QQuickItem*>("snapshotMode");
    auto foreignAccessible = QAccessible::queryAccessibleInterface(foreignMode);
    if (!foreignAccessible || !foreignAccessible->actionInterface()) { return 20; }
    foreignAccessible->actionInterface()->doAction(QAccessibleActionInterface::pressAction());
    polish(foreignControl);
    PhoneAccessibilityTree foreignBridge;
    bool foreignChoiceVisible = false;
    for (auto value : foreignBridge.snapshot(foreignRoot, QSize(480, 900)).value("nodes").toArray()) {
        foreignChoiceVisible |= value.toObject().value("semanticId").toString() == "snapshotMode.option.still";
    }
    if (!foreignChoiceVisible) { return 22; }
    if (!node("snapshotMode.option.still").isEmpty()) { return 21; }
    delete foreignRoot;
    delete sibling;
    delete root;
    std::puts("Actual Snapshot native popup choices, checked state, field and capture input passed.");
}
