// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original QML and ordinary Qt input. Host seams supply the running script's
// initial page message, context services and source-root URL only.
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQuickWindow>
#include <QtTest/QTest>
#include <QSignalSpy>
#include <iostream>
#include "tests/device/native/AvatarPeopleViewObservation.h"
const QString base=QString::fromUtf8(OVERTE_SOURCE_ROOT);
QUrl PathUtils::defaultScriptsLocation(const QString&) { return QUrl::fromLocalFile(base+"/scripts/"); }
QUrl PathUtils::qmlUrl(const QString& relative) { return QUrl::fromLocalFile(base+"/interface/resources/qml/"+relative); }
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);QCoreApplication::setOrganizationName("Overte-E2E-Host");qmlRegisterModule("Hifi",1,0);qmlRegisterModule("TabletScriptingInterface",1,0);QQmlEngine engine;QObject::connect(&engine,&QQmlEngine::warnings,[](const QList<QQmlError>& errors) { for (const auto& error:errors) { std::cerr<<"QML "<<error.toString().toStdString()<<"\n"; } });engine.addImportPath(base+"/interface/resources/qml");
    engine.rootContext()->setContextProperty("HMD",QVariantMap{{"active",false},{"mounted",false}});
    engine.rootContext()->setContextProperty("AddressManager",QVariantMap{{"isConnected",true}});
    engine.rootContext()->setContextProperty("Entities",QVariant::fromValue(engine.evaluate("({canRezAvatarEntities:function(){return true;},getEntityProperties:function(){return {};},getJointNames:function(){return [];}})")));
    engine.rootContext()->setContextProperty("MyAvatar",QVariant::fromValue(engine.evaluate("({getJointNames:function(){return ['Hips'];}})")));
    QQmlComponent component(&engine,PathUtils::qmlUrl("hifi/AvatarApp.qml"));QScopedPointer<QObject> object(component.create());
    if (!object) { for (const auto& error:component.errors()) { std::cerr<<error.toString().toStdString()<<'\n'; }return 1; }
    auto root=qobject_cast<QQuickItem*>(object.data());if (!root) { return 2; }
    QQuickWindow window;window.resize(640,1000);root->setParentItem(window.contentItem());root->setSize(QSizeF(640,1000));window.show();window.requestActivate();QTest::qWait(300);
    const QVariantMap original{{"avatarUrl","qrc:/meshes/defaultAvatar_full.fst"},{"avatarScale",1.0},{"avatarEntites",QVariantList{}}};
    const QVariantMap settings{{"dominantHand","right"},{"otherAvatarsCollisionsEnabled",true},{"collisionsEnabled",true},{"hmdAvatarAlignmentType","head"},{"animGraphUrl",""},{"animGraphOverrideUrl",""},{"collisionSoundUrl",""}};
    QVariant message=QVariantMap{{"method","getAvatars"},{"data",QVariantMap{{"bookmarks",QVariantMap()},{"currentAvatar",original},{"displayName","owned host"},{"currentAvatarSettings",settings}}}};
    if (!QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,message))) { return 3; }QTest::qWait(300);
    overte::e2e::AvatarPeopleUi ui;auto capture=[&] { return ui.observe(root,&window); };
    auto input=[&](const QString& id,const QString& action,const QVariant& data=QVariant()) {
        const auto observed=capture();QJsonObject row;for (const auto& value:observed.value("controls").toArray()) { if (value.toObject().value("id")==id) { row=value.toObject(); } }
        if (row.isEmpty()) { std::cerr<<"missing "<<id.toStdString()<<' '<<QJsonDocument(observed).toJson(QJsonDocument::Compact).constData()<<'\n';return false; }
        QJsonObject request{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"action",action},
            {"instance",observed.value("instance")},{"generation",observed.value("generation")},{"sequence",observed.value("lastCommandSequence").toDouble()+1},
            {"observedElapsedMs",observed.value("elapsedMs")},{"controlId",id},{"controlToken",row.value("token")}};
        if (action=="replace") { request["text"]=QJsonValue::fromVariant(data); }if (action=="set-value") { request["value"]=QJsonValue::fromVariant(data); }
        auto pointer=[&](QQuickItem*,const QPointF& p) { QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,p.toPoint());return true; };
        auto click=[&](QQuickItem* item) { return pointer(item,item->mapToScene(QPointF(item->width()/2,item->height()/2))); };
        const auto result=ui.apply(root,&window,request,click,{},pointer);QTest::qWait(260);
        if (!result.value("performed").toBool()) { std::cerr<<"refused "<<id.toStdString()<<'\n';return false; }return true;
    };
    QSignalSpy avatarMessages(root,SIGNAL(sendToScript(QVariant)));
    if (!capture().value("ready").toBool()) { return 4; }
    if (!input("avatar.url","activate") || !input("avatar.dialog.input","activate") || !input("avatar.dialog.input","replace","https://controlled.invalid/owned/avatar-a.fst")) { return 5; }
    bool entered=false;for (const auto& row:capture().value("controls").toArray()) { if (row.toObject().value("id")=="avatar.dialog.input" && row.toObject().value("text")=="https://controlled.invalid/owned/avatar-a.fst") { entered=true; } }
    if (!entered || !input("avatar.dialog.confirm","activate")) { return 6; }
    bool applied=false;for (const auto& args:avatarMessages) { const auto m=args.at(0).toMap();if (m.value("method")=="applyExternalAvatar" && m.value("avatarURL")=="https://controlled.invalid/owned/avatar-a.fst") { applied=true; } }if (!applied) { return 25; }
    if (!input("avatar.bookmark.add","activate") || !input("avatar.dialog.input","replace","e2e-"+QString(32,'b')) || !input("avatar.dialog.cancel","activate")) { return 7; }
    if (!input("avatar.settings","activate") || !input("avatar.scale","set-value",15.0)) { return 8; }
    bool scaled=false;for (const auto& row:capture().value("controls").toArray()) { if (row.toObject().value("id")=="avatar.scale" && qAbs(row.toObject().value("value").toDouble()-15.0)<0.1) { scaled=true; } }
    if (!scaled || !input("avatar.dialog.cancel","activate")) { return 9; }
    if (!input("avatar.settings","activate") || !input("avatar.scale","set-value",15.0) || !input("avatar.dialog.confirm","activate")) { return 33; }
    bool savedScale=false;for (const auto& args:avatarMessages) { const auto m=args.at(0).toMap();if (m.value("method")=="setScale" && qAbs(m.value("avatarScale").toDouble()-1.5)<.005) { savedScale=true; } }
    if (!savedScale || !input("avatar.settings","activate") || !input("avatar.scale","set-value",10.0) || !input("avatar.dialog.confirm","activate")) { return 34; }
    overte::e2e::AvatarPeopleViewObservation view;const auto observed=view.read({root},true);if (observed.isEmpty() || !observed.value("avatar").toMap().value("present").toBool()) { return 10; }
    const auto current=observed.value("avatar").toMap().value("current").toMap();
    if (current.keys()!=QStringList{"avatarScale","avatarUrl","name"} || current.value("avatarUrl")!=original.value("avatarUrl")
            || current.value("avatarScale").toDouble()!=1.0) { std::cerr<<"Missing original current avatar QObject properties\n";return 32; }
    const QString wearableId="88888888-8888-4888-8888-888888888888",wearableUrl="https://controlled.invalid/owned/main.gltf";
    if (!input("avatar.wearables","activate") || !input("avatar.wearable.add","activate") || !input("avatar.dialog.input","activate")
            || !input("avatar.dialog.input","replace",wearableUrl) || !input("avatar.dialog.confirm","activate")) { return 38; }
    bool addedWearable=false;for (const auto& args:avatarMessages) { const auto m=args.at(0).toMap();if (m.value("method")=="addWearable" && m.value("url")==wearableUrl) { addedWearable=true; } }
    if (!addedWearable) { return 39; }
    const QVariantMap vector{{"x",1.0},{"y",1.0},{"z",1.0}},zero{{"x",0.0},{"y",0.0},{"z",0.0}};
    const QVariantMap properties{{"id",wearableId},{"modelURL",wearableUrl},{"localPosition",zero},{"localRotationAngles",zero},{"dimensions",vector},{"naturalDimensions",vector},{"parentJointIndex",0}};
    QVariant wornMessage=QVariantMap{{"method","wearablesUpdated"},{"wearables",QVariantList{QVariantMap{{"properties",properties}}}}};
    if (!QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,wornMessage))) { return 35; }
    bool originalWearable=false;for (const auto& row:capture().value("controls").toArray()) { const auto actual=row.toObject();
        if (actual.value("id")=="avatar.wearable.remove" && actual.value("wearableId")==wearableId
                && actual.value("wearableUrlSha256")==QString::fromLatin1(QCryptographicHash::hash(wearableUrl.toUtf8(),QCryptographicHash::Sha256).toHex())) { originalWearable=true; } }
    if (!originalWearable) { std::cerr<<"Missing original selected wearable "<<QJsonDocument(capture()).toJson(QJsonDocument::Compact).constData()<<'\n';return 36; }
    if (!input("avatar.wearable.remove","activate")) { return 36; }
    bool tookOff=false;for (const auto& args:avatarMessages) { const auto m=args.at(0).toMap();if (m.value("method")=="deleteWearable" && m.value("entityID")==wearableId) { tookOff=true; } }
    if (!tookOff || !input("avatar.dialog.confirm","activate")) { return 37; }
    QQuickItem blocker(window.contentItem());blocker.setSize(QSizeF(640,1000));blocker.setZ(100000);blocker.setAcceptedMouseButtons(Qt::LeftButton);
    if (input("avatar.url","activate")) { return 11; }blocker.setVisible(false);
    // A separately loaded original People page receives host producer messages;
    // the test exercises only ordinary UI transport and passive page/model reads.
    root->setVisible(false);QObject services,users;
    services.setProperty("findableBy","none");users.setProperty("canKick",false);
    engine.rootContext()->setContextProperty("GlobalServices",&services);engine.rootContext()->setContextProperty("Users",QVariant::fromValue(engine.evaluate("({canKick:false,getAvatarGain:function(){return 0;}})")));
    engine.rootContext()->setContextProperty("PlatformInfo",QVariant::fromValue(engine.evaluate("({has3DHTML:function(){return false;}})")));
    engine.rootContext()->setContextProperty("Account",QVariant::fromValue(engine.evaluate("({username:'owned-self',metaverseServerURL:'https://controlled.invalid',isLoggedIn:function(){return true;}})")));
    engine.rootContext()->setContextProperty("HMD",QVariantMap{{"active",false},{"mounted",false}});
    QQmlComponent palComponent(&engine,PathUtils::qmlUrl("hifi/Pal.qml"));QScopedPointer<QObject> palObject(palComponent.beginCreate(engine.rootContext()));
    QSignalSpy messages(palObject.data(),SIGNAL(sendToScript(QVariant)));palComponent.completeCreate();
    if (!palObject) { for (const auto& error:palComponent.errors()) { std::cerr<<error.toString().toStdString()<<'\n'; }return 12; }
    root=qobject_cast<QQuickItem*>(palObject.data());if (!root) { return 13; }root->setParentItem(window.contentItem());root->setSize(QSizeF(640,1000));
    auto send=[&](const QString& method,const QVariant& params) { QVariant m=QVariant::fromValue(engine.toScriptValue(QVariantMap{{"method",method},{"params",params}}));const auto ok=QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,m));QTest::qWait(260);return ok; };
    const QString session="11111111-1111-4111-8111-111111111111";
    auto person=[](const QString& id,const QString& name) { return QVariantMap{{"sessionId",id},{"userName",name},{"displayName",name},{"profileUrl",""},{"connection",""},{"admin",false},{"isPresent",true},{"isReplicated",false},{"personalMute",false},{"ignore",false},{"audioLevel",0.0},{"avgAudioLevel",0.0}}; };
    if (!send("nearbyUsers",QVariantList{person("","owned-self"),person(session,"owned-peer")})) { return 14; }
    bool boundRow=false;for (const auto& raw:capture().value("controls").toArray()) { const auto r=raw.toObject();if (r.value("id")=="people.row.0" && r.value("peerSession")==session && r.value("userName")=="owned-peer") { boundRow=true; } }
    if (!boundRow) { std::cerr<<"Missing actual People row metadata\n";return 23; }
    if (!input("people.row.0","activate") || !input("people.RequestConnection","activate")) { return 15; }
    bool requested=false;for (const auto& args:messages) { const auto m=args.at(0).toMap();if (m.value("method")=="connectionRequest" && m.value("params")==session) { requested=true; } }
    if (!requested || !send("connectionState",QVariantMap{{"phase","incoming"},{"peer",session},{"requestId",QString(32,'b')},{"peerName","owned-peer"},{"message","Original peer invitation"}})) { return 16; }
    auto peopleView=view.read({root},true);if (peopleView.isEmpty() || !peopleView.value("people").toMap().value("dialog").toBool()) { return 17; }
    if (!input("people.ConnectionDecline","activate")) { return 18; }
    if (!send("connectionState",QVariantMap{{"phase","incoming"},{"peer",session},{"requestId",QString(32,'c')},{"peerName","owned-peer"},{"message","Original peer invitation"}}) || !input("people.ConnectionAccept","activate")) { return 19; }
    if (!send("connectionState",QVariantMap{{"phase","outgoing"},{"peer",session},{"requestId",QString(32,'d')},{"peerName","owned-peer"},{"message","Waiting for consent"}}) || !input("people.ConnectionCancel","activate")) { return 20; }
    if (!send("connectionState",QVariantMap{{"phase","idle"},{"message",""},{"peerName",""}})) { return 21; }
    peopleView=view.read({root},true);if (peopleView.isEmpty() || peopleView.value("people").toMap().value("dialog").toBool()) { return 22; }
    bool declined=false,accepted=false,cancelled=false;
    for (const auto& args:messages) { const auto m=args.at(0).toMap();if (m.value("method")=="connectionRespond") { if (m.value("params").toBool()) { accepted=true; }else { declined=true; } }if (m.value("method")=="connectionCancel") { cancelled=true; } }
    if (!declined || !accepted || !cancelled) { return 24; }
    if (!input("people.connections","activate")) { return 26; }
    const QVariantMap user{{"username","owned-peer"},{"connection","connection"},{"images",QVariantMap{{"thumbnail",""}}},{"location",QVariantMap{{"domain",QVariantMap{{"name","Owned domain"}}}}}};
    const QVariantMap response{{"status","success"},{"data",QVariantMap{{"users",QVariantList{user}}}},{"total_pages",1},{"current_page",1},{"total_entries",1}};
    QSet<int> replied;
    for (int pass=0;pass<4;++pass) {
        QVariantList pending;for (const auto& args:messages) { const auto m=overte::e2e::createVariant(args.at(0)).toMap();if (m.value("method")=="http.request" && !replied.contains(m.value("id").toInt())) { pending.append(m.value("id")); } }
        if (pending.isEmpty()) { break; }
        for (const auto& id:pending) {
            if (!id.isValid()) { return 27; }replied.insert(id.toInt());
            QVariant httpMessage=QVariant::fromValue(engine.toScriptValue(QVariantMap{{"method","http.response"},{"id",id},{"error",QVariant()},{"response",response}}));
            if (!QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,httpMessage))) { return 28; }QTest::qWait(200);
        }
    }
    if (replied.isEmpty()) { return 27; }
    peopleView=view.read({root},true);if (peopleView.isEmpty() || peopleView.value("models").toMap().value("connectionsUserModel").toMap().value("count").toInt()!=1) { return 29; }
    if (!input("people.row.0","activate") || !input("people.remove.owned-peer","activate")) { return 30; }
    bool removed=false;for (const auto& args:messages) { const auto m=args.at(0).toMap();if (m.value("method")=="removeConnection" && m.value("params")=="owned-peer") { removed=true; } }if (!removed) { return 31; }
    std::cout<<"PASS: original Avatar/People QML ordinary URL/bookmark/scale/request/decline/accept/cancel events, passive models and foreign obstruction\n";return 0;
}
