// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSNormalUiInput.h"
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickRenderControl>
#include <QUuid>
#include <QtTest/QTest>
#include <cstdio>
#include <thread>

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    QQmlEngine engine;
    QQmlComponent component(&engine);
    component.setData(R"QML(
import QtQuick 2.12
import QtQuick.Controls 2.5
Item {
 id: root; width: 640; height: 360
 property bool addressShown: false
 property int openings: 0; property int submissions: 0; property int cancellations: 0
 property int tablets: 0
 Button { x: 10; y: 10; width: 110; height: 60; text: "GO TO"
   onClicked: { root.openings++; root.addressShown = true; } }
 Button { objectName: "OverteTabletOpen"; x: 10; y: 280; width: 110; height: 60
   onClicked: root.tablets++ }
 TextField { objectName: "PhoneAddressField"; x: 10; y: 100; width: 430; height: 60
   visible: root.addressShown; onAccepted: root.submissions++ }
 Button { objectName: "PhoneAddressGoButton"; x: 10; y: 190; width: 110; height: 60
   visible: root.addressShown; onClicked: { root.submissions++; root.addressShown = false; } }
 Button { objectName: "PhoneAddressCancelButton"; x: 140; y: 190; width: 110; height: 60
   visible: root.addressShown; onClicked: { root.cancellations++; root.addressShown = false; } }
})QML", QUrl("file:///ios-hud-input-fixture.qml"));
    auto hud = qobject_cast<QQuickItem*>(component.create());
    if (!hud) { qFatal("%s", qPrintable(component.errorString())); }
    component.setData(R"QML(
import QtQuick 2.12
import QtQuick.Controls 2.5
Item {
 id: root; width: 640; height: 360
 property int backs: 0; property int forwards: 0; property int places: 0; property int closes: 0
 Button { x: 10; y: 10; width: 120; height: 60; text: "PLACES"; onClicked: root.places++ }
 Button { objectName: "goBack"; x: 10; y: 100; width: 110; height: 60; onClicked: root.backs++ }
 Button { objectName: "goForward"; x: 140; y: 100; width: 110; height: 60; onClicked: root.forwards++ }
 Button { objectName: "nav.home"; x: 270; y: 100; width: 110; height: 60 }
 Button { objectName: "tabletPage.2"; x: 10; y: 220; width: 50; height: 50 }
 Button { objectName: "nav.close"; x: 400; y: 100; width: 110; height: 60; onClicked: root.closes++ }
})QML", QUrl("file:///ios-tablet-input-fixture.qml"));
    auto tablet = qobject_cast<QQuickItem*>(component.create());
    if (!tablet) { qFatal("%s", qPrintable(component.errorString())); }
    QQuickRenderControl hudRender, tabletRender;
    QQuickWindow hudWindow(&hudRender), tabletWindow(&tabletRender);
    hudWindow.resize(640, 360); tabletWindow.resize(640, 360);
    hudWindow.contentItem()->setSize(QSizeF(640, 360));
    tabletWindow.contentItem()->setSize(QSizeF(640, 360));
    hud->setParentItem(hudWindow.contentItem()); tablet->setParentItem(tabletWindow.contentItem());
    QTest::qWait(30);
    overte::ios::NormalUiInput input;
    bool tabletShown { false };
    int checks { 0 };
    auto check = [&](bool ok, const char* message) {
        if (!ok) { qFatal("iOS normal Qt input failed: %s", message); }
        ++checks;
    };
    auto snapshot = [&] { return input.observe(hud, tablet, tabletShown); };
    auto find = [](const QJsonObject& value, const QString& id) {
        for (const auto& row : value["controls"].toArray()) {
            if (row.toObject()["id"] == QJsonValue(id)) { return row.toObject(); }
        }
        return QJsonObject();
    };
    auto press = [&](const QString& id) {
        return input.press(id, find(snapshot(), id)["token"].toString());
    };
    auto edit = [&](const QString& operation) {
        const auto observed = snapshot();
        return QJsonObject { { "schemaVersion", 1 }, { "commandId", QUuid::createUuid().toString(QUuid::WithoutBraces) },
            { "instance", observed["instance"] }, { "sequence", observed["lastSequence"].toDouble() + 1 },
            { "observedElapsedMs", observed["elapsedMs"] },
            { "fieldToken", find(observed, "address.field")["token"] }, { "operation", operation } };
    };
    const auto envelope = [](const QString& operation) {
        return QJsonObject { { "schemaVersion", 1 },
            { "commandId", "ios-" + QUuid::createUuid().toString(QUuid::Id128) },
            { "action", "normal-ui-input" }, { "operation", operation } };
    };
    check(snapshot()["ready"].toBool(), "actual HUD root observed");
    const auto observationRequest = envelope("observe");
    check(input.request(observationRequest)["commandId"] == observationRequest["commandId"],
        "actual producer preserves the observation request nonce");
    check(input.request(observationRequest)["observation"].toObject()["ready"].toBool(),
        "actual request samples live GUI state without an expected feature result");
    auto injected = observationRequest; injected["navigationPassed"] = true;
    check(!input.validRequest(injected) && input.request(injected).isEmpty(), "request cannot supply its own feature verdict");
    injected = observationRequest; injected["schemaVersion"] = true;
    check(!input.validRequest(injected), "boolean is not a numeric request schema");
    injected = observationRequest; injected["commandId"] = "foreign";
    check(!input.validRequest(injected), "foreign outer nonce rejected");
    injected = observationRequest; injected["operation"] = "navigate";
    check(!input.validRequest(injected), "request cannot invoke a navigation service");
    const auto gotoToken = find(snapshot(), "hud.goto")["token"].toString();
    check(input.projectedFrame("hud.goto", gotoToken, QRectF(0, 0, 1280, 720), QRectF(0, 0, 1280, 720))
        == QRectF(20, 20, 220, 120), "native frame scales actual Qt window coordinates");
    check(input.projectedFrame("hud.goto", gotoToken, QRectF(0, 0, 640, 360), QRectF(20, 20, 600, 320))
        == QRectF(20, 20, 100, 50), "native projection intersects safe bounds without adding duplicate inset");
    check(input.projectedFrame("hud.goto", gotoToken, QRectF(), QRectF()).isEmpty(), "missing native frame cannot invent a hit target");
    const auto tabletOpenToken = find(snapshot(), "hud.tablet")["token"].toString();
    check(!input.projectedFrame("hud.tablet", tabletOpenToken, QRectF(0, 0, 640, 360), QRectF(0, 0, 640, 360))
        .intersects(input.projectedFrame("hud.goto", gotoToken, QRectF(0, 0, 640, 360), QRectF(0, 0, 640, 360))),
        "native Open targets actual separate widget instead of covering Go To");
    check(press("hud.tablet") && hud->property("tablets").toInt() == 1, "actual Qt tablet button receives normal input");
    check(find(snapshot(), "places.back").isEmpty(), "closed separate tablet is excluded");
    check(press("hud.goto"), "actual HUD pointer delivered");
    check(hud->property("openings").toInt() == 1, "actual native Qt button opened the editor");
    check(find(snapshot(), "hud.goto").isEmpty(), "modal field covers underlying toolbar");
    check(find(snapshot(), "hud.tablet").isEmpty(), "modal field removes underlying tablet-open hit target");
    auto field = hud->findChild<QQuickItem*>("PhoneAddressField");
    auto beforeFocus = edit("replace"); beforeFocus["text"] = "private input";
    check(!input.edit(beforeFocus)["performed"].toBool(), "unfocused field receives no text");
    check(field->property("text").toString().isEmpty(), "refused edit left actual editor empty");
    check(press("address.field") && field->hasActiveFocus(), "normal pointer owns real editor focus");
    auto editRequest = envelope("edit");
    auto requestInput = edit("replace"); requestInput["text"] = "ordinary text";
    editRequest["input"] = requestInput;
    const auto requestStatus = input.request(editRequest);
    check(requestStatus["status"].toObject()["performed"].toBool()
        && field->property("text").toString() == "ordinary text", "actual request dispatches native focused-field input");
    check(requestStatus["commandId"] == editRequest["commandId"]
        && requestStatus["status"].toObject()["commandId"] == requestInput["commandId"],
        "outer transport and inner native input nonces remain distinct");
    check(!input.request(editRequest)["status"].toObject()["performed"].toBool(), "duplicate request cannot replay text input");
    for (const auto& violation : { QString("sequence"), QString("instance"), QString("operation"),
            QString("text"), QString("fieldToken"), QString("commandId"), QString("extra"), QString("oversize") }) {
        auto invalid = requestInput;
        if (violation == "sequence") { invalid["sequence"] = true; }
        else if (violation == "instance") { invalid["instance"] = "foreign"; }
        else if (violation == "operation") { invalid["operation"] = "setDestination"; }
        else if (violation == "text") { invalid["text"] = "injected\ncommand"; }
        else if (violation == "fieldToken") { invalid["fieldToken"] = "foreign"; }
        else if (violation == "commandId") { invalid["commandId"] = "foreign"; }
        else if (violation == "oversize") { invalid["text"] = QString(4097, 'x'); }
        else { invalid["featurePassed"] = true; }
        injected = editRequest; injected["input"] = invalid;
        check(!input.validRequest(injected) && input.request(injected).isEmpty(), "malformed request rejected before GUI input");
    }
    auto wrongInstance = edit("replace"); wrongInstance["text"] = "foreign";
    wrongInstance["instance"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
    check(!input.edit(wrongInstance)["performed"].toBool(), "different process input instance rejected");
    auto future = edit("submit"); future["observedElapsedMs"] = snapshot()["elapsedMs"].toDouble() + 60000;
    check(!input.edit(future)["performed"].toBool(), "future native capture cannot qualify input");
    auto replace = edit("replace"); replace["text"] = QString::fromUtf8("http://controlled.invalid/scene.json?Grüße🌍");
    const auto typed = input.edit(replace);
    check(typed["performed"].toBool(), "native IME input delivered");
    check(field->property("text").toString() == replace["text"].toString(), "actual Unicode editor value changed");
    check(!QJsonDocument(typed).toJson().contains("controlled.invalid"), "delivery status contains no private field value");
    check(!input.edit(replace)["performed"].toBool(), "same native edit sequence never replays");
    auto malformed = edit("replace"); malformed["text"] = "bad\ninput";
    check(!input.edit(malformed)["performed"].toBool(), "control text rejected by actual shared editor input");
    check(field->property("text").toString() == replace["text"].toString(), "invalid edit did not change native text");
    auto extra = edit("submit"); extra["navigationPassed"] = true;
    check(!input.edit(extra)["performed"].toBool(), "feature verdict is not an input argument");
    check(input.edit(edit("submit"))["performed"].toBool(), "normal Return delivered");
    check(hud->property("submissions").toInt() == 1, "actual native accepted signal occurred once");
    const auto previous = find(snapshot(), "address.go")["token"].toString();
    check(press("address.cancel"), "normal Cancel pointer delivered");
    check(hud->property("cancellations").toInt() == 1 && !field->isVisible(), "actual cancel closed editor");
    check(!input.press("address.go", previous), "closed editor pointer token is invalid");
    check(press("hud.goto"), "normal toolbar reopens editor");
    check(!input.press("address.go", previous), "reopened editor cannot inherit old control token");
    check(press("address.go") && hud->property("submissions").toInt() == 2, "real normal Go button dispatched");
    tabletShown = true;
    check(find(snapshot(), "hud.goto").isEmpty(), "open tablet covers toolbar input");
    check(press("tablet.places") && tablet->property("places").toInt() == 1, "actual separate-tablet PLACES pointer routed");
    check(press("places.back") && tablet->property("backs").toInt() == 1, "actual separate-window Back pointer routed");
    check(press("places.forward") && tablet->property("forwards").toInt() == 1, "actual Forward pointer routed");
    hud->setProperty("addressShown", true);
    check(find(snapshot(), "places.back").isEmpty() && find(snapshot(), "tablet.home").isEmpty(),
        "modal address dialog covers separate tablet controls too");
    hud->setProperty("addressShown", false);
    auto back = tablet->findChild<QQuickItem*>("goBack");
    back->setEnabled(false);
    check(!press("places.back") && tablet->property("backs").toInt() == 1, "disabled native control receives no pointer");
    back->setEnabled(true);
    const auto old = find(snapshot(), "places.back")["token"].toString();
    tablet->setOpacity(0);
    check(find(snapshot(), "places.back").isEmpty(), "transparent tablet control absent");
    tablet->setOpacity(1);
    check(!input.press("places.back", old), "reappeared control cannot inherit absent token");
    QQuickItem duplicate(tablet);
    duplicate.setObjectName("goForward"); duplicate.setSize(QSizeF(40, 40));
    check(!snapshot()["ready"].toBool(), "ambiguous source controls fail closed");
    duplicate.setVisible(false);
    check(snapshot()["ready"].toBool(), "hidden duplicate does not replace actual control");
    bool foreignRejected { false };
    std::thread worker([&] { foreignRejected = input.observe(hud, tablet, true).isEmpty()
        && input.item("places.forward", "old") == nullptr && input.edit({}).isEmpty()
        && input.request(observationRequest).isEmpty(); });
    worker.join();
    check(foreignRejected, "foreign thread rejected before GUI access");
    check(press("tablet.close") && tablet->property("closes").toInt() == 1, "normal Qt Close pointer reaches actual source control");
    std::printf("iOS normal input: %d actual Qt checks passed (Qt %s); UIKit and installed-code binding NOT_PERFORMED.\n", checks, QT_VERSION_STR);
    duplicate.setParentItem(nullptr); duplicate.setParent(nullptr);
    delete hud; delete tablet;
}
