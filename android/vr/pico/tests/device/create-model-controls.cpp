// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/NormalScriptControls.h"
#include "tests/device/native/NormalControlUi.h"
#include <QGuiApplication>
#include <QQuickRenderControl>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QtTest/QTest>
#include <cassert>

void paintCounterexamples(QQmlEngine& engine) {
#if QT_VERSION < QT_VERSION_CHECK(6,0,0)
    QQuickRenderControl renderer;QQuickWindow window(&renderer);window.resize(160,160);renderer.initialize(nullptr);
    auto image=[&] { renderer.polishItems();renderer.sync();renderer.render();return renderer.grab(); };
#else
    QQuickWindow window;window.resize(160,160);window.show();
    auto image=[&] { window.update();QTest::qWait(80);return window.grabWindow(); };
#endif
    auto load=[&](const QByteArray& qml) {
        QQmlComponent component(&engine);component.setData(qml,QUrl("qrc:/create-hit-paint-fixture.qml"));
        auto root=qobject_cast<QQuickItem*>(component.create());assert(root);root->setParentItem(window.contentItem());QTest::qWait(30);return root;
    };
    auto root=load("import QtQuick 2.7; Rectangle {x:20;y:20;width:80;height:80;color:'#e01020';"
        " Rectangle {objectName:'Behind';z:-1;x:10;y:10;width:40;height:40;color:'#10e020'} }");
    auto behind=root->findChild<QQuickItem*>("Behind");assert(behind);
    const auto point=behind->mapToScene(QPointF(20,20));auto pixels=image();assert(!pixels.isNull());
    assert(pixels.pixelColor(point.toPoint()).rgb()==QColor("#e01020").rgb());
    assert(!overte::e2e::NormalControlUi::ownsPoint(behind,&window,point));delete root;
    root=load("import QtQuick 2.7; Item {width:160;height:160;"
        " Rectangle {objectName:'Target';x:20;y:20;width:40;height:40;color:'#10e020'}"
        " Rectangle {objectName:'Foreign';z:100;width:5;height:5;color:'transparent';"
        " Rectangle {objectName:'Outside';z:10;x:20;y:20;width:40;height:40;color:'#1050e0'} } }");
    auto target=root->findChild<QQuickItem*>("Target"),foreign=root->findChild<QQuickItem*>("Foreign");assert(target&&foreign);
    const auto center=target->mapToScene(QPointF(20,20));pixels=image();assert(!pixels.isNull());
    assert(pixels.pixelColor(center.toPoint()).rgb()==QColor("#1050e0").rgb());
    assert(!overte::e2e::NormalControlUi::ownsPoint(target,&window,center));
    foreign->setEnabled(false);pixels=image();assert(!pixels.isNull());
    assert(pixels.pixelColor(center.toPoint()).rgb()==QColor("#1050e0").rgb());
    assert(!overte::e2e::NormalControlUi::ownsPoint(target,&window,center));
    foreign->setVisible(false);pixels=image();assert(!pixels.isNull());
    assert(pixels.pixelColor(center.toPoint()).rgb()==QColor("#10e020").rgb());
    assert(overte::e2e::NormalControlUi::ownsPoint(target,&window,center));
    foreign->setVisible(true);foreign->setEnabled(true);foreign->setClip(true);pixels=image();assert(!pixels.isNull());
    assert(pixels.pixelColor(center.toPoint()).rgb()==QColor("#10e020").rgb());
    assert(overte::e2e::NormalControlUi::ownsPoint(target,&window,center));delete root;
#if QT_VERSION < QT_VERSION_CHECK(6,0,0)
    renderer.invalidate();
#endif
}

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    using namespace overte::e2e;
    NormalControlUi controls(NormalControlUi::Surface::Create);
    if (!app.arguments().contains("--testScript")) { assert(controls.observe(nullptr,nullptr).isEmpty());return 0; }
    const auto path=app.arguments().last();
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");
    PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    QQmlEngine engine;QQuickWindow window;window.resize(1200,1800);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(1200,1800));
    QQuickItem loader(&root);loader.setObjectName("loader");loader.setSize(root.size());
    auto load=[&] {
        QQmlComponent component(&engine,QUrl::fromLocalFile(path+"/scripts/system/create/qml/NativeCreate.qml"));
        auto page=qobject_cast<QQuickItem*>(component.create());
        if (!page) { qFatal("%s",qPrintable(component.errorString())); }
        page->setParentItem(&loader);page->setSize(loader.size());QTest::qWait(50);return page;
    };
    auto page=load();assert(!createComponentSource(page).isEmpty());
    QSignalSpy calls(page,SIGNAL(sendToScript(QVariant)));
    auto observe=[&] { return controls.observe(&root,&window); };
    auto row=[&](const QString& id) {
        auto value=observe();assert(value.value("ready").toBool());
        for (const auto& raw:value.value("controls").toArray()) { if (raw.toObject().value("id")==id) { return raw.toObject(); } }
        qFatal("missing actual normal control: %s",qPrintable(id));return QJsonObject();
    };
    auto request=[&](const QString& id,const QString& action,const QString& text=QString()) {
        auto actual=row(id);auto current=observe();
        QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",current.value("instance")},{"generation",current.value("generation")},
            {"sequence",current.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",current.value("elapsedMs")},
            {"controlId",id},{"controlToken",actual.value("token")},{"action",action}};
        if (action=="replace") { command["text"]=text; }return command;
    };
    int clicks{0};
    auto pointer=[&](QQuickItem* item) {
        ++clicks;QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,
            item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());
        QCoreApplication::processEvents();return true;
    };
    auto apply=[&](const QJsonObject& command) { return controls.apply(&root,&window,command,pointer); };
    auto activate=[&](const QString& id) { auto result=apply(request(id,"activate"));if (!result.value("performed").toBool()) {fprintf(stderr,"normal activation refused: %s\n",qPrintable(id));abort();} };
    assert(row("create.host").value("currentIndex").toInt()==0); // Original domain default.
    activate("create.resource");const auto url=QStringLiteral("http://controlled.test/feature-fixture/v1/runs/")+QString(32,'a')+
        "/tickets/"+QString(32,'b')+"/gltf-bundle/main.gltf";
    auto replacement=request("create.resource","replace",url);assert(apply(replacement).value("performed").toBool());
    assert(row("create.resource").value("text")==url && calls.count()==0);
    assert(!apply(replacement).value("performed").toBool());
    auto create=request("create.new-model","activate");assert(apply(create).value("performed").toBool());
    assert(calls.count()==1 && page->property("currentTab").toInt()==2);
    auto original=createVariant(calls.takeFirst().first()).toMap();auto params=createVariant(original.value("params")).toMap();
    auto properties=createVariant(params.value("properties")).toMap();
    assert(original.value("method")=="nativeCreate.create" && params.value("host")=="domain"
        && properties.size()==2 && properties.value("type")=="Model" && properties.value("modelURL")==url);
    assert(!apply(create).value("performed").toBool() && calls.count()==0); // No replay after page transition.
    // A declared entity-actor boundary delivers the original backend selection
    // route. All property input below remains original pointer/IME delivery.
    QVariantMap selectedProperties{{"name",""},{"type","Model"},{"textures",""},
        {"dimensions",QVariantMap{{"x",1.0},{"y",1.0},{"z",1.0}}}};
    for (int index=0;index<100;++index) { selectedProperties.insert(QString("extra%1").arg(index,3,10,QChar('0')),"original"); }
    QVariantMap selection{{"method","nativeCreate.selection"},{"params",QVariantMap{{"entities",QVariantList{
        QVariantMap{{"id","33333333-3333-3333-3333-333333333333"},{"type","Model"},{"editable",true},{"properties",selectedProperties}}}}}}};
    assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,QVariant(selection))));QTest::qWait(30);
    calls.clear();auto search=page->findChild<QQuickItem*>("NativeCreatePropertySearch");assert(search);
    assert(createControlId(search)=="create.filter");
    const auto center=search->mapToScene(QPointF(search->width()/2,search->height()/2));
    assert(NormalControlUi::ownsPoint(search,&window,center));
    // Real Qt software paint and hit order are checked in a controlled host
    // window below, independent of platform grabWindow availability on Qt5.
    paintCounterexamples(engine);
    // A genuinely higher visible foreign item blocks the actual original field,
    // including when disabled; hidden children cannot supply false occlusion.
    auto foreign=new QQuickItem(window.contentItem());foreign->setZ(1000);foreign->setPosition(center-QPointF(20,20));foreign->setSize(QSizeF(40,40));
    assert(!NormalControlUi::ownsPoint(search,&window,center));foreign->setEnabled(false);
    assert(!NormalControlUi::ownsPoint(search,&window,center));foreign->setVisible(false);
    assert(NormalControlUi::ownsPoint(search,&window,center));delete foreign;
    search->setEnabled(false);assert(!NormalControlUi::ownsPoint(search,&window,center));
    assert(!row("create.filter").value("inputReady").toBool());search->setEnabled(true);
    // Unbounded original-style content must honor a real parent's clip. These
    // host items diagnose scene geometry only; no product QML field is moved.
    auto container=new QQuickItem(window.contentItem());container->setZ(1000);
    auto outside=new QQuickItem(container);outside->setPosition(center-QPointF(20,20));outside->setSize(QSizeF(40,40));
    assert(!NormalControlUi::ownsPoint(search,&window,center));container->setClip(true);
    assert(NormalControlUi::ownsPoint(search,&window,center));delete container;
    auto excessive=new QQuickItem(window.contentItem());excessive->setZ(1000);auto depth=excessive;
    for(int index=0;index<130;++index) { depth=new QQuickItem(depth); }
    assert(!NormalControlUi::ownsPoint(search,&window,center));delete excessive;
    excessive=new QQuickItem(window.contentItem());excessive->setZ(1000);
    for(int index=0;index<4097;++index) { new QQuickItem(excessive); }
    assert(!NormalControlUi::ownsPoint(search,&window,center));delete excessive;
    assert(NormalControlUi::ownsPoint(search,&window,center));
    activate("create.filter");
    assert(apply(request("create.filter","replace","textures")).value("performed").toBool());QTest::qWait(30);
    assert(search->property("text").toString()=="textures");
    assert(row("create.textures").value("text")=="");activate("create.textures");
    const auto textureUrl=QStringLiteral("http://controlled.test/feature-fixture/v1/runs/")+QString(32,'a')+
        "/tickets/"+QString(32,'c')+"/checker.png";
    const auto textureJson=QString::fromUtf8(QJsonDocument(QJsonObject{{"checker.png",textureUrl}}).toJson(QJsonDocument::Compact));
    assert(apply(request("create.textures","replace",textureJson)).value("performed").toBool());
    assert(row("create.textures").value("text")==textureJson);activate("create.apply-typed");
    int edits{0};
    for (const auto& call:calls) {
        const auto message=createVariant(call.first()).toMap();
        if (message.value("method")=="nativeCreate.edit") {
            ++edits;const auto body=createVariant(message.value("params")).toMap();
            assert(body.value("id")=="33333333-3333-3333-3333-333333333333");
            const auto patch=createVariant(body.value("properties")).toMap();
            assert(patch.size()==1 && patch.value("textures")==textureJson);
        }
    }
    assert(edits==1);calls.clear();
    // Original NEW-tab navigation is normal pointer input; another entity is
    // never created by changing a native observation or by invoking a handler.
    activate("create.tab.0");auto stale=request("create.new-model","activate");
    delete page;QCoreApplication::processEvents();page=load();
    assert(!apply(stale).value("performed").toBool());
    auto field=page->findChild<QQuickItem*>("NativeCreateResourceUrl");assert(field && field->property("text").toString().isEmpty());
    QSignalSpy replacementCalls(page,SIGNAL(sendToScript(QVariant)));
    activate("create.new-model");assert(replacementCalls.count()==0 && page->property("statusError").toBool()); // Original error, no entity request.
    assert(clicks>=4);delete page;
    qInfo("PASS actual NativeCreate NEW Model and original texture filter/TextArea/Apply via pointer/NativeFieldInput; exact original domain/Model/URL and texture edit callbacks; unbounded Flickable/clip/foreign overlay/hidden/disabled/traversal bounds, no replay and missing-URL error; host window and backend actor are explicit boundaries");
}
