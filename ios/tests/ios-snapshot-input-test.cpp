// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSNormalUiInput.h"
#include <cmath>
#include <QGuiApplication>
#include <QJsonArray>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickRenderControl>
#include <QSignalSpy>
#include <QUuid>
#include <QtTest/QTest>
#include <cstdio>

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc != 2) { return 2; }
    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    QQmlComponent component(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]) + "/ReviewHost.qml"));
    auto hud = qobject_cast<QQuickItem*>(component.create());
    if (!hud) { qFatal("%s", qPrintable(component.errorString())); }
    auto tablet = hud->findChild<QQuickItem*>("nestedTablet");
    auto review = hud->findChild<QQuickItem*>("snapshotReview");
    auto address = hud->findChild<QQuickItem*>("PhoneAddressField");
    if (!tablet || !review || !address) { return 3; }
    QQuickRenderControl render;
    QQuickWindow window(&render);
    window.resize(480, 900); window.contentItem()->setSize(QSizeF(480, 900));
    hud->setParentItem(window.contentItem());
    QVariant settings = QVariantMap{{"type", "snapshot"}, {"action", "captureSettings"}, {"setting", false}};
    QMetaObject::invokeMethod(review, "fromScript", Q_ARG(QVariant, settings));
    auto settle = [&] { QTest::qWait(30); render.polishItems(); QCoreApplication::processEvents(); render.polishItems(); };
    settle();
    overte::ios::NormalUiInput input;
    int checks { 0 };
    auto check = [&](bool value, const char* label) {
        if (!value) { qFatal("Actual iOS Snapshot input failed: %s", label); }
        ++checks;
    };
    auto observe = [&] { return input.observe(hud, tablet, true); };
    auto control = [&](const QString& id) {
        for (auto value : observe()["controls"].toArray()) {
            if (value.toObject()["id"] == QJsonValue(id)) { return value.toObject(); }
        }
        return QJsonObject();
    };
    auto press = [&](const QString& id) {
        const auto row = control(id);
        check(!row.isEmpty(), qPrintable(id));
        check(input.press(id, row["token"].toString()), "actual Qt pointer delivered");
        settle();
    };
    auto edit = [&](const QString& operation, const QString& token, const QString& text = QString()) {
        const auto snapshot = observe();
        QJsonObject command{{"schemaVersion", 1}, {"commandId", QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"instance", snapshot["instance"]}, {"sequence", snapshot["lastSequence"].toDouble() + 1},
            {"observedElapsedMs", snapshot["elapsedMs"]}, {"fieldToken", token}, {"operation", operation}};
        if (operation == "replace") { command["text"] = text; }
        return input.edit(command);
    };
    check(observe()["ready"].toBool(), "actual nested tablet and HUD roots ready");
    auto name = control("snapshot.name");
    check(!name.isEmpty(), "actual nested Snapshot field observed");
    const auto prefix = QStringLiteral("parity-0123456789abcdef-panorama");
    check(!edit("replace", name["token"].toString(), prefix)["performed"].toBool(), "unfocused name edit refused");
    press("snapshot.name");
    name = control("snapshot.name");
    check(edit("replace", name["token"].toString(), prefix)["performed"].toBool(), "actual focused native name input delivered");
    auto field = review->findChild<QQuickItem*>("snapshotName");
    check(field && field->property("text").toString() == prefix, "real field contains the owned prefix");
    check(!edit("replace", name["token"].toString(), "foreign-name")["performed"].toBool()
        && field->property("text").toString() == prefix, "unowned names cannot use the closed field transport");
    check(!edit("submit", name["token"].toString())["performed"].toBool(), "Snapshot name cannot implicitly submit a feature");
    const auto frame = name["frame"].toObject();
    const auto projected = input.projectedFrame("snapshot.name", name["token"].toString(),
        QRectF(0, 0, 240, 450), QRectF(0, 10, 240, 440));
    check(!projected.isEmpty() && std::abs(projected.x() - frame["x"].toDouble() / 2) < 0.01
        && std::abs(projected.width() - frame["width"].toDouble() / 2) < 0.01,
        "actual nested window geometry projects to native safe bounds");
    press("snapshot.mode");
    int selected { 0 };
    for (const auto& mode : {"still", "animated", "panorama", "cubemap"}) {
        const auto row = control(QStringLiteral("snapshot.mode.") + mode);
        check(!row.isEmpty() && row["checked"].isBool(), "actual owned popup radio state observed");
        selected += row["checked"].toBool() ? 1 : 0;
    }
    check(selected == 1 && control("snapshot.mode.still")["checked"].toBool(), "one actual initial mode selected");
    const auto old = control("snapshot.mode.panorama");
    press("snapshot.mode.panorama");
    check(control("snapshot.mode.panorama").isEmpty()
        && !input.press("snapshot.mode.panorama", old["token"].toString()), "closed popup token cannot adopt a new control");
    press("snapshot.mode");
    check(control("snapshot.mode.panorama")["checked"].toBool(), "real mode selection retained after reopening");
    press("snapshot.mode.panorama");
    press("snapshot.format");
    check(control("snapshot.format.png")["checked"].toBool(), "actual initial format selected");
    press("snapshot.format.jpg");
    press("snapshot.format");
    check(control("snapshot.format.jpg")["checked"].toBool(), "actual selected format observed");
    press("snapshot.format.png");
    const auto previousName = control("snapshot.name");
    address->setVisible(true); address->forceActiveFocus(); settle();
    const auto modal = observe();
    bool snapshotsCovered = true;
    for (auto row : modal["controls"].toArray()) {
        snapshotsCovered &= !row.toObject()["id"].toString().startsWith("snapshot.");
    }
    check(snapshotsCovered, "address modal removes all underlying Snapshot controls");
    check(!edit("replace", previousName["token"].toString(), prefix)["performed"].toBool(),
        "modal invalidates old Snapshot field input");
    address->setVisible(false); settle();
    QSignalSpy messages(review, SIGNAL(sendToScript(QVariant)));
    press("snapshot.capture");
    check(messages.count() == 1, "ordinary capture button emitted one real request");
    const auto capture = messages.at(0).at(0).toMap();
    check(capture.value("action") == "takeSnapshot" && capture.value("mode") == "panorama"
        && capture.value("filename") == prefix, "real QML capture mode and name preserved");
    // A different popup shares this window, but is not owned by the tablet.
    auto foreign = hud->findChild<QQuickItem*>("foreignCombo");
    QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier,
        foreign->mapToScene(QPointF(foreign->width() / 2, foreign->height() / 2)).toPoint());
    settle();
    auto popupObject = foreign->property("popup").value<QObject*>();
    check(popupObject && popupObject->property("visible").toBool(), "foreign popup actually opened for the ownership negative");
    check(control("snapshot.mode.still").isEmpty(), "foreign same-window popup cannot impersonate tablet radio controls");
    delete hud;
    std::printf("iOS actual Snapshot input: %d Qt checks passed; UIKit/IPA/device qualification not performed.\n", checks);
}
