// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PicoE2eNavigationUi.h"
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQuickRenderControl>
#include <QScopedPointer>
#include <QUuid>
#include <QtTest/QTest>
#include <cstdio>
#include <thread>

#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
#include <PointerEvent.h>
#include <QDateTime>
#include <QMouseEvent>
#include <QTouchDevice>
#include <QTouchEvent>
#include <QWheelEvent>
#include <cmath>
#include <map>
// Actual source bodies and native touch state, not replacement pointer logic.
// Only the full surface's root/window/pause service boundary is controlled.
#include "actual-pointer-route.inc"
#endif

using overte::pico::e2e::NavigationUi;

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc != 2) { qFatal("the actual in-tree GOTO handler fixture is required"); }
    QQmlEngine engine;
    QObject::connect(&engine, &QQmlEngine::warnings, [&](const QList<QQmlError>& warnings) {
        for (const auto& warning : warnings) { qFatal("%s", qPrintable(warning.toString())); }
    });
    QQmlComponent audioBoundary(&engine);
    audioBoundary.setData("import QtQml 2.12\nQtObject { function playSound(value) {} }", QUrl("file:///tablet-audio-boundary.qml"));
    QScopedPointer<QObject> tabletAudio(audioBoundary.create());
    if (!tabletAudio) { qFatal("%s", qPrintable(audioBoundary.errorString())); }
    engine.rootContext()->setContextProperty("Tablet", tabletAudio.data());
    engine.rootContext()->setContextProperty("TabletEnums", QVariantMap { { "ButtonHover", 0 }, { "ButtonClick", 1 } });
    QQmlComponent component(&engine);
    QByteArray fixture = R"QML(
import QtQuick 2.12
import QtQuick.Controls 2.5
import "." as Actual
Item {
    id: root; width: 640; height: 420
    property int gotoClicks: 0
    property int backClicks: 0
    property int submissions: 0
    property bool addressShown: false
    Actual.NativeGotoButton { x: 10; y: 10; width: 100; height: 60
        onClicked: { root.gotoClicks++; root.addressShown = true; }
    }
    TextField { objectName: "tabletAddressLine"; x: 10; y: 100; width: 450; height: 60
        visible: root.addressShown; focus: false; onAccepted: root.submissions++ }
    Button { objectName: "tabletAddressBack"; x: 10; y: 180; width: 100; height: 60
        property bool buttonEnabled: false
        onClicked: root.backClicks++ }
    Item { objectName: "clipped"; x: 10; y: 270; width: 50; height: 40; clip: true
        Button { objectName: "tabletAddressForward"; x: 30; width: 100; height: 40 } }
    Button { objectName: "tabletPage.2"; x: 200; y: 270; width: 40; height: 40 }
})QML";
    component.setData(fixture, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]) + "/navigation-ui-fixture.qml"));
    auto root = qobject_cast<QQuickItem*>(component.create());
    if (!root) { qFatal("%s", qPrintable(component.errorString())); }
    QQuickRenderControl renderControl;
    QQuickWindow window(&renderControl);
    window.resize(640, 420);
    window.contentItem()->setSize(QSizeF(640, 420));
    root->setParentItem(window.contentItem());
    // The real VR tablet has a render-control window, not a shown desktop one.
    QTest::qWait(30);
#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
    OffscreenQmlSurface surface(root, &window);
#endif
    auto field = root->findChild<QQuickItem*>("tabletAddressLine");
    auto back = root->findChild<QQuickItem*>("tabletAddressBack");
    NavigationUi bridge;
    int checks { 0 }, pointerInputs { 0 };
    auto check = [&](bool ok, const char* label) {
        if (!ok) { qFatal("native Pico navigation UI failed: %s", label); }
        ++checks;
    };
    auto observe = [&] { return bridge.observe(root, &window, true); };
    auto control = [](const QJsonObject& snapshot, const QString& name) {
        for (const auto& value : snapshot["controls"].toArray()) {
            if (value.toObject()["id"] == QJsonValue(name)) { return value.toObject(); }
        }
        return QJsonObject();
    };
    auto command = [&](const QJsonObject& snapshot, const QString& name, const QString& action) {
        return QJsonObject { { "schemaVersion", 1 }, { "commandId", QUuid::createUuid().toString(QUuid::WithoutBraces) },
            { "bridgeId", snapshot["bridgeId"] }, { "generation", snapshot["generation"] },
            { "sequence", snapshot["lastCommandSequence"].toDouble() + 1 },
            { "observedElapsedMs", snapshot["elapsedMs"] }, { "controlId", name },
            { "controlToken", control(snapshot, name)["token"] }, { "action", action } };
    };
    auto pointer = [&](QQuickItem* item) {
        ++pointerInputs;
#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
        const bool delivered = sendPointerClick(item, &surface);
#else
        QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier,
            item->mapToScene(QPointF(item->width() / 2, item->height() / 2)).toPoint());
        const bool delivered = true;
#endif
        QCoreApplication::processEvents();
        return delivered; // Assertions read actual Qt state below.
    };
    auto apply = [&](const QJsonObject& value) { return bridge.apply(root, &window, true, value, pointer); };
    auto observed = observe();
    check(observed["ready"].toBool(), "actual open root is ready");
    check(!control(observed, "navigation.goto").isEmpty(), "actual GOTO button discovered");
    check(control(observed, "navigation.address").isEmpty(), "hidden editor absent");
    check(control(observed, "navigation.forward").isEmpty(), "clipped center absent");
    check(!control(observed, "tablet.page.2").isEmpty(), "actual page control discovered");
    auto go = command(observed, "navigation.goto", "activate");
    auto extra = go; extra["expectedScene"] = "not-an-input";
    check(!apply(extra)["performed"].toBool() && pointerInputs == 0, "extra feature claims rejected before input");
    check(apply(go)["performed"].toBool(), "real pointer delivered");
    check(root->property("gotoClicks").toInt() == 1 && field->isVisible(), "actual Qt button opened actual editor");
    check(!apply(go)["performed"].toBool() && pointerInputs == 1, "same command never replayed");
    observed = observe();
    auto type = command(observed, "navigation.address", "replace");
    type["text"] = "http://controlled.invalid/scene.json?location=Grüße";
    check(!apply(type)["performed"].toBool() && field->property("text").toString().isEmpty(), "unfocused edit refused");
    check(apply(command(observe(), "navigation.address", "activate"))["performed"].toBool(), "actual pointer focused editor");
    check(field->hasActiveFocus(), "real Qt editor owns focus");
    type = command(observe(), "navigation.address", "replace");
    type["text"] = QString::fromUtf8("http://controlled.invalid/scene.json?location=Grüße🌍");
    check(apply(type)["performed"].toBool(), "actual focused native edit delivered");
    check(field->property("text").toString() == type["text"].toString(), "native input changed actual editor text");
    auto submit = command(observe(), "navigation.address", "submit");
    const auto status = apply(submit);
    check(status["performed"].toBool() && root->property("submissions").toInt() == 1, "actual Return emitted one accepted signal");
    check(!status.contains("verdict") && !QJsonDocument(status).toJson().contains("controlled.invalid"), "status exposes no expected feature verdict or entered text");
    check(!control(observe(), "navigation.back")["enabled"].toBool(), "actual buttonEnabled state retained");
    check(!apply(command(observe(), "navigation.back", "activate"))["performed"].toBool(), "disabled semantic button receives no pointer");
    back->setProperty("buttonEnabled", true);
    check(apply(command(observe(), "navigation.back", "activate"))["performed"].toBool(), "enabled Back pointer delivered");
    check(root->property("backClicks").toInt() == 1, "actual Back clicked exactly once");
    auto staleControl = command(observe(), "navigation.address", "submit");
    field->setVisible(false); observe(); field->setVisible(true);
    check(!apply(staleControl)["performed"].toBool(), "disappeared/reappeared control invalidates old token");
    auto future = command(observe(), "navigation.back", "activate");
    future["observedElapsedMs"] = 9007199254740000.0;
    check(!apply(future)["performed"].toBool(), "invented future observation rejected");
    auto expired = command(observe(), "navigation.back", "activate");
    QTest::qWait(5100);
    check(!apply(expired)["performed"].toBool(), "actually expired native observation rejected");
    QQuickItem duplicate(root);
    duplicate.setObjectName("tabletAddressBack"); duplicate.setSize(QSizeF(30, 30));
    check(!observe()["ready"].toBool(), "ambiguous duplicate controls invalidate observation");
    duplicate.setVisible(false);
    check(observe()["ready"].toBool(), "hidden duplicate does not substitute visible control");
    root->setOpacity(0.0);
    check(observe()["controls"].toArray().isEmpty(), "transparent ancestor removes controls");
    root->setOpacity(1.0);
    auto previousGeneration = command(observe(), "navigation.back", "activate");
    check(!bridge.observe(root, &window, false)["ready"].toBool(), "closed tablet cannot accept input");
    check(!apply(previousGeneration)["performed"].toBool(), "close/reopen invalidates previous surface generation");
    QQuickWindow foreign;
    check(!bridge.observe(root, &foreign, true)["ready"].toBool(), "foreign window never qualifies root");
    bool foreignThreadRejected { false };
    std::thread worker([&] { foreignThreadRejected = bridge.observe(root, &window, true).isEmpty()
        && bridge.apply(root, &window, true, previousGeneration, pointer).isEmpty(); });
    worker.join();
    check(foreignThreadRejected, "foreign thread rejected before scene graph and input");
    check(root->property("submissions").toInt() == 1 && root->property("backClicks").toInt() == 1,
        "rejected commands never navigated or submitted");
#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
    const char* route = "actual in-tree VR surface pointer bodies";
#else
    const char* route = "Qt mouse primitive boundary";
#endif
    std::printf("Pico navigation input: %d actual Qt checks passed (Qt %s; %s).\n", checks, QT_VERSION_STR, route);
    // duplicate is stack-owned; detach before deleting its heap-owned parent.
    duplicate.setParentItem(nullptr); duplicate.setParent(nullptr);
    delete root;
}
