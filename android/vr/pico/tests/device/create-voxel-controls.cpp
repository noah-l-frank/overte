// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual original QML/normal touch/field + full original tools/bridge/voxel JS.
// JS runtime/transport/geometry/volume/timers are declared host actors.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QQuickItem>
#include <QSignalSpy>
#include <QTest>
#include <QTextStream>
#include <QJsonDocument>
#include <QFile>
#include <QFileInfo>
#include <QDir>
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
#include "actual-create-voxel-input.inc"
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
#include "create-voxel-native-join.h"
#endif

int main(int argc,char**argv){
    QGuiApplication app(argc,argv);using namespace overte::e2e;
    NormalControlUi tools(NormalControlUi::Surface::CreateVoxel),normal(NormalControlUi::Surface::Create);
    if(!app.arguments().contains("--testScript")){assert(tools.observe(nullptr,nullptr).isEmpty());return 0;}
    const auto path=app.arguments().at(app.arguments().size()-2),imports=app.arguments().last();
#ifdef OVERTE_CREATE_ORIGINAL_TEXTURES
    PathUtils::defaultScriptsLocation(path+"/scripts/");
#else
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
#endif
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
    QJsonObject settingsReceipt;
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    // Capture the real empty pre-reply state before Add needs an earlier
    // nativeCreate.ready roundtrip. Never reset the QML receipt afterwards.
    settingsReceipt={{"beforeReply",page->property("e2eSettingsReceived").toBool()},
        {"beforeControls",tools.observe(&root,&window).value("controls").toArray().size()}};
#endif
    auto evaluate=[&](const QString& code,const QString& file=QString()){
        auto result=engine.evaluate(code,file);if(result.isError()){qFatal("%s",qPrintable(result.toString()+"\n"+result.property("stack").toString()));}return result;};
    auto source=[&](const QString& file){QFile input(path+'/'+file);assert(input.open(QIODevice::ReadOnly));return QString::fromUtf8(input.readAll());};
    evaluate(source("android/vr/pico/tests/device/create-voxel-backend.js"));
    for(const auto& file:{"scripts/system/create/modules/nativeCreateBridge.js","scripts/system/create/editModes/editModes.js","scripts/system/create/editModes/editVoxels.js"}){evaluate(source(file),file);}
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    NativeCreateVoxelJoin nativeVoxel;
    QQmlEngine::setObjectOwnership(&nativeVoxel,QQmlEngine::CppOwnership);
    engine.globalObject().setProperty("nativeVoxel",engine.newQObject(&nativeVoxel));
    evaluate(source("android/vr/pico/tests/device/create-voxel-native-bindings.js"));
    QFile originalDelete(app.arguments().at(app.arguments().size()-3));assert(originalDelete.open(QIODevice::ReadOnly));
    evaluate(QString::fromUtf8(originalDelete.readAll()),"original-voxel-delete.js");
#endif
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    engine.globalObject().setProperty("originalCreateScriptDirectory",path+"/scripts/system/create");
    evaluate(source("android/vr/pico/tests/device/create-voxel-add-bindings.js"));
    for(const auto& name:{"original-voxel-validation.js","original-voxel-add.js"}){
        QFile input(QFileInfo(originalDelete).dir().filePath(name));assert(input.open(QIODevice::ReadOnly));
        evaluate(QString::fromUtf8(input.readAll()),name);
    }
#endif
    auto backend=evaluate("initializeOriginalTools()");int delivered=0;
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    engine.globalObject().setProperty("nativeCreate",backend);
#endif
    auto drain=[&]{
        while(delivered<calls.size()){
            const auto original=createVariant(calls.at(delivered++).first());const auto raw=QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact);
            auto value=evaluate('('+QString::fromUtf8(raw)+')');
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
            auto result=engine.globalObject().property("fromQml").call({value});
#else
            auto result=backend.property("handle").call({value});
#endif
            if(result.isError()){qFatal("%s",qPrintable(result.toString()+"\n"+result.property("stack").toString()));}
            const auto outputs=evaluate("outputs.splice(0,outputs.length)").toVariant().toList();
            for(const auto& message:outputs){assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,message)));}
        }
    };
    OffscreenQmlSurface surface(&root,&window);int pointers=0;
    auto pointer=[&](QQuickItem* item){++pointers;const bool sent=sendPointerClick(item,&surface);QCoreApplication::processEvents();return sent;};
    auto row=[&](NormalControlUi& ui,const QString& id){const auto value=ui.observe(&root,&window);assert(value.value("ready").toBool());
        for(const auto& item:value.value("controls").toArray()){if(item.toObject().value("id")==id){return item.toObject();}}
        std::function<void(QQuickItem*)> diagnose=[&](QQuickItem* item){const auto known=createVoxelControlId(item);if(!known.isEmpty()){
            const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
            fprintf(stderr,"actual tool %s visible=%d enabled=%d size=%g,%g scene=%g,%g rect=%d\n",qPrintable(known),item->isVisible(),item->isEnabled(),item->width(),item->height(),point.x(),point.y(),!NormalControlUi::visibleRect(item,&window).isEmpty());}
            for(auto child:item->childItems()){diagnose(child);}};diagnose(&root);
        qFatal("missing actual original tool: %s",qPrintable(id));return QJsonObject();};
    auto apply=[&](NormalControlUi& ui,const QString& id,const QString& action,const QJsonValue& argument=QJsonValue()){
        const auto item=row(ui,id),actual=ui.observe(&root,&window);QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",actual.value("instance")},{"generation",actual.value("generation")},{"sequence",actual.value("lastCommandSequence").toInt()+1},
            {"observedElapsedMs",actual.value("elapsedMs")},{"controlId",id},{"controlToken",item.value("token")},{"action",action}};
        if(action=="replace"){command["text"]=argument;}else if(action=="select-index"){command["index"]=argument;}
        const auto result=ui.apply(&root,&window,command,pointer);if(!result.value("performed").toBool()){qFatal("actual normal input refused: %s/%s",qPrintable(id),qPrintable(action));}
        if(id=="create.tab.3" && settingsReceipt.isEmpty()){
            // The normal tab has opened, but the original backend reply has not
            // been delivered. QML defaults must not become an owned baseline.
            const auto receipt=page->property("e2eSettingsReceived");
            assert(receipt.userType()==QMetaType::Bool && !receipt.toBool());
            const auto controls=tools.observe(&root,&window).value("controls").toArray();
            assert(controls.isEmpty() && createVoxelSettings(page).isEmpty());
            settingsReceipt["beforeReply"]=receipt.toBool();settingsReceipt["beforeControls"]=controls.size();
        }
        drain();QCoreApplication::processEvents();renderControl.polishItems();QCoreApplication::processEvents();return result;
    };
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    // The complete original PathUtils supplies the canonical file directory.
    // Exercise both spellings and preserve exact scheme/authority identity.
    const auto actualScripts=PathUtils::defaultScriptsLocation();
    assert(actualScripts.scheme()=="file" && !actualScripts.path().endsWith('/'));
    const auto actualDialog=QUrl::fromLocalFile(QFileInfo(path+"/scripts/system/create/qml/NewPolyVoxDialog.qml").canonicalFilePath());
    const auto relativeDialog=QUrl("system/create/qml/NewPolyVoxDialog.qml");
    assert(createScriptDirectoryUrl(actualScripts).resolved(relativeDialog)==actualDialog);
    auto slashScripts=actualScripts;slashScripts.setPath(slashScripts.path()+'/');
    assert(createScriptDirectoryUrl(slashScripts).resolved(relativeDialog)==actualDialog);
    const QUrl qrcScripts("qrc:///scripts"),qrcSlash("qrc:///scripts/");
    assert(createScriptDirectoryUrl(qrcScripts).resolved(relativeDialog)==createScriptDirectoryUrl(qrcSlash).resolved(relativeDialog));
    assert(createScriptDirectoryUrl(qrcScripts).resolved(relativeDialog)!=actualDialog);
    // Same complete original QML bytes under actual foreign Qt contexts must
    // remain inadmissible, even with identical IDs and parent structure.
    for(const auto& foreignUrl:{QUrl::fromLocalFile(path+"/foreign/system/create/qml/NewPolyVoxDialog.qml"),
            QUrl("qrc:///scripts/system/create/qml/NewPolyVoxDialog.qml")}){
        QQmlComponent foreignComponent(&engine);
        foreignComponent.setData(source("scripts/system/create/qml/NewPolyVoxDialog.qml").toUtf8(),foreignUrl);
        auto foreign=qobject_cast<QQuickItem*>(foreignComponent.create());
        if(!foreign){qFatal("%s",qPrintable(foreignComponent.errorString()));}foreign->setParentItem(&root);foreign->setSize(root.size());
        std::function<void(QQuickItem*)> rejectForeign=[&](QQuickItem* item){assert(!createPolyvoxObject(item) && createExtraControlId(item).isEmpty());
            for(auto child:item->childItems()){rejectForeign(child);}};
        rejectForeign(foreign);delete foreign;
    }
    // Normal detail selector -> original fromQml -> original Tablet push.
    NormalControlUi extra(NormalControlUi::Surface::CreateExtra);
    apply(extra,"create-extra.detail-kind","activate");apply(extra,"create-extra.detail-kind","select-index",3);
    apply(extra,"create-extra.detail-open","activate");
    const auto pushed=evaluate("dialogStack").toVariant().toList();assert(pushed.size()==1);
    assert(pushed.first().toString().endsWith("/qml/NewPolyVoxDialog.qml"));page->setVisible(false);
    QQmlComponent dialogComponent(&engine,QUrl(pushed.first().toString()));
    auto dialog=qobject_cast<QQuickItem*>(dialogComponent.create());
    if(!dialog){qFatal("%s",qPrintable(dialogComponent.errorString()));}dialog->setParentItem(&root);dialog->setSize(root.size());
    QSignalSpy dialogCalls(dialog,SIGNAL(sendToScript(QVariant)));QTest::qWait(50);
    assert(createPolyvoxObject(dialog));
    for(const auto& axis:{"x","y","z"}){const auto id=QString("create-extra.polyvox.")+axis;apply(extra,id,"activate");apply(extra,id,"replace","8");}
    apply(extra,"create-extra.polyvox.preset","activate");apply(extra,"create-extra.polyvox.preset","select-index",1);
    assert(row(extra,"create-extra.polyvox.shape").value("currentIndex").toInt()==0);
    apply(extra,"create-extra.polyvox.add","activate");assert(dialogCalls.size()==1);
    const auto addMessage=createVariant(dialogCalls.first().first()).toMap();
    auto addResult=engine.globalObject().property("fromQml").call({engine.toScriptValue(addMessage)});
    if(addResult.isError()){qFatal("%s",qPrintable(addResult.toString()+"\n"+addResult.property("stack").toString()));}
    assert(evaluate("dialogStack.length").toInt()==0);delete dialog;page->setVisible(true);
    // This transform remains an explicit properties-application endpoint. The
    // dialog-created entity/initial cuboid and texture URLs remain original.
    assert(nativeVoxel.edit(nativeVoxel.entityId(),{{"name",QString(32,'a').prepend("e2e-")+"-voxel"},
        {"position",QVariantMap{{"x",0},{"y",1},{"z",-2}}},{"dimensions",QVariantMap{{"x",1},{"y",1},{"z",1}}}}));
    assert(nativeVoxel.finishAdd());settingsReceipt["receivedBeforeTools"]=page->property("e2eSettingsReceived").toBool();
    const auto addCommands=evaluate("deletedCommands.splice(0,deletedCommands.length)").toVariant().toList();
    auto listUpdate=backend.property("handle").call({evaluate("({method:'nativeCreate.refresh',params:{}})")});
    if(listUpdate.isError()){qFatal("%s",qPrintable(listUpdate.toString()));}
#endif
    apply(normal,"create.tab.3","activate");assert(page->property("currentTab").toInt()==3);
    assert(page->property("e2eSettingsReceived").toBool());settingsReceipt["afterReply"]=true;
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    assert(createVoxelPage(page)==page);
    // The same full original NativeCreate page with valid settings/tab/shape
    // still cannot qualify through either foreign file or qrc provenance.
    const auto actualToolSettings=createVariant(page->property("voxelSettings"));
    for(const auto& foreignUrl:{QUrl::fromLocalFile(path+"/foreign/system/create/qml/NativeCreate.qml"),
            QUrl("qrc:///scripts/system/create/qml/NativeCreate.qml")}){
        QQmlComponent foreignComponent(&engine);
        foreignComponent.setData(source("scripts/system/create/qml/NativeCreate.qml").toUtf8(),foreignUrl);
        auto foreign=qobject_cast<QQuickItem*>(foreignComponent.create());
        if(!foreign){qFatal("%s",qPrintable(foreignComponent.errorString()));}foreign->setParentItem(&root);foreign->setSize(root.size());
        foreign->setProperty("currentTab",3);
        const QVariant reply=QVariantMap{{"method","nativeCreate.settings"},{"params",actualToolSettings}};
        assert(QMetaObject::invokeMethod(foreign,"fromScript",Q_ARG(QVariant,reply)));
        assert(createPage(foreign)==foreign && foreign->property("e2eSettingsReceived").toBool());
        std::function<void(QQuickItem*)> rejectForeign=[&](QQuickItem* item){assert(!createVoxelPage(item) && createVoxelControlId(item).isEmpty());
            for(auto child:item->childItems()){rejectForeign(child);}};
        rejectForeign(foreign);delete foreign;
    }
#endif
    const auto baseline=row(tools,"create-voxel.mode").value("settings").toObject();assert(baseline.value("createAppMode")==QJsonValue("object"));
    auto choose=[&](const QString& id,int index){apply(tools,id,"activate");apply(tools,id,"select-index",index);assert(row(tools,id).value("currentIndex").toInt()==index);};
    choose("create-voxel.mode",1);choose("create-voxel.shape",2);choose("create-voxel.dynamics",0);choose("create-voxel.pointer",0);
    apply(tools,"create-voxel.remove","activate");assert(row(tools,"create-voxel.remove").value("checked").toBool());
    for(const auto& suffix:{"diameter","reach"}){const auto id="create-voxel."+QString(suffix);apply(tools,id,"activate");apply(tools,id,"replace","0.5");}
    apply(tools,"create-voxel.apply","activate");
    QQuickItem* actualApply=nullptr;
    std::function<void(QQuickItem*)> findApply=[&](QQuickItem* item){if(createVoxelControlId(item)=="create-voxel.apply"){assert(!actualApply);actualApply=item;}for(auto child:item->childItems()){findApply(child);}};
    findApply(&root);assert(actualApply);
    assert(originalCreateVoxelInput(actualApply,&window,"create-voxel.apply","activate",{},pointer).value("performed").toBool());drain();
    const auto measured=row(tools,"create-voxel.mode").value("settings").toObject();
    assert(measured.value("voxelSphereSize").toDouble()==.5 && measured.value("voxelEditMode")==QJsonValue("cube") && measured.value("voxelRemove").toBool());
    auto stroke=backend.property("stroke").call();if(stroke.isError()){qFatal("%s",qPrintable(stroke.toString()+"\n"+stroke.property("stack").toString()));}
    const auto changed=QJsonObject::fromVariantMap(stroke.toVariant().toMap());
    #ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    if(nativeVoxel.ignored()){
        assert(changed.value("calls").toArray().isEmpty() && changed.value("strokes").toArray().isEmpty());
        int count=0;for(const auto& value:changed.value("volume").toArray()){count+=value.toInt()!=0;}assert(count==64);
    }else{
#endif
    assert(changed.value("calls").toArray().size()==1 && changed.value("strokes").toArray().size()==1 && changed.value("remainingTimers").toArray().isEmpty());
    const auto mutation=changed.value("calls").toArray().first().toObject();assert(mutation.value("value").toInt()==0);
    assert(mutation.value("low").toObject()==QJsonObject({{"x",2},{"y",2},{"z",3}}));
    assert(mutation.value("size").toObject()==QJsonObject({{"x",4},{"y",4},{"z",4}}));
    int nonzero=0;for(const auto& value:changed.value("volume").toArray()){nonzero+=value.toInt()!=0;}assert(nonzero==16);
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    }
    nativeVoxel.observe("after-original-stroke");
#endif
    // Original tool settings are restored through the same real normal route.
    choose("create-voxel.shape",0);apply(tools,"create-voxel.remove","activate");
    apply(tools,"create-voxel.diameter","activate");apply(tools,"create-voxel.diameter","replace","0.3");apply(tools,"create-voxel.apply","activate");choose("create-voxel.mode",0);
    const auto restored=row(tools,"create-voxel.mode").value("settings").toObject();assert(restored==baseline);
    // Hold the actual original token, then change geometry or original Qt hit
    // ownership. None of these refusals may reach the original touch sender.
    const auto held=tools.observe(&root,&window),button=row(tools,"create-voxel.mode");
    QJsonObject heldCommand{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"instance",held.value("instance")},{"generation",held.value("generation")},
        {"sequence",held.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",held.value("elapsedMs")},
        {"controlId","create-voxel.mode"},{"controlToken",button.value("token")},{"action","activate"}};
    const auto originalPointers=pointers;
    page->setX(page->x()+2);assert(row(tools,"create-voxel.mode").value("token")!=button.value("token"));
    assert(!tools.apply(&root,&window,heldCommand,pointer).value("performed").toBool());page->setX(page->x()-2);
    page->setEnabled(false);assert(!tools.apply(&root,&window,heldCommand,pointer).value("performed").toBool());page->setEnabled(true);
    QQmlComponent overlayComponent(&engine);overlayComponent.setData("import QtQuick 2.7;Rectangle {color:'red';MouseArea {anchors.fill:parent}}",{});
    auto overlay=qobject_cast<QQuickItem*>(overlayComponent.create());assert(overlay);overlay->setParentItem(&root);overlay->setSize(root.size());overlay->setZ(999);
    assert(!tools.apply(&root,&window,heldCommand,pointer).value("performed").toBool());delete overlay;
    QQuickItem clip(&root);clip.setClip(true);clip.setSize(QSizeF(1,1));page->setParentItem(&clip);
    assert(!tools.apply(&root,&window,heldCommand,pointer).value("performed").toBool());page->setParentItem(&root);
    assert(pointers==originalPointers);
    QJsonArray counterexamples{"moved-token","disabled","higher-overlay","clipped"};
    QJsonObject output{{"settingsReceipt",settingsReceipt},{"before",baseline},{"configured",measured},{"restored",restored},{"stroke",changed},{"pointerCalls",pointers},{"counterexamples",counterexamples}};
#ifdef OVERTE_CREATE_VOXEL_NATIVE_JOIN
    output["sourceUrlCounterexamples"]=QJsonArray{"canonical-file-directory","file-directory-with-slash","qrc-directory-spellings","foreign-file-context","foreign-qrc-context","foreign-voxel-file-context","foreign-voxel-qrc-context"};
    output["addCommands"]=QJsonArray::fromVariantList(addCommands);
    output["addCuboids"]=QJsonArray::fromVariantList(evaluate("addCuboids").toVariant().toList());
    output["dialogEvents"]=QJsonArray::fromVariantList(evaluate("dialogEvents").toVariant().toList());
    nativeVoxel.observe("settings-restored");
    apply(normal,"create.tab.2","activate");
    apply(normal,"create.delete","activate");
    // Same normal editor Delete, actual Qt deferred destruction and original
    // weak observers; the scene-release endpoint remains an explicit host seam.
    QTest::qWait(100);nativeVoxel.observe("delete-quiet");
    QElapsedTimer quiet;quiet.start();
    while(quiet.elapsed()<3100){QTest::qWait(100);nativeVoxel.observe("delete-quiet");}
    output["nativeJoin"]=QJsonArray::fromVariantList(nativeVoxel.history());
    output["deleteCommands"]=QJsonArray::fromVariantList(evaluate("deletedCommands").toVariant().toList());
    output["deleteLists"]=QJsonArray::fromVariantList(evaluate("deletedLists").toVariant().toList());
#endif
    delete page;QTextStream(stdout)<<QJsonDocument(output).toJson(QJsonDocument::Compact)<<'\n';
}
