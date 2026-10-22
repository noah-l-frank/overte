// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Snapshot QML, ordinary Qt events and original normal-control helper.
// Script preferences/capture callbacks and OS backend are explicit host seams.
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QtTest/QTest>
#include <QSignalSpy>
#include <QDebug>
#include <cstdio>
#include "tests/device/native/NormalControlUi.h"
// Source-root URL boundary only; no UI or input result is supplied here.
QUrl PathUtils::defaultScriptsLocation(const QString&) { return QUrl::fromLocalFile(QString::fromUtf8(OVERTE_SOURCE_ROOT)+"/scripts/"); }
QUrl PathUtils::qmlUrl(const QString& relative) { return QUrl::fromLocalFile(QString::fromUtf8(OVERTE_SOURCE_ROOT)+"/interface/resources/qml/"+relative); }

class SnapshotService : public QObject {
    Q_OBJECT
public:
    QString format{"png"};
    Q_INVOKABLE QStringList getAvailableSnapshotFormats() { return {"png","jpg","webp"}; }
    Q_INVOKABLE QString getSnapshotFormat() { return format; }
    Q_INVOKABLE void setSnapshotFormat(const QString& value) { format=value; }
    Q_INVOKABLE QString snapshotFileUrl(const QString&) { return {}; }
};
class ExportService : public QObject {
    Q_OBJECT
    Q_PROPERTY(QStringList capabilities READ capabilities CONSTANT)
    Q_PROPERTY(bool busy READ busy CONSTANT)
    Q_PROPERTY(QString error READ error CONSTANT)
public:
    static ExportService* actual;QString path,action,cancelled;
    ExportService(QObject* parent=nullptr) : QObject(parent) { actual=this; }
    QStringList capabilities() const { return {"save","share"}; }
    bool busy() const { return false; }
    QString error() const { return {}; }
    Q_INVOKABLE QString request(const QString& file,const QString& kind) { path=file;action=kind;return "1"; }
    Q_INVOKABLE void cancel(const QString& ticket) { cancelled=ticket; }
signals:
    void completed(const QString& ticket,const QString& status,const QString& error);
};
ExportService* ExportService::actual=nullptr;

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);qmlRegisterType<ExportService>("Overte.Android",1,0,"NativeSnapshotAdapter");
    QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[1]));SnapshotService snapshot;
    engine.rootContext()->setContextProperty("Snapshot",&snapshot);
    const auto url=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])+"/system/snapshot/NativeSnapshotReview.qml");
    QQmlComponent component(&engine,url);QScopedPointer<QObject> object(component.create());
    auto page=qobject_cast<QQuickItem*>(object.data());if(!page) { qWarning()<<component.errors();return 1; }
    QQuickWindow window;window.resize(640,1100);page->setParentItem(window.contentItem());page->setSize(QSizeF(640,1100));
    window.show();window.requestActivate();QTest::qWait(80);
    auto message=[&](const QVariantMap& value) { QVariant data=value;return QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,data)); };
    if(!message({{"type","snapshot"},{"action","captureSettings"},{"setting",false}})) { return 2; }QTest::qWait(30);
    overte::e2e::SnapshotUi ui;auto observe=[&] { return ui.observe(page,&window); };
    auto row=[](const QJsonObject& source,const QString& id) { for(const auto& value:source.value("controls").toArray()) { if(value.toObject().value("id")==id) { return value.toObject(); } }return QJsonObject{}; };
    auto request=[&](const QJsonObject& source,const QString& id,const QString& action) {
        const auto control=row(source,id);
        return QJsonObject{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",source.value("instance")},{"generation",source.value("generation")},
            {"sequence",source.value("lastCommandSequence").toDouble()+1},{"observedElapsedMs",source.value("elapsedMs")},
            {"controlId",id},{"controlToken",control.value("token")},{"action",action}};
    };
    auto pointer=[&](QQuickItem*,const QPointF& point) { QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,point.toPoint());return true; };
    auto click=[&](QQuickItem* item) { return pointer(item,item->mapToScene(QPointF(item->width()/2,item->height()/2))); };
    auto apply=[&](const QJsonObject& command) { return ui.apply(page,&window,command,click,{},pointer); };
    auto input=[&](const QString& id,const QString& action,const QJsonValue& value=QJsonValue()) {
        const auto source=observe();if(row(source,id).isEmpty()) { qWarning()<<"Missing"<<id<<source;return false; }
        auto command=request(source,id,action);if(action=="replace") { command["text"]=value; }if(action=="select-index") { command["index"]=value; }
        const auto result=apply(command);QTest::qWait(20);return result.value("performed").toBool();
    };
    const auto mode=QString::fromLocal8Bit(argv[2]);QSignalSpy messages(page,SIGNAL(sendToScript(QVariant)));
    if(!observe().value("ready").toBool() || row(observe(),"snapshot.page").value("profile")!="native-snapshot-review-v1") { return 3; }
    std::puts(QJsonDocument(observe()).toJson(QJsonDocument::Compact).constData());
    if(mode=="stale") {
        const auto source=observe();auto command=request(source,"snapshot.capture","activate");
        command["controlToken"]=QString(32,'f');if(apply(command).value("performed").toBool() || !messages.isEmpty()) { return 4; }
        if(apply(request(source,"snapshot.capture","activate")).value("performed").toBool() || !messages.isEmpty()) { return 5; }
        return 0;
    }
    if(mode=="foreign") {
        QQuickItem imitation;imitation.setObjectName("snapshotReview");QQuickItem control(&imitation);control.setObjectName("snapshotCapture");
        if(!overte::e2e::snapshotControlId(&control).isEmpty()) { return 6; }
        QScopedPointer<QObject> duplicate(component.create());auto other=qobject_cast<QQuickItem*>(duplicate.data());
        other->setParentItem(page);other->setSize(QSizeF(640,1100));QTest::qWait(25);
        if(observe().value("ready").toBool() || !observe().value("controls").toArray().isEmpty()) { return 7; }
        other->setParentItem(nullptr);return 0;
    }
    if(mode=="obstruction") {
        const auto source=observe();QQmlComponent overlayComponent(&engine);overlayComponent.setData("import QtQuick\nRectangle { color:'red'; z:1000; anchors.fill:parent; MouseArea {anchors.fill:parent} }",QUrl("file:///foreign-overlay.qml"));
        QScopedPointer<QObject> overlay(overlayComponent.create());auto item=qobject_cast<QQuickItem*>(overlay.data());item->setParentItem(window.contentItem());QTest::qWait(25);
        if(apply(request(source,"snapshot.capture","activate")).value("performed").toBool() || !messages.isEmpty()) { return 8; }
        item->setParentItem(nullptr);return 0;
    }
    if(!input("snapshot.name","activate") || !input("snapshot.name","replace","Owned photo")
        || row(observe(),"snapshot.name").value("text")!="Owned photo") { return 9; }
    if(!input("snapshot.mode","activate") || !input("snapshot.mode","select-index",1)
        || row(observe(),"snapshot.mode").value("currentIndex")!=1) { return 10; }
    if(!input("snapshot.format","activate") || !input("snapshot.format","select-index",1)
        || row(observe(),"snapshot.format").value("currentText")!="jpg" || snapshot.format!="jpg") { return 11; }
    messages.clear();if(!input("snapshot.capture","activate") || messages.size()!=1) { return 12; }
    const auto capture=messages[0][0].toMap();
    if(capture.value("action")!="takeSnapshot" || capture.value("mode")!="animated" || capture.value("filename")!="Owned photo") { return 13; }
    // Original script-to-QML callback seam, separate from the delivered click.
    if(!message({{"type","snapshot"},{"action","clearPreviousImages"}})) { return 14; }QTest::qWait(25);
    if(!row(observe(),"snapshot.page").value("capturing").toBool() || !input("snapshot.cancel-capture","activate")) { return 15; }
    if(messages.last()[0].toMap().value("action")!="cancelSnapshotCapture") { return 16; }
    message({{"type","snapshot"},{"action","captureStatus"},{"phase","cancelled"}});
    const QString path="/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/owned.png";
    const QString digest=QString::fromLatin1(QCryptographicHash::hash(path.toUtf8(),QCryptographicHash::Sha256).toHex());
    message({{"type","snapshot"},{"action","addImages"},{"image_data",QVariantList{QVariantMap{{"localPath",path}}}},{"options",QVariantMap{{"canShare",true},{"isLoggedIn",true}}}});QTest::qWait(50);
    if(row(observe(),"snapshot.save."+digest).value("path")!=path || !input("snapshot.save."+digest,"activate")) { return 17; }
    if(!ExportService::actual || ExportService::actual->path!=path || ExportService::actual->action!="save") { return 18; }
    if(!input("snapshot.cancel-export","activate") || ExportService::actual->cancelled!="1") { return 19; }
    if(!input("snapshot.share."+digest,"activate") || ExportService::actual->action!="share") { return 20; }
    page->setParentItem(nullptr);return 0;
}
#include "snapshot-controls-runtime.moc"
