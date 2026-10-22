// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "ActualMenuBinding.h"
#include "tests/device/native/NormalControlUi.h"
#include "tests/device/native/NormalViewMenuControls.h"
#include <QApplication>
#include <QDebug>
#include <QDynamicPropertyChangeEvent>
#include <QLoggingCategory>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QtTest/QTest>
#include <cassert>
Q_LOGGING_CATEGORY(uiLogging,"view.menu.host.fixture")
#include "ActualMenuBinding.inc"
#include "ActualViewInput.inc"

int main(int argc,char** argv) {
    QApplication app(argc,argv);
    using namespace overte::e2e;
    if (!app.arguments().contains("--testScript")) {assert(!ViewMenuContext{}.valid());return 0;}
    const auto path=app.arguments().last();PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");
    PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    qmlRegisterModule("TabletScriptingInterface",1,0);
    QQmlEngine engine;engine.addImportPath(path+"/interface/resources/qml");
    QQmlComponent services(&engine);
    services.setData("import QtQuick 2.7; QtObject { property bool screenSpaceMode:false;"
        " function playButtonClickSound() {} function playSound(value) {} }",QUrl("qrc:/view-menu-services.qml"));
    QScopedPointer<QObject> tablet(services.create());assert(tablet);
    engine.rootContext()->setContextProperty("tabletRoot",tablet.data());
    engine.rootContext()->setContextProperty("Tablet",tablet.data());
    engine.rootContext()->setContextProperty("TabletEnums",QVariantMap{{"ButtonClick",0},{"ButtonHover",1}});
    QQuickWindow window;window.resize(900,1000);window.show();window.requestActivate();
    QQmlComponent page(&engine,PathUtils::qmlUrl("hifi/tablet/TabletMenu.qml"));
    if (page.isError()) {qWarning()<<page.errors();return 2;}
    auto root=qobject_cast<QQuickItem*>(page.create());assert(root);root->setParentItem(window.contentItem());
    auto create=[&](const QString& url) {
        QQmlComponent component(&engine,PathUtils::qmlUrl(url));auto result=component.create();
        if (!result) {qWarning()<<component.errors();}assert(result);result->setParent(root);return result;
    };
    auto menu=root->property("rootMenu").value<QObject*>();assert(menu);
    auto view=create("controls/WrappedMenu.qml");view->setProperty("title","View");
    auto first=create("controls/WrappedMenuItem.qml"),third=create("controls/WrappedMenuItem.qml");
    first->setProperty("tabletExclusive",true);third->setProperty("tabletExclusive",true);
    QMenu nativeView("View");QActionGroup group(&nativeView);group.setExclusive(true);
    auto nativeFirst=nativeView.addAction("First Person"),nativeThird=nativeView.addAction("Third Person");
    for (auto action:{nativeFirst,nativeThird}) {action->setCheckable(true);group.addAction(action);}
    nativeFirst->setChecked(true);
    bindActionToQmlAction(first,nativeFirst,menu);bindActionToQmlAction(third,nativeThird,menu);
    auto menuData=new MenuUserData(nativeView.menuAction(),view,menu);
    auto append=[](QObject* parent,const char* method,QObject* value) {
        assert(QMetaObject::invokeMethod(parent,method,Q_ARG(QVariant,QVariant::fromValue(value))));
    };
    append(view,"addItemWrap",first);append(view,"addItemWrap",third);append(menu,"addMenuWrap",view);
    ViewMenuContext context{nativeView.menuAction(),nativeFirst,nativeThird,true};assert(context.valid());fixtureViewContext=context;
    assert(QMetaObject::invokeMethod(root,"setRootMenu",Q_ARG(QVariant,QVariant::fromValue(menu)),Q_ARG(QVariant,QVariant(""))));
    auto find=[&](const QString& id) {
        QQuickItem* result{nullptr};
        for (int attempt=0;attempt<30 && !result;++attempt) {
            std::function<void(QQuickItem*)> visit=[&](QQuickItem* item) {
                if (viewMenuControlId(item,context)==id && !NormalControlUi::visibleRect(item,&window).isEmpty()) {
                    assert(!result);result=item;
                }
                for (auto child:item->childItems()) {visit(child);}
            };visit(root);
            if (!result) {QTest::qWait(20);}
        }
        if (!result) {
            std::function<void(QQuickItem*)> inspect=[&](QQuickItem* item) {
                if (QString(item->metaObject()->className()).startsWith("TabletMenuItem")) {
                    const auto source=viewMenuSource(item);
                    qWarning()<<"missing"<<id<<item->metaObject()->className()<<item->property("text")<<source
                        <<(source ? source->property("user_data") : QVariant())<<context.valid()<<viewMenuControlId(item,context)
                        <<NormalControlUi::visibleRect(item,&window);
                }
                for (auto child:item->childItems()) {inspect(child);}
            };inspect(root);
        }
        assert(result);return result;
    };
    auto click=[&](QQuickItem* item) {
        QTest::qWait(350);
        const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
        assert(NormalControlUi::ownsPoint(item,&window,point));
        const auto id=viewMenuControlId(item,context);
        auto result=originalViewInput(item,&window,id,"activate",[&](QQuickItem* actual){
            assert(actual==item);QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,point.toPoint());return true;
        });assert(result["performed"].toBool());QTest::qWait(350);
    };
    auto viewItem=find("view-menu.view");QJsonObject observation;
    appendViewMenuObservation(observation,viewItem,"view-menu.view",context);assert(observation["inputReady"].toBool());
    assert(viewMenuBinding(view,nativeView.menuAction()));assert(!viewMenuBinding(view,nativeThird));
    click(viewItem);auto thirdItem=find("view-menu.third");
    appendViewMenuObservation(observation,thirdItem,"view-menu.third",context);assert(!observation["checked"].toBool() && observation["inputReady"].toBool());
    QSignalSpy actualThird(nativeThird,&QAction::triggered);click(thirdItem);
    if (actualThird.count()!=1) {fprintf(stderr,"third triggers=%d firstChecked=%d thirdChecked=%d qmlChecked=%d\n",actualThird.count(),nativeFirst->isChecked(),nativeThird->isChecked(),third->property("checked").toBool());}
    assert(actualThird.count()==1 && nativeThird->isChecked() && !nativeFirst->isChecked());
    appendViewMenuObservation(observation,thirdItem,"view-menu.third",context);assert(observation["checked"].toBool());
    auto firstItem=find("view-menu.first");QSignalSpy actualFirst(nativeFirst,&QAction::triggered);click(firstItem);
    assert(actualFirst.count()==1 && nativeFirst->isChecked() && !nativeThird->isChecked());
    int forbiddenPointers{0};
    const auto forbidden=[&](QQuickItem*){++forbiddenPointers;return true;};
    assert(!originalViewInput(thirdItem,&window,"view-menu.third","replace",forbidden)["performed"].toBool());
    assert(!originalViewInput(thirdItem,&window,"view-menu.third","activate",{})["performed"].toBool());
    fixtureViewContext.hmd=false;
    assert(!originalViewInput(thirdItem,&window,"view-menu.third","activate",forbidden)["performed"].toBool());
    fixtureViewContext=context;assert(forbiddenPointers==0);
    group.setExclusive(false);assert(viewMenuControlId(thirdItem,context).isEmpty());group.setExclusive(true);
    context.hmd=false;assert(viewMenuControlId(thirdItem,context).isEmpty());context.hmd=true;
    auto originalData=third->property("user_data");third->setProperty("user_data",first->property("user_data"));
    assert(viewMenuControlId(thirdItem,context).isEmpty());third->setProperty("user_data",originalData);
    nativeThird->setEnabled(false);appendViewMenuObservation(observation,thirdItem,"view-menu.third",context);
    assert(!observation["inputReady"].toBool());nativeThird->setEnabled(true);
    nativeThird->setVisible(false);appendViewMenuObservation(observation,thirdItem,"view-menu.third",context);
    assert(!observation["inputReady"].toBool());nativeThird->setVisible(true);
    third->setProperty("checked",true);appendViewMenuObservation(observation,thirdItem,"view-menu.third",context);
    assert(!observation["inputReady"].toBool());third->setProperty("checked",false);
    delete MenuUserData::forObject(nativeFirst);delete MenuUserData::forObject(nativeThird);delete menuData;
    delete root;
    qInfo()<<"PASS original VR menu delegates -> actual pointer -> deferred original QAction bridge and exclusive checked state; host menu/service/window seams";
}
