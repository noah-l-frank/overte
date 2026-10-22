// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Host seams: PathUtils resource root and original script messages only.
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QtTest/QTest>
#include <QJsonDocument>
#include <iostream>
#include "tests/device/native/NormalControlUi.h"
#include "libraries/networking/src/FeatureNavigationReplies.h"
const QString base=QString::fromUtf8(OVERTE_SOURCE_ROOT);
QUrl PathUtils::defaultScriptsLocation(const QString&) { return QUrl::fromLocalFile(base+"/scripts/"); }
QUrl PathUtils::qmlUrl(const QString& relative) { return QUrl::fromLocalFile(base+"/interface/resources/qml/"+relative); }
struct Reply : QNetworkReply {
    explicit Reply(const overte::network::RequestTicket& ticket) {
        setUrl(QUrl("http://controlled.invalid/api/v1/places/hidden-"+QString(32,'b')));
        setAttribute(QNetworkRequest::HttpStatusCodeAttribute,404);setError(ContentNotFoundError,"original 404");
        setRawHeader("X-Overte-Fixture-Response",QByteArray(32,'c'));
        setProperty("_overte_request_ticket",QVariant::fromValue(ticket));
    }
    void abort() override {} qint64 readData(char*,qint64) override { return 0; }
};
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);QQmlEngine engine;engine.addImportPath(base+"/interface/resources/qml");
    QQmlComponent component(&engine,QUrl::fromLocalFile(base+"/scripts/system/places/PicoPlaces.qml"));
    QScopedPointer<QObject> object(component.create());
    if (!object) { for (const auto& error:component.errors()) { std::cerr<<error.toString().toStdString()<<'\n'; }return 1; }
    auto root=qobject_cast<QQuickItem*>(object.data());if (!root) { return 2; }
    QQuickWindow window;window.resize(640,800);root->setParentItem(window.contentItem());root->setSize(QSizeF(640,800));window.show();window.requestActivate();QTest::qWait(300);
    QVariant message=QVariantMap{{"channel","com.overte.places"},{"action","CURRENT_LOCATION"},{"data","http://controlled.invalid/owned/scene.json?location=/0,0,4/0,0,0,1"}};
    QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,message));
    message=QVariantMap{{"channel","com.overte.places"},{"action","PLACE_DATA"},{"data",QVariantList{}},{"metaverseServers",QVariantList{}}};
    QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,message));QTest::qWait(260);
    overte::e2e::NavigationUi ui;
    auto capture=[&] { return ui.observe(root,&window); };
    const auto initial=capture();
    if (!initial.value("ready").toBool() || initial.value("controls").toArray().isEmpty()) { return 3; }
    auto input=[&](const QString& id,const QString& action,const QString& text=QString()) {
        const auto observed=capture();QJsonObject row;
        for (const auto& value:observed.value("controls").toArray()) { const auto actual=value.toObject();if (actual.value("id").toString()==id) { row=actual; } }
        if (row.isEmpty()) { std::cerr<<"missing "<<id.toStdString()<<'\n';return false; }
        QJsonObject request{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"action",action},
            {"instance",observed.value("instance")},{"generation",observed.value("generation")},
            {"sequence",observed.value("lastCommandSequence").toDouble()+1},{"observedElapsedMs",observed.value("elapsedMs")},
            {"controlId",id},{"controlToken",row.value("token")}};
        if (action=="replace") { request["text"]=text; }
        auto click=[&](QQuickItem* item) { const auto p=item->mapToScene(QPointF(item->width()/2,item->height()/2));QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,p.toPoint());return true; };
        const auto result=ui.apply(root,&window,request,click);QTest::qWait(260);
        if (action=="replace" && result.value("performed").toBool()) {
            bool changed=false;
            for (const auto& value:capture().value("controls").toArray()) {
                const auto current=value.toObject();if (current.value("id")==id && current.value("text")==text) { changed=true; }
            }
            if (!changed) { return false; }
        }
        if (id=="navigation.bookmarkName" && (row.value("dialogOriginalName")!=QJsonValue("")
                || row.value("dialogAddress")!=QJsonValue("http://controlled.invalid/owned/scene.json?location=/0,0,4/0,0,0,1"))) { return false; }
        if (!result.value("performed").toBool()) { std::cerr<<"refused "<<id.toStdString()<<'\n';return false; }return true;
    };
    if (!input("navigation.placesSearch","activate") || !input("navigation.placesSearch","replace",QString("hidden-")+QString(32,'b'))) { return 4; }
    if (!input("navigation.bookmarksTab","activate") || !input("navigation.addBookmark","activate")) { return 5; }
    if (!input("navigation.bookmarkName","activate") || !input("navigation.bookmarkName","replace",QString("e2e-")+QString(32,'b'))
            || !input("navigation.bookmark.cancel","activate")) { return 6; }
    for (const auto& value:capture().value("controls").toArray()) {
        if (value.toObject().value("id")==QJsonValue("navigation.bookmarkName")) { return 11; }
    }
    // A real enabled foreign input surface must stop the transparent-decoration
    // accommodation. No direct QML action is used to bypass the obstruction.
    QQuickItem blocker(window.contentItem());blocker.setSize(QSizeF(640,800));blocker.setZ(100000);
    blocker.setAcceptedMouseButtons(Qt::LeftButton);
    if (input("navigation.placesTab","activate")) { return 12; }
    blocker.setVisible(false);
    overte::network::RequestScope scope;auto ticket=scope.next();Reply reply(ticket);overte::e2e::FeatureNavigationReplies replies;
    replies.recordCurrentError(&reply,ticket);const auto event=replies.currentNotFound(ticket);if (event.isEmpty()) { return 7; }
    QQuickItem modal;overte::e2e::NavigationModalObservation::created(&modal,event);
    if (overte::e2e::NavigationModalObservation::original(&modal).value("nativeEvent").toMap()!=event) { return 8; }
    QQuickItem foreign;if (!overte::e2e::NavigationModalObservation::original(&foreign).isEmpty()) { return 9; }
    scope.next();if (!replies.currentNotFound(ticket).isEmpty()) { return 10; }
    std::cout<<"Original QML normal inputs and native modal/reply identity passed\n";return 0;
}
