// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QChar>
#include <QBitArray>
#include "tests/device/native/SnapshotReviewObservation.h"
#include <QGuiApplication>
#include <QJsonDocument>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QtTest/QTest>
#include <QtTest/QSignalSpy>
#include <QPointer>
#include <ui/NativeFieldInput.h>
#include <cstdio>
#include <cassert>

// Native Snapshot/keyboard services and Android export are explicit host seams.
// The full original Review QML, contexts, controls and pointer events are real.
class SnapshotServices : public QObject {
    Q_OBJECT
public:
    Q_INVOKABLE QStringList getAvailableSnapshotFormats() const {return {"png","jpg","webp"};}
    Q_INVOKABLE QString getSnapshotFormat() const {return "png";}
    Q_INVOKABLE void setSnapshotFormat(const QString&) {}
    Q_INVOKABLE QString snapshotFileUrl(const QString&) const {return {};}
};
class KeyboardServices : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool use3DKeyboard MEMBER use3DKeyboard)
    Q_PROPERTY(bool raised MEMBER raised)
public:bool use3DKeyboard{true},raised{false};
};
#include "snapshot-review-originals-test.moc"

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);assert(argc>=3);
    QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[2])+"/interface/resources/qml");
    SnapshotServices snapshot;KeyboardServices keyboard;
    engine.rootContext()->setContextProperty("Snapshot",&snapshot);
    engine.rootContext()->setContextProperty("KeyboardScriptingInterface",&keyboard);
    QQuickWindow window;window.resize(800,1100);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(800,1100));
    const auto source=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]));
    auto capture=[&] {return overte::e2e::picoSnapshotReviewObservation(&root,&window);};
    if(!app.arguments().contains("--testScript")) {assert(capture().isEmpty());return 0;}
    const auto absent=capture();assert(absent.value("present")==false && absent.value("review").isNull());
    auto load=[&] {
        QQmlComponent component(&engine,source);auto page=qobject_cast<QQuickItem*>(component.create());
        if(!page) {qFatal("%s",qPrintable(component.errorString()));}
        page->setParent(&root);page->setParentItem(&root);page->setSize(root.size());QTest::qWait(30);return page;
    };
    auto page=load();const auto first=capture();assert(first.value("present")==true && first.value("snapshotReviewObservationVersion")==2);
    assert(first.value("review").toObject().value("componentUrl")==source.toString());
    assert(first.value("review").toObject().value("visible")==true);
    auto fromScript=[&](QVariantMap message) {
        message.insert("type","snapshot");assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,QVariant(message))));
        QCoreApplication::processEvents();
    };
    fromScript({{"action","captureSettings"},{"setting",true}});
    const auto initialized=capture().value("review").toObject();
    assert(initialized.value("mode")==1 && initialized.value("format")=="png" && initialized.value("captureSettingsLoaded")==true);
    auto field=page->findChild<QQuickItem*>("snapshotName");assert(field);
    assert(initialized.value("captureName")=="");
    QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,field->mapToScene(QPointF(field->width()/2,field->height()/2)).toPoint());
    assert(overte::ui::replaceFocusedField(field,&window,"parity-aaaaaaaaaaaaaaaa-animated"));
    assert(capture().value("review").toObject().value("captureName")=="parity-aaaaaaaaaaaaaaaa-animated");
    QSignalSpy outbound(page,SIGNAL(sendToScript(QVariant)));assert(outbound.isValid());outbound.clear();
    auto button=page->findChild<QQuickItem*>("snapshotCapture");assert(button && button->isEnabled());
    QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,button->mapToScene(QPointF(button->width()/2,button->height()/2)).toPoint());
    assert(outbound.size()==1 && outbound.at(0).at(0).toMap().value("action")=="takeSnapshot");
    // Synthetic script delivery is explicit; no capture effect is inferred from
    // that pointer receipt. Only original QML properties are read below.
    fromScript({{"action","clearPreviousImages"}});
    assert(capture().value("review").toObject().value("capturing")==true);
    page->setVisible(false);const auto hidden=capture();
    assert(hidden.value("present")==true && hidden.value("review").toObject().value("visible")==false
        && hidden.value("review").toObject().value("capturing")==true);
    std::puts(QJsonDocument(hidden).toJson(QJsonDocument::Compact).constData());
    page->setVisible(true);fromScript({{"action","captureStatus"},{"phase","cancelled"}});
    assert(capture().value("review").toObject().value("capturing")==false);
    auto duplicate=load();assert(capture().isEmpty());delete duplicate;
    auto foreign=new QQuickItem(&root);foreign->setObjectName("snapshotReview");assert(capture().isEmpty());delete foreign;
    QQuickWindow other;assert(overte::e2e::picoSnapshotReviewObservation(&root,&other).isEmpty());
    assert(overte::e2e::picoSnapshotReviewObservation(nullptr,&window).isEmpty());
    const QPointer<QQuickItem> original=page;page->setParentItem(nullptr);
    assert(capture().value("present")==false && original); // Detachment is not retirement.
    delete page;assert(original.isNull());
}
