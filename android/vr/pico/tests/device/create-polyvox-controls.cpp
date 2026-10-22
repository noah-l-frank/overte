// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual original PolyVox dialog/controls and NativeFieldInput. Only HMD/sound,
// host window and script/domain delivery are substituted, separately declared.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QSignalSpy>
#include <QTest>
#include <QTextStream>
#include <QJsonArray>
#include <QJsonDocument>
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
#include "PathUtils.h"
#include "actual-create-extra-input.inc"

struct ActualKeyCounter : QObject {
    int presses{0};
    bool eventFilter(QObject*,QEvent* event) override {
        if(event->type()==QEvent::KeyPress){++presses;}return false;
    }
};

int main(int argc,char**argv) {
    QGuiApplication app(argc,argv);using namespace overte::e2e;
    NormalControlUi controls(NormalControlUi::Surface::CreateExtra);
    if (!app.arguments().contains("--testScript")) {assert(controls.observe(nullptr,nullptr).isEmpty());return 0;}
    const auto path=app.arguments().at(app.arguments().size()-2),imports=app.arguments().last();
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    QQmlEngine engine;engine.addImportPath(path+"/interface/resources/qml");engine.addImportPath(imports);
    QQmlComponent hmd(&engine);hmd.setData("import QtQuick 2.7;QtObject {property bool active:false}",{});
    QScopedPointer<QObject> actor(hmd.create());assert(actor);engine.rootContext()->setContextProperty("HMD",actor.data());
    QQuickRenderControl renderControl;QQuickWindow window(&renderControl);window.resize(600,700);
    window.contentItem()->setSize(QSizeF(600,700));
    QQuickItem root(window.contentItem());root.setSize(QSizeF(600,700));
    auto load=[&](const QString& file){
        QQmlComponent component(&engine,QUrl::fromLocalFile(path+"/scripts/system/create/qml/"+file));
        auto page=qobject_cast<QQuickItem*>(component.create());if(!page){qFatal("%s",qPrintable(component.errorString()));}
        page->setParentItem(&root);page->setSize(root.size());QTest::qWait(50);return page;
    };
    auto page=load("NewPolyVoxDialog.qml");
    auto observe=[&]{return controls.observe(&root,&window);};
    auto row=[&](const QString& id){
        const auto actual=observe();assert(actual.value("ready").toBool());
        for(const auto& value:actual.value("controls").toArray()){if(value.toObject().value("id")==id){return value.toObject();}}
        fprintf(stderr,"missing original control: %s\n",qPrintable(id));abort();return QJsonObject();
    };
    auto request=[&](const QString& id,const QString& action,const QJsonValue& value=QJsonValue()){
        const auto item=row(id),actual=observe();QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",actual.value("instance")},{"generation",actual.value("generation")},
            {"sequence",actual.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",actual.value("elapsedMs")},
            {"controlId",id},{"controlToken",item.value("token")},{"action",action}};
        if(action=="replace"){command["text"]=value;}else if(action=="select-index"){command["index"]=value;}return command;
    };
    OffscreenQmlSurface surface(&root,&window);
    int clicks{0};auto pointer=[&](QQuickItem* item){++clicks;const auto sent=sendPointerClick(item,&surface);
        QCoreApplication::processEvents();return sent;};
    auto apply=[&](const QJsonObject& command){return controls.apply(&root,&window,command,pointer);};
    auto activate=[&](const QString& id){const auto result=apply(request(id,"activate"));
        if(!result.value("performed").toBool()){qFatal("original pointer refused: %s",qPrintable(id));}};
    auto find=[&](const QString& id){QQuickItem* found=nullptr;
        std::function<void(QQuickItem*)> walk=[&](QQuickItem* item){if(createExtraControlId(item)==id){assert(!found);found=item;}
            for(auto child:item->childItems()){walk(child);}};walk(&root);assert(found);return found;};
    // The actual NativeCreate detail selector emits the unchanged original
    // dialog request. Script/Tablet loading itself remains a declared boundary.
    const auto firstPage=row("create-extra.polyvox.page");const auto firstContext=createPolyvoxObject(page).context;
    delete page;page=load("NativeCreate.qml");QSignalSpy nativeCalls(page,SIGNAL(sendToScript(QVariant)));
    activate("create-extra.detail-kind");
    // Qt's original popup overlay is above ordinary content. Put the foreign
    // sibling above its actual z, rather than assuming a nominal overlay z.
    qreal highest=0;for(auto child:window.contentItem()->childItems()){highest=std::max(highest,child->z());}
    auto foreignPopup=new QQuickItem(window.contentItem());foreignPopup->setSize(QSizeF(600,700));foreignPopup->setZ(highest+1);
    ActualKeyCounter keys;window.installEventFilter(&keys);const auto beforeKeys=keys.presses;
    const auto blockedIndex=row("create-extra.detail-kind").value("currentIndex");
    assert(!apply(request("create-extra.detail-kind","select-index",3)).value("performed").toBool());
    assert(row("create-extra.detail-kind").value("currentIndex")==blockedIndex);
    foreignPopup->setEnabled(false);assert(!apply(request("create-extra.detail-kind","select-index",3)).value("performed").toBool());
    assert(keys.presses==beforeKeys);
    delete foreignPopup;
    assert(apply(request("create-extra.detail-kind","select-index",3)).value("performed").toBool());
    assert(row("create-extra.detail-kind").value("currentIndex")==3);activate("create-extra.detail-open");
    assert(nativeCalls.size()==1);const auto original=createVariant(nativeCalls.first().first()).toMap();
    assert(original.value("method")=="newEntityButtonClicked");
    assert(createVariant(original.value("params")).toMap().value("buttonName")=="newPolyVoxButton");
    delete page;page=load("NewPolyVoxDialog.qml");QSignalSpy polyvoxCalls(page,SIGNAL(sendToScript(QVariant)));
    assert(row("create-extra.polyvox.page").value("profile")=="original-new-polyvox-v1");
    assert(!row("create-extra.polyvox.add").value("enabled").toBool());
    // All three real IntValidator fields receive original Qt focus/key input.
    for(const auto& axis:{"x","y","z"}){
        const auto id=QString("create-extra.polyvox.")+axis;assert(row(id).value("text")=="20");activate(id);
        assert(apply(request(id,"replace","8")).value("performed").toBool());assert(row(id).value("text")=="8");
    }
    activate("create-extra.polyvox.preset");assert(apply(request("create-extra.polyvox.preset","select-index",1)).value("performed").toBool());
    assert(row("create-extra.polyvox.preset").value("currentIndex")==1);
    assert(row("create-extra.polyvox.shape").value("currentIndex")==0 && row("create-extra.polyvox.shape").value("count")==4);
    assert(row("create-extra.polyvox.add").value("enabled").toBool());
    // A source-qualified paintless original parent permits its negative-z
    // child. Actual unknown/opaque surfaces still block before any input.
    auto button=find("create-extra.polyvox.add");auto parent=button->parentItem();
    assert(button->z()<0 && parent->inherits("QQuickRow") && !parent->flags().testFlag(QQuickItem::ItemHasContents));
    const auto blocked=[&]{const auto before=clicks;assert(!apply(request("create-extra.polyvox.add","activate")).value("performed").toBool());
        assert(before==clicks && polyvoxCalls.size()==0);};
    parent->setFlag(QQuickItem::ItemHasContents,true);blocked();parent->setFlag(QQuickItem::ItemHasContents,false);
    auto foreign=new QQuickItem(window.contentItem());foreign->setZ(1000);foreign->setSize(QSizeF(600,700));
    foreign->setAcceptTouchEvents(true);blocked();foreign->setEnabled(false);blocked();foreign->setVisible(false);
    assert(NormalControlUi::ownsPoint(button,&window,button->mapToScene(QPointF(button->width()/2,button->height()/2)),createExtraDecoration));
    delete foreign;
    button->setEnabled(false);blocked();button->setEnabled(true);
    const auto token=row("create-extra.polyvox.add").value("token");button->setX(button->x()+1);
    assert(row("create-extra.polyvox.add").value("token")!=token);button->setX(button->x()-1);
    const auto stale=request("create-extra.polyvox.add","activate");activate("create-extra.polyvox.add");
    assert(polyvoxCalls.size()==1);const auto message=createVariant(polyvoxCalls.first().first()).toMap();assert(message.value("method")=="newPolyVoxDialogAdd");
    const auto params=createVariant(message.value("params")).toMap();for(const auto& axis:{"X","Y","Z"}){assert(params.value(QString("volumeSize")+axis)=="8");}
    assert(params.value("initialShapeIndex").toInt()==0 && params.value("surfaceStyleIndex").toInt()==3);
    assert(params.value("xTextureURL").toString().startsWith("qrc:///serverless/Textures/"));
    const auto count=clicks;assert(!apply(stale).value("performed").toBool() && clicks==count && polyvoxCalls.size()==1);
    const auto pageId=row("create-extra.polyvox.page").value("pageId");const auto context=createPolyvoxObject(page).context;
    const auto before=observe().value("createExtraUiInventory").toObject().value("pages").toArray();assert(before.size()==2);
    assert(before[0].toObject().value("windowId")==before[1].toObject().value("windowId"));
    delete page;
    const auto retired=observe().value("createExtraUiInventory").toObject().value("pages").toArray();
    assert(!retired[1].toObject().value("pageAlive").toBool());
    assert(retired[1].toObject().value("contextAlive").toBool()==!context.isNull());
    assert(retired[0].toObject().value("contextAlive").toBool()==!firstContext.isNull());
    page=load("NewPolyVoxDialog.qml");QSignalSpy nativeBranch(page,SIGNAL(sendToScript(QVariant)));
    auto branch=[&](const QString& id,const QString& action,const QJsonObject& command=QJsonObject()){
        return originalCreateExtraInput(find(id),&window,id,action,command,pointer).value("performed").toBool();};
    for(const auto& axis:{"x","y","z"}){
        const auto id=QString("create-extra.polyvox.")+axis;assert(branch(id,"activate"));assert(branch(id,"replace",{{"text","8"}}));}
    assert(branch("create-extra.polyvox.preset","activate"));assert(branch("create-extra.polyvox.preset","select-index",{{"index",1}}));
    assert(branch("create-extra.polyvox.add","activate") && nativeBranch.size()==1);
    delete page;
    page=load("NewPolyVoxDialog.qml");QSignalSpy cancellation(page,SIGNAL(sendToScript(QVariant)));
    assert(branch("create-extra.polyvox.cancel","activate") && cancellation.size()==1);
    const auto cancel=createVariant(cancellation.first().first()).toMap();assert(cancel.value("method")=="newPolyVoxDialogCancel");delete page;
    QTextStream(stdout)<<QJsonDocument(QJsonObject{{"detail",QJsonObject::fromVariantMap(original)},
        {"polyvox",QJsonObject::fromVariantMap(message)},{"cancel",QJsonObject::fromVariantMap(cancel)}}).toJson(QJsonDocument::Compact)<<'\n';
}
