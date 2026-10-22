// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QGuiApplication>
#include <QQuickWindow>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QtTest/QTest>
#include <QPointer>
#include <QDateTime>
#include <QMouseEvent>
#include <QTouchDevice>
#include <QTouchEvent>
#include <QWheelEvent>
#include <QJsonArray>
#include <map>
#include <cmath>
#include <cassert>
#include <cstdio>
#include <PointerEvent.h>
#include "NormalScriptControls.h"
#include "NormalAudioControls.h"
#include "NormalEmoteControls.h"
#include "ActualEmoteInput.inc"

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);assert(argc==3);
    QQmlEngine engine;const QUrl source=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2]));
    QQmlComponent component(&engine,source);auto page=qobject_cast<QQuickItem*>(component.create());
    if(!page)qFatal("%s",qPrintable(component.errorString()));
    QQuickWindow window;window.resize(480,706);window.show();window.requestActivate();
    page->setParentItem(window.contentItem());page->setSize(QSizeF(480,706));QTest::qWait(40);
    OffscreenQmlSurface surface(page,&window);QSignalSpy events(page,SIGNAL(sendToScript(QVariant)));
    QQuickItem* grid{nullptr};
    std::function<void(QQuickItem*)> find=[&](QQuickItem* item){
        if(overte::e2e::emoteControlId(item)=="emote.grid")grid=item;
        for(auto child:item->childItems())find(child);
    };
    find(page);assert(grid && grid->objectName().isEmpty()); // Original lexical id, no product changes.
    assert(overte::e2e::emoteControlId(page)=="emote.page");
    auto buttonFor=[&](const QString& name){
        QQuickItem* found{nullptr};
        std::function<void(QQuickItem*)> walk=[&](QQuickItem* item){
            if(overte::e2e::emoteControlId(item)=="emote.play."+name)found=item;
            for(auto child:item->childItems())walk(child);
        };
        walk(page);return found;
    };
    const auto names=overte::e2e::emoteNames();int pointerCalls=0,scrollCalls=0;
    auto input=[&](QQuickItem* item,const QString& id,const QString& action,const QString& direction=QString()){
        std::function<bool(QQuickItem*)> pointerClick=[&](QQuickItem* target){++pointerCalls;return sendPointerClick(target,&surface);};
        std::function<bool(QQuickItem*,const QPointF&,int)> pointerScroll=[&](QQuickItem* target,const QPointF& point,int delta){
            ++scrollCalls;return sendPointerScroll(target,&surface,point,delta);
        };
        return originalEmoteInput(item,&window,id,action,{{"direction",direction}},pointerClick,pointerScroll);
    };
    for(const auto& name:names){
        auto button=buttonFor(name);assert(button);
        const auto id="emote.play."+name;assert(overte::e2e::emoteControlId(button)==id);
        auto before=events.count();
        const auto delivered=input(button,id,"activate").value("performed").toBool();
        if(!delivered){QJsonObject row;overte::e2e::appendEmoteControlObservation(row,button,id);
            const auto rect=overte::e2e::emoteVisibleRect(button);
            fprintf(stderr,"Input %s failed after %d pointers, row %s; owns %d; visible %g,%g,%g,%g\n",qPrintable(name),pointerCalls,
                QJsonDocument(row).toJson(QJsonDocument::Compact).constData(),
                overte::e2e::NormalControlUi::ownsPoint(button,&window,rect.center()),rect.x(),rect.y(),rect.width(),rect.height());abort();}
        QCoreApplication::processEvents();assert(events.count()==before+1);
        const auto actual=events.last().first().toMap();assert(actual.value("method")=="phoneEmote.play" && actual.value("name")==name);
    }
    assert(pointerCalls==10 && scrollCalls==0);
    {
        QQuickItem blocker(page);blocker.setZ(50);blocker.setSize(page->size());
        const auto calls=pointerCalls;
        assert(!input(buttonFor("Crying"),"emote.play.Crying","activate").value("performed").toBool());
        assert(pointerCalls==calls); // Real higher stacking sibling remains an occlusion.
    }

    const auto beforeScroll=events.count();window.resize(480,250);page->setSize(QSizeF(480,250));QTest::qWait(40);
    const auto originalY=grid->property("contentY").toDouble();
    assert(input(grid,"emote.grid","scroll","down").value("performed").toBool());QTest::qWait(400);
    const auto afterDown=grid->property("contentY").toDouble();
    assert(std::isfinite(afterDown) && scrollCalls==1);
    // Actual surface delivery may be ignored by the hosted Flickable. Preserve
    // that measurement: an ACK never proves scrolling or feature success.
    fprintf(stderr,"Actual surface Scroll delivered: originalY=%g afterDownY=%g\n",originalY,afterDown);
    assert(events.count()==beforeScroll); // Scroll never substitutes a Play callback.
    assert(input(grid,"emote.grid","scroll","up").value("performed").toBool());QTest::qWait(400);
    assert(std::isfinite(grid->property("contentY").toDouble()) && scrollCalls==2);
    assert(!input(grid,"emote.grid","activate").value("performed").toBool());
    assert(!input(page,"emote.page","activate").value("performed").toBool());
    auto button=buttonFor("Crying");assert(button);
    const auto calls=pointerCalls;auto token=overte::e2e::emoteControlSource(button,"emote.play.Crying");
    window.resize(500,250);page->setSize(QSizeF(500,250));QTest::qWait(40);
    assert(overte::e2e::emoteControlSource(button,"emote.play.Crying")!=token);
    page->setVisible(false);assert(!input(button,"emote.play.Crying","activate").value("performed").toBool());
    assert(pointerCalls==calls);delete page;
    qInfo("PASS actual Pico Emote QML, ten original pointer inputs and two original surface Scroll events; no animation/device verdict");
}
