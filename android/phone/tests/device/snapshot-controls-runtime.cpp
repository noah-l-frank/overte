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
#include "tests/device/native/PhoneSnapshotFastCancel.h"
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

// ORIGINAL_TEST_BINDING

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
    auto sharedUi=std::make_shared<overte::e2e::SnapshotUi>();auto& ui=*sharedUi;auto observe=[&] { return ui.observe(page,&window); };
    auto row=[](const QJsonObject& source,const QString& id) { for(const auto& value:source.value("controls").toArray()) { if(value.toObject().value("id")==id) { return value.toObject(); } }return QJsonObject{}; };
    auto request=[&](const QJsonObject& source,const QString& id,const QString& action) {
        const auto control=row(source,id);
        return QJsonObject{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",source.value("instance")},{"generation",source.value("generation")},
            {"sequence",source.value("lastCommandSequence").toDouble()+1},{"observedElapsedMs",source.value("elapsedMs")},
            {"controlId",id},{"controlToken",control.value("token")},{"action",action}};
    };
    auto pointer=[&](QQuickItem* item,const QPointF& point) { return overte::e2e::NormalControlUi::pointerEvent(item,&window,point); };
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
    if(mode.startsWith("fast-")) {
        // Only the script/VM producer is simulated. Original QML and helper
        // inputs, native event loop, actual Qt timers/clocks are executed.
        if(!input("snapshot.mode","activate") || !input("snapshot.mode","select-index",1)) { return 30; }messages.clear();
        QTimer delay,timeout;delay.setSingleShot(true);timeout.setSingleShot(true);
        QVariantList scriptEvents,captureEvents;int captures=0,starts=0,invocations=0;QString active;
        QElapsedTimer lifetime;lifetime.start();
        const auto scriptInstance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        const auto historyInstance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        auto record=[&](const QString& kind) {
            ++invocations;QVariantList timers;
            if(delay.isActive())timers.append(QVariantMap{{"handle",1},{"active",delay.isActive()},{"singleShot",delay.isSingleShot()},{"intervalMs",delay.interval()},{"remainingMs",delay.remainingTime()}});
            if(timeout.isActive())timers.append(QVariantMap{{"handle",2},{"active",timeout.isActive()},{"singleShot",timeout.isSingleShot()},{"intervalMs",timeout.interval()},{"remainingMs",timeout.remainingTime()}});
            const auto epoch=QDateTime::currentMSecsSinceEpoch();
            const QVariantMap compiled{{"scriptId",2},{"resourceName","file:///packaged/scripts/system/snapshot.js"},{"encoding","utf-16le-code-units"},{"codeUnits",40},{"sha256",QString(64,'c')},{"compiledEpochMs",3}};
            const QVariantMap work{{"snapshotScriptWorkVersion",1},{"scriptId",2},{"capturedEpochMs",epoch},{"timers",timers},
                {"signalCallbacks",1},{"timerCallbacks",0},{"signalInvocations",invocations},{"timerInvocations",0},{"timerRegistrations",starts*2}};
            const QVariantMap caller{{"callerVersion",2},{"method","featureCaptureEvent"},{"sequence",invocations},{"invokedEpochMs",epoch},
                {"manager",QVariantMap{{"instance",QString(32,'a')},{"assigned",true},{"url","file:///packaged/scripts/defaultScripts.js"},{"loadGeneration",1},{"assignedEpochMs",1}}},
                {"code",QVariantMap{{"submitted",true},{"encoding","utf-16le-code-units"},{"codeUnits",20},{"sha256",QString(64,'b')},{"submittedEpochMs",2}}},
                {"compilation",compiled},{"snapshotWork",work}};
            scriptEvents.append(QVariantMap{{"sequence",scriptEvents.size()+1},{"kind",kind},{"id",active},{"mode","animated"},{"revision",starts},
                {"capturedEpochMs",epoch},{"elapsedMs",lifetime.elapsed()},{"caller",caller}});
        };
        QObject::connect(&delay,&QTimer::timeout,[&] {
            ++captures;captureEvents.append(QVariantMap{{"sequence",captureEvents.size()+1},{"kind","capture-begin"},{"id",active},
                {"phase",""},{"path",""},{"error",""},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"elapsedMs",lifetime.elapsed()}});
        });
        // QSignalSpy is the original QML producer boundary. A precise timer
        // drains only newly emitted original messages, without invoking QML
        // handlers or changing capture delays.
        QTimer scriptBridge;scriptBridge.setTimerType(Qt::PreciseTimer);scriptBridge.setInterval(1);int consumed=0;
        QObject::connect(&scriptBridge,&QTimer::timeout,[&] {
            while(consumed<messages.size()) {
                const auto delivered=messages[consumed++][0].toMap();const auto action=delivered.value("action").toString();
                if(action=="takeSnapshot") {
                    if(mode=="fast-ignored") { continue; }
                    ++starts;active="snap_"+QString::number(QDateTime::currentMSecsSinceEpoch())+'_'+QString::number(starts);
                    delay.start(350);timeout.start(60000);
                    message({{"type","snapshot"},{"action","clearPreviousImages"}});record("pending");
                    if(mode=="fast-stale") { auto row=scriptEvents.last().toMap();row["capturedEpochMs"]=qint64(1);scriptEvents.last()=row; }
                    if(mode=="fast-native-replacement") { captureEvents.append(QVariantMap{{"foreign",true}}); }
                } else if(action=="cancelSnapshotCapture" && !active.isEmpty()) {
                    if(mode=="fast-ignore-cancel") { continue; }
                    delay.stop();timeout.stop();message({{"type","snapshot"},{"action","captureStatus"},{"phase","cancelled"}});
                    if(mode=="fast-foreign") { active="snap_1_999"; }
                    record("cancelled");active.clear();
                }
            }
        });scriptBridge.start();
        auto native=[&] {
            QVariantList owned;
            if(captures)owned.append(QVariantMap{{"id",active},{"state","active"},{"announced",false}});
            return QVariantMap{{"phoneSnapshotObservationVersion",1},{"nativeReview",true},
                {"storageRoot","/data/user/0/io.github.noah_be.overte.phone/files/Snapshots"},{"captures",owned},{"uploads",QStringList{}},
                {"history",QVariantMap{{"snapshotHistoryVersion",1},{"instance",historyInstance},{"complete",true},{"sequence",captureEvents.size()},{"events",captureEvents}}},
                {"scriptHistory",QVariantMap{{"snapshotScriptHistoryVersion",1},{"instance",scriptInstance},{"complete",true},{"sequence",scriptEvents.size()},{"events",scriptEvents}}}};
        };
        const QString run(32,'e');const auto command=request(observe(),"snapshot.capture","activate");
        const auto id=command.value("commandId").toString();
        auto snapshotNative=QSharedPointer<Snapshot>::create();snapshotNative->read=native;
        auto offscreen=QSharedPointer<OffscreenUi>::create();offscreen->root=page;offscreen->window=&window;
        SnapshotTestDependencies::service<Snapshot>()=snapshotNative;SnapshotTestDependencies::service<OffscreenUi>()=offscreen;
        TestScriptingInterface bridge;bridge._phoneSnapshotUi=sharedUi;
        QVariantMap latest;
        auto call=[&](const QString& operation,const QJsonObject& input=QJsonObject{}) {
            const QVariantMap wire{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
                {"action","phone-snapshot-cancel"},{"runId",run},{"jobId",id},{"operation",operation},{"request",input.toVariantMap()}};
            latest=bridge.phoneSnapshotCancel(wire);return latest.value("source").toMap();
        };
        const QVariantMap invalid{{"schemaVersion",1},{"commandId",QString(32,'a')},{"action","phone-snapshot-cancel"},
            {"runId",run},{"jobId",id},{"operation","observe"},{"request",QVariantMap{}}};
        // Direct native callers do not get a weaker boundary than the Probe.
        for (const auto& key:QStringList{"schemaVersion","runId","jobId","operation","request"}) {
            auto bad=invalid;bad[key]=key=="schemaVersion" ? QVariant(true) : QVariant("foreign");
            if (!bridge.phoneSnapshotCancel(bad).isEmpty()) { return 41; }
        }
        auto extra=invalid;extra["expectedCancelled"]=true;
        if (!bridge.phoneSnapshotCancel(extra).isEmpty() || !bridge.phoneSnapshotCancel(invalid).isEmpty()
            || !bridge._phoneSnapshotCancelJobs.isEmpty() || bridge._phoneSnapshotCancelSequence!=0 || !messages.isEmpty()) { return 42; }
        auto state=call("start",command);
        QElapsedTimer wait;wait.start();
        while(state.value("phase")=="capturing" || state.value("phase")=="cancelling") {
            if(wait.elapsed()>5500) { return 31; }QTest::qWait(5);state=call("observe");
        }
        if(mode=="fast-normal" || mode=="fast-late-work") {
            if(state.value("phase")!="complete" || captures!=0 || delay.isActive() || timeout.isActive()
                || state.value("timerActive").toBool() || scriptEvents.size()!=2) { qWarning()<<state;return 32; }
            if(state.value("pending").toMap().isEmpty() || state.value("cancelled").toMap().isEmpty()) { return 33; }
            const auto before=messages.size();call("start",command);
            QTest::qWait(10);if(messages.size()!=before) { return 34; }
            if(call("retire").value("retired")!=true) { return 35; }
            if(mode=="fast-late-work") {
                if(!input("snapshot.capture","activate")) { return 36; }QTest::qWait(10);
                if(!delay.isActive() || !call("retire").isEmpty()
                    || !delay.isActive() || !timeout.isActive()) { return 37; }
            }
        } else {
            if(state.value("phase")!="failed" || state.value("timerActive").toBool()) { qWarning()<<state;return 38; }
            if(mode=="fast-ignored" && (captures!=0 || scriptEvents.size()!=0 || messages.size()!=1)) { return 39; }
            if(mode=="fast-ignore-cancel" && (captures!=1 || !timeout.isActive())) { return 40; }
        }
        std::puts((QByteArray("FAST:")+QJsonDocument::fromVariant(state).toJson(QJsonDocument::Compact)).constData());
        if (mode=="fast-normal") { std::puts((QByteArray("BINDING:")+QJsonDocument::fromVariant(latest).toJson(QJsonDocument::Compact)).constData()); }
        scriptBridge.stop();delay.stop();timeout.stop();page->setParentItem(nullptr);return 0;
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
