// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/LifecycleBackgroundHistory.h"
#include "tests/device/native/LifecycleUiObservation.h"
#include <ui/NativeFieldInput.h>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickWindow>
#include <QSaveFile>
#include <QJsonDocument>
#include <QtTest/QTest>
#include <cassert>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);const bool enabled=app.arguments().contains("--testScript");
    const auto source=QUrl::fromLocalFile(app.arguments().at(app.arguments().size()-2));QQmlEngine engine;
    QQuickWindow window;window.resize(640,900);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(640,900));
    QQuickItem loader(&root);loader.setObjectName("loader");loader.setSize(root.size());
    QQmlComponent component(&engine,source);auto page=qobject_cast<QQuickItem*>(component.create());
    if (!page) { qFatal("%s",qPrintable(component.errorString())); }
    page->setParentItem(&loader);page->setSize(loader.size());QTest::qWait(50);
    auto field=page->findChild<QQuickItem*>("chatMessageInput");assert(field);
    const QString run(32,'a');int reads{0};bool available{true};quint64 keyboardSequence{0};
    overte::e2e::LifecycleUiObservation ui({{"chat",source}});
    auto observe=[&](const QString& actual) {
        assert(actual==run);++reads;
        if (!available) { return QVariantMap(); }
        // The actual Qt Chat field/weak identities are original. Physical VR
        // entity visibility is an explicit native boundary in this host test.
        const QVariantMap keyboard{{"available",true},{"backend","native-vr-entity-keyboard"},
            {"instance",QString(32,'b')},{"sequence",static_cast<qulonglong>(++keyboardSequence)},
            {"created",true},{"enabled",true},{"raised",field->hasActiveFocus()},{"visible",field->hasActiveFocus()},
            {"keys",QVariantList{QVariantMap{{"pressed",false}}}}};
        return ui.observe(&root,&window,true,false,actual,keyboard);
    };
    overte::e2e::LifecycleBackgroundHistory history(&root,observe);
    auto command=[&](const QString& operation,const QVariantMap& prior=QVariantMap()) {
        QVariantMap value{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"action","feature-lifecycle-background"},{"operation",operation},{"runId",run}};
        if (operation!="observe") { value["ownerInstance"]=prior["instance"];value["intentSequence"]=prior["lastIntentSequence"].toULongLong()+1; }
        return value;
    };
    const auto firstCommand=command("observe");auto first=history.request(firstCommand);
    if (!enabled) { assert(first.isEmpty() && reads==0);delete page;return 0; }
    assert(!first.isEmpty() && !first["active"].toBool() && first["available"].toBool());
    {
        overte::e2e::LifecycleBackgroundHistory empty(&root,observe);
        auto baseline=empty.request(command("observe"));auto armed=empty.request(command("arm",baseline));
        assert(armed["performed"].toBool() && armed["available"].toBool() && armed["timerActive"].toBool());
        const auto row=armed["frames"].toList().first().toMap();
        assert(row["editor"].toMap()["text"].toString().isEmpty() && !row["editor"].toMap()["focused"].toBool());
        assert(!row["keyboard"].toMap()["visible"].toBool());
        auto released=empty.request(command("release",armed));assert(released["released"].toBool() && !released["timerActive"].toBool());
    }
    reads=0;
    QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,field->mapToScene(QPointF(8,8)).toPoint());
    QCoreApplication::processEvents();assert(field->hasActiveFocus());
    assert(overte::ui::replaceFocusedField(field,&window,"reply-"+run));
    QTest::qWait(20);assert(field->property("text")=="reply-"+run);
    const auto arm=command("arm",first);auto active=history.request(arm);
    assert(active["performed"].toBool() && active["active"].toBool() && active["available"].toBool());
    auto frames=active["frames"].toList();assert(frames.size()==1);
    const auto identity=frames.first().toMap()["editor"].toMap();assert(identity["kind"]=="chat");
    assert(history.request(arm)==active);assert(reads==1); // Exact nonce never resamples.
    QTest::qWait(300);auto observed=history.request(command("observe"));
    frames=observed["frames"].toList();assert(frames.size()>=3);
    assert(frames.first()==active["frames"].toList().first());
    for (const auto& item:frames) {
        const auto frame=item.toMap();assert(frame["editor"].toMap()["id"]==identity["id"]);
        assert(frame["applicationState"].toString()=="active");
        assert(frame["uiSequence"].toULongLong()>0 && frame["keyboard"].toMap()["sequence"].toULongLong()>0);
    }
    // A fake notification cannot create a background fact: the helper compares
    // it to actual QGuiApplication state before capturing anything.
    assert(QGuiApplication::applicationState()==Qt::ApplicationActive);
    app.applicationStateChanged(Qt::ApplicationHidden);
    auto invalid=history.request(command("observe"));assert(!invalid["available"].toBool() && !invalid["active"].toBool());
    auto released=history.request(command("release",invalid));assert(released["performed"].toBool() && released["released"].toBool());
    assert(released["frames"]==invalid["frames"]);assert(!released["available"].toBool());
    QVariantList packets;
    for (const auto& pair:{qMakePair(QString("observe"),first),qMakePair(QString("arm"),active),
            qMakePair(QString("observe"),observed),qMakePair(QString("observe"),invalid),qMakePair(QString("release"),released)}) {
        packets.append(QVariantMap{{"operation",pair.first},{"packet",pair.second}});
    }
    QSaveFile output(app.arguments().last());assert(output.open(QIODevice::WriteOnly));
    assert(output.setPermissions(QFile::ReadOwner|QFile::WriteOwner));
    const auto bytes=QJsonDocument::fromVariant(packets).toJson(QJsonDocument::Compact);
    assert(output.write(bytes)==bytes.size() && output.commit());
    assert(!history.request(command("arm",released))["performed"].toBool());
    delete page;QCoreApplication::processEvents();
    qInfo("PASS actual Qt Chat field/IME/weak identities, timer history, nonce retention and real-state mismatch; VR/OS background remains an explicit boundary");
}
