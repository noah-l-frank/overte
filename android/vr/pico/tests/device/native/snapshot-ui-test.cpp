// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PicoE2eNavigationUi.h"
#include <QGuiApplication>
#include <QJsonArray>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickRenderControl>
#include <QSignalSpy>
#include <QUuid>
#include <QtTest/QTest>
#include <cstdio>

#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
#include <PointerEvent.h>
#include <QDateTime>
#include <QMouseEvent>
#include <QTouchDevice>
#include <QTouchEvent>
#include <QWheelEvent>
#include <cmath>
#include <map>
#include "actual-pointer-route.inc"
#endif

using overte::pico::e2e::NavigationUi;

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc != 2) { return 2; }
    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    QQmlComponent component(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]) + "/ReviewHost.qml"));
    auto root = qobject_cast<QQuickItem*>(component.create());
    if (!root) { qFatal("%s", qPrintable(component.errorString())); }
    QQuickRenderControl render;
    QQuickWindow window(&render);
    window.resize(480, 706);
    window.contentItem()->setSize(QSizeF(480, 706));
    root->setParentItem(window.contentItem());
    auto review = root->findChild<QQuickItem*>("snapshotReview");
    if (!review) { return 3; }
    QVariant settings = QVariantMap{{"type", "snapshot"}, {"action", "captureSettings"}, {"setting", false}};
    QMetaObject::invokeMethod(review, "fromScript", Q_ARG(QVariant, settings));
    auto settle = [&] { QTest::qWait(30); render.polishItems(); QCoreApplication::processEvents(); render.polishItems(); };
    settle();
    QSignalSpy messages(review, SIGNAL(sendToScript(QVariant)));
#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
    OffscreenQmlSurface surface(root, &window);
#endif
    NavigationUi bridge;
    int checks { 0 }, pointerInputs { 0 };
    auto check = [&](bool condition, const char* description) {
        if (!condition) { qFatal("Actual Pico Snapshot input failed: %s", description); }
        ++checks;
    };
    auto observe = [&] { return bridge.observe(root, &window, true); };
    auto control = [&](const QString& id) {
        for (auto value : observe()["controls"].toArray()) {
            if (value.toObject()["id"] == QJsonValue(id)) { return value.toObject(); }
        }
        return QJsonObject();
    };
    auto command = [&](const QString& id, const QString& action) {
        const auto snapshot = observe();
        return QJsonObject{{"schemaVersion", 1}, {"commandId", QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"bridgeId", snapshot["bridgeId"]}, {"generation", snapshot["generation"]},
            {"sequence", snapshot["lastCommandSequence"].toDouble() + 1},
            {"observedElapsedMs", snapshot["elapsedMs"]}, {"controlId", id},
            {"controlToken", control(id)["token"]}, {"action", action}};
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
        settle();
        return delivered;
    };
    auto apply = [&](const QJsonObject& value) { return bridge.apply(root, &window, true, value, pointer); };
    auto activate = [&](const QString& id) {
        check(!control(id).isEmpty(), qPrintable(id));
        check(apply(command(id, "activate"))["performed"].toBool(), "ordinary pointer activation delivered");
    };
    check(observe()["ready"].toBool(), "actual hidden render-control root ready");
    check(!control("snapshot.name").isEmpty(), "actual name field discovered");
    auto text = command("snapshot.name", "replace");
    text["text"] = "parity-0123456789abcdef-panorama";
    check(!apply(text)["performed"].toBool(), "unfocused field edit refused");
    activate("snapshot.name");
    text = command("snapshot.name", "replace"); text["text"] = "parity-0123456789abcdef-panorama";
    check(apply(text)["performed"].toBool(), "actual focused IME replacement delivered");
    auto field = review->findChild<QQuickItem*>("snapshotName");
    check(field && field->property("text") == text["text"].toVariant(), "actual bounded field text changed");
    auto invalid = command("snapshot.name", "replace"); invalid["text"] = "foreign-unowned-name";
    check(!apply(invalid)["performed"].toBool() && field->property("text") == text["text"].toVariant(),
        "unowned text cannot be injected through Snapshot input");
    check(!apply(command("snapshot.name", "submit"))["performed"].toBool(), "Snapshot field cannot invoke implicit submit");
    activate("snapshot.mode");
    int selected { 0 };
    for (const auto& name : {"still", "animated", "panorama", "cubemap"}) {
        const auto choice = control(QStringLiteral("snapshot.mode.") + name);
        check(!choice.isEmpty() && choice["checked"].isBool(), "actual radio choice and checked state observed");
        selected += choice["checked"].toBool() ? 1 : 0;
    }
    check(selected == 1 && control("snapshot.mode.still")["checked"].toBool(), "one actual initial mode selected");
    const auto staleChoice = command("snapshot.mode.panorama", "activate");
    activate("snapshot.mode.panorama");
    check(control("snapshot.mode.panorama").isEmpty(), "closed popup no longer contributes choices");
    check(!apply(staleChoice)["performed"].toBool(), "previous popup command cannot replay input");
    activate("snapshot.mode");
    check(control("snapshot.mode.panorama")["checked"].toBool(), "real selected mode retained on reopen");
    activate("snapshot.mode.panorama");
    activate("snapshot.format");
    check(control("snapshot.format.png")["checked"].toBool(), "actual initial PNG choice observed");
    activate("snapshot.format.jpg");
    activate("snapshot.format");
    check(control("snapshot.format.jpg")["checked"].toBool(), "real format preference observed after pointer selection");
    activate("snapshot.format.png");
    QQuickItem foreignSibling(window.contentItem());
    foreignSibling.setObjectName("snapshotCapture"); foreignSibling.setSize(QSizeF(40, 40));
    check(observe()["ready"].toBool(), "arbitrary sibling does not become a second capture control");
    messages.clear();
    activate("snapshot.capture");
    check(messages.count() == 1, "normal button emits one actual script request");
    const auto capture = messages.at(0).at(0).toMap();
    check(capture.value("action") == "takeSnapshot" && capture.value("mode") == "panorama"
        && capture.value("filename") == "parity-0123456789abcdef-panorama", "real QML capture mode and name preserved");
    QQuickWindow foreign;
    check(!bridge.observe(root, &foreign, true)["ready"].toBool(), "foreign window refused");
    delete root;
#if defined(OVERTE_TEST_PICO_SURFACE_POINTER)
    const char* route = "actual in-tree VR surface pointer bodies";
#else
    const char* route = "Qt mouse primitive boundary";
#endif
    std::printf("Pico actual Snapshot input: %d checks passed; %d normal pointers; %s; no app capture or device acceptance.\n",
                checks, pointerInputs, route);
}
