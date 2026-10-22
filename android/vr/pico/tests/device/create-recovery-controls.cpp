// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual NativeCreate QML, normal pointer/field/combo and original editor JS.
// Host window, non-V8 JS runtime, permissions, storage and geometry are actors.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QQuickItem>
#include <QSignalSpy>
#include <QTest>
#include <QTextStream>
#include <QJsonDocument>
#include <QFile>
#include <cassert>
#include <PointerEvent.h>
#include <QMouseEvent>
#include <QTouchDevice>
#include <QTouchEvent>
#include <QWheelEvent>
#include <QQuickRenderControl>
#include <map>
#include "actual-pointer-route.inc"
#include "tests/device/native/NormalScriptControls.h"
#include "tests/device/native/NormalControlUi.h"
#include "actual-create-base-input.inc"

int main(int argc,char**argv){
    QGuiApplication app(argc,argv);using namespace overte::e2e;
    NormalControlUi normal(NormalControlUi::Surface::Create);
    if(!app.arguments().contains("--testScript")){assert(normal.observe(nullptr,nullptr).isEmpty());return 0;}
    const auto path=app.arguments().at(app.arguments().size()-2),imports=app.arguments().last();
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    QQmlEngine engine;engine.addImportPath(path+"/interface/resources/qml");engine.addImportPath(imports);
    QQmlComponent hmd(&engine);hmd.setData("import QtQuick 2.7;QtObject {property bool active:false}",{});
    QScopedPointer<QObject> hmdActor(hmd.create());engine.rootContext()->setContextProperty("HMD",hmdActor.data());
    QQuickRenderControl renderControl;QQuickWindow window(&renderControl);window.resize(600,1000);window.contentItem()->setSize(QSizeF(600,1000));
    QQuickItem root(window.contentItem());root.setSize(QSizeF(600,1000));
    QQmlComponent component(&engine,QUrl::fromLocalFile(path+"/scripts/system/create/qml/NativeCreate.qml"));
    auto page=qobject_cast<QQuickItem*>(component.beginCreate(engine.rootContext()));if(!page){qFatal("%s",qPrintable(component.errorString()));}
    page->setParentItem(&root);page->setSize(root.size());QSignalSpy calls(page,SIGNAL(sendToScript(QVariant)));
    component.completeCreate();QTest::qWait(50);assert(calls.size()==1);
    assert(createVariant(calls.first().first()).toMap().value("method").toString()=="nativeCreate.ready");
    assert(page->property("e2eSettingsReceived").userType()==QMetaType::Bool && !page->property("e2eSettingsReceived").toBool());
    auto evaluate=[&](const QString& code,const QString& file=QString()){
        auto result=engine.evaluate(code,file);if(result.isError()){qFatal("%s",qPrintable(result.toString()+"\n"+result.property("stack").toString()));}return result;};
    auto source=[&](const QString& file){QFile input(path+'/'+file);assert(input.open(QIODevice::ReadOnly));return QString::fromUtf8(input.readAll());};
    evaluate(source("android/vr/pico/tests/device/create-recovery-backend.js"));
    evaluate(source("scripts/system/create/modules/picoQmlMessageValidation.js"));evaluate("var validatePicoQmlMessage=module.exports;module={exports:{}};");
    evaluate(source("scripts/system/create/modules/nativeCreateBridge.js"));evaluate("var originalNativeBridge=module.exports;");
    QFile originalCode(imports+"/../original-recovery.js");assert(originalCode.open(QIODevice::ReadOnly));evaluate(QString::fromUtf8(originalCode.readAll()));
    auto backend=evaluate("initializeOriginalRecovery()");int delivered=0;
    auto drain=[&]{
        while(delivered<calls.size()){
            const auto original=createVariant(calls.at(delivered++).first());const auto raw=QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact);
            auto value=evaluate('('+QString::fromUtf8(raw)+')');auto result=backend.property("handle").call({value});assert(!result.isError());
            const auto outputs=evaluate("outputs.splice(0,outputs.length)").toVariant().toList();
            for(const auto& message:outputs){assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,message)));}
        }
    };
    OffscreenQmlSurface surface(&root,&window);int pointers=0;QString currentId;QJsonObject currentCommand;
    auto rawPointer=[&](QQuickItem* item){++pointers;const bool sent=sendPointerClick(item,&surface);QCoreApplication::processEvents();return sent;};
    auto pointer=[&](QQuickItem* item){return originalCreateInput(item,&window,currentId,"activate",currentCommand,rawPointer).value("performed").toBool();};
    auto row=[&](NormalControlUi& ui,const QString& id){const auto value=ui.observe(&root,&window);assert(value.value("ready").toBool());
        for(const auto& item:value.value("controls").toArray()){if(item.toObject().value("id")==id){return item.toObject();}}
        std::function<void(QQuickItem*)> diagnose=[&](QQuickItem* item){const auto known=createControlId(item);if(!known.isEmpty()){
            const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
            fprintf(stderr,"actual tool %s visible=%d enabled=%d size=%g,%g scene=%g,%g rect=%d\n",qPrintable(known),item->isVisible(),item->isEnabled(),item->width(),item->height(),point.x(),point.y(),!NormalControlUi::visibleRect(item,&window).isEmpty());}
            for(auto child:item->childItems()){diagnose(child);}};diagnose(&root);
        qFatal("missing actual original tool: %s",qPrintable(id));return QJsonObject();};
    auto apply=[&](NormalControlUi& ui,const QString& id,const QString& action,const QJsonValue& argument=QJsonValue()){
        const auto item=row(ui,id),actual=ui.observe(&root,&window);QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",actual.value("instance")},{"generation",actual.value("generation")},{"sequence",actual.value("lastCommandSequence").toInt()+1},
            {"observedElapsedMs",actual.value("elapsedMs")},{"controlId",id},{"controlToken",item.value("token")},{"action",action}};
        if(action=="replace"){command["text"]=argument;}else if(action=="select-index"){command["index"]=argument;}
        currentId=id;currentCommand=command;
        const auto result=ui.apply(&root,&window,command,pointer);if(!result.value("performed").toBool()){qFatal("actual normal input refused: %s/%s",qPrintable(id),qPrintable(action));}
        drain();QCoreApplication::processEvents();renderControl.polishItems();QCoreApplication::processEvents();return result;
    };
    drain();renderControl.polishItems();QCoreApplication::processEvents();
    auto choose=[&](const QString& id,int index){apply(normal,id,"activate");apply(normal,id,"select-index",index);assert(row(normal,id).value("currentIndex").toInt()==index);};
    choose("create.host",0);choose("create.shape",0);apply(normal,"create.new-shape","activate");
    const auto denied=row(normal,"create.page");
    assert(denied.value("statusError").toBool() && denied.value("statusText")==QJsonValue("Invalid entity type, properties or creation permission."));
    auto before=evaluate("recoveryState()").toVariant().toMap();assert(before.value("creates").toList().isEmpty());
    // Only this declared permissions actor changes; no native setter or direct
    // product control handler is invoked as the test's input.
    evaluate("permission=true");apply(normal,"create.tab.0","activate");choose("create.host",0);choose("create.shape",0);
    apply(normal,"create.new-shape","activate");
    const auto created=row(normal,"create.page");assert(!created.value("statusError").toBool() && created.value("selectedIds").toArray().size()==1);
    auto measured=evaluate("recoveryState()").toVariant().toMap();const auto creations=measured.value("creates").toList();assert(creations.size()==1);
    const auto original=creations.first().toMap();assert(original.value("host")==QVariant("domain"));
    const auto properties=original.value("properties").toMap();assert(properties.value("type")==QVariant("Shape") && properties.value("shape")==QVariant("Cube"));
    assert(measured.value("timers").toInt()==0);
    apply(normal,"create.delete","activate");const auto deleted=row(normal,"create.page");assert(deleted.value("selectedIds").toArray().isEmpty());
    const auto final=evaluate("recoveryState()").toVariant().toMap();assert(final.value("rows").toList().isEmpty() && final.value("deletes").toList().size()==1);
    QJsonObject output{{"denied",denied},{"created",created},{"deleted",deleted},{"actor",QJsonObject::fromVariantMap(final)},{"pointerCalls",pointers}};
    delete page;QTextStream(stdout)<<QJsonDocument(output).toJson(QJsonDocument::Compact)<<'\n';
}
