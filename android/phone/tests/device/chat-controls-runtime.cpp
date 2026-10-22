// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual original Chat QML and normal Qt events. Host producers explicitly
// supply incoming page messages; this does not test MessagesMixer or devices.
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQuickWindow>
#include <QtTest/QTest>
#include <QSignalSpy>
#include <iostream>
#include "tests/device/native/NormalControlUi.h"
const QString base=QString::fromUtf8(OVERTE_SOURCE_ROOT);
QUrl PathUtils::defaultScriptsLocation(const QString&) { return QUrl::fromLocalFile(base+"/scripts/"); }
QUrl PathUtils::qmlUrl(const QString& relative) { return QUrl::fromLocalFile(base+"/interface/resources/qml/"+relative); }
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);QQmlEngine engine;
    engine.rootContext()->setContextProperty("HMD",QVariantMap{{"active",false}});
    QQmlComponent component(&engine,QUrl::fromLocalFile(base+"/scripts/communityScripts/armored-chat/armored_chat.qml"));
    QScopedPointer<QObject> object(component.create());
    if (!object) { for (const auto& error:component.errors()) { std::cerr<<error.toString().toStdString()<<'\n'; }return 1; }
    auto root=qobject_cast<QQuickItem*>(object.data());if (!root) { return 2; }
    root->setProperty("tabletMode",true);QQuickWindow window;window.resize(640,1000);root->setParentItem(window.contentItem());root->setSize(QSizeF(640,1000));window.show();window.requestActivate();QTest::qWait(300);
    overte::e2e::ChatUi ui;QSignalSpy messages(root,SIGNAL(sendToScript(QVariant)));
    auto capture=[&] { return ui.observe(root,&window); };
    auto input=[&](const QString& id,const QString& action,const QString& text=QString()) {
        auto observed=capture();QJsonObject row;
        for (const auto& value:observed.value("controls").toArray()) { if (value.toObject().value("id")==id) { row=value.toObject(); } }
        if (row.isEmpty()) { std::cerr<<"missing "<<id.toStdString()<<' '<<QJsonDocument(observed).toJson(QJsonDocument::Compact).constData()<<'\n';return false; }
        QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"action",action},
            {"instance",observed.value("instance")},{"generation",observed.value("generation")},{"sequence",observed.value("lastCommandSequence").toDouble()+1},
            {"observedElapsedMs",observed.value("elapsedMs")},{"controlId",id},{"controlToken",row.value("token")}};
        if (action=="replace") { command["text"]=text; }
        auto click=[&](QQuickItem* item) { QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());return true; };
        auto result=ui.apply(root,&window,command,click);QTest::qWait(150);
        if (!result.value("performed").toBool()) { std::cerr<<"refused "<<id.toStdString()<<'\n';return false; }return true;
    };
    const QString run(32,'a'),text="Overte ä Ω 東京 "+run;
    if (!capture().value("ready").toBool() || !input("chat.domain","activate") || root->property("pageVal")!="domain"
            || !input("chat.input","activate") || !input("chat.input","replace",text) || !input("chat.send","activate")) { return 3; }
    bool sent=false;for (const auto& args:messages) { const auto m=overte::e2e::createVariant(args.at(0)).toMap();if (m.value("type")=="send_message" && m.value("channel")=="domain" && m.value("message")==text) { sent=true; } }
    auto histories=overte::e2e::chatOriginalHistory(root,run);
    if (!sent || !histories.value("localMessages").toList().isEmpty() || !histories.value("domainMessages").toList().isEmpty()) { return 4; }
    if (!input("chat.settings","activate") || root->property("pageVal")!="settings" || !input("chat.erase","activate")) { return 5; }
    bool erased=false;for (const auto& args:messages) { const auto m=overte::e2e::createVariant(args.at(0)).toMap();if (m.value("type")=="action" && m.value("action")=="erase_history") { erased=true; } }
    if (!erased) { return 6; }
    QQuickItem blocker(window.contentItem());blocker.setSize(QSizeF(640,1000));blocker.setZ(100000);blocker.setAcceptedMouseButtons(Qt::LeftButton);
    if (input("chat.local","activate")) { return 7; }blocker.setVisible(false);
    if (!input("chat.close","activate")) { return 8; }
    bool closed=false;for (const auto& args:messages) { if (overte::e2e::createVariant(args.at(0)).toMap().value("type")=="chat.close") { closed=true; } }
    if (!closed) { return 9; }
    std::cout<<"PASS: original Chat QML normal channel/unicode/send/settings/erase/close events, empty receive models and foreign obstruction\n";return 0;
}
