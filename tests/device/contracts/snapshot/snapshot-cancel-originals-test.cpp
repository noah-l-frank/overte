// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QChar>
#include <QBitArray>
#include "tests/device/native/PicoSnapshotFastCancel.h"
#include "tests/device/native/PicoSnapshotCancelBridge.h"
#include "tests/device/native/SnapshotCaptureOriginals.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QtTest/QTest>
#include <QJsonDocument>
#include <cassert>
#include <cstdio>
#include <QTemporaryDir>
#include <QSaveFile>
#include <QSharedPointer>
#include <thread>
#include "tests/device/native/FeatureLifecycle.h"
#include "tests/device/native/PrivatePreviewFiles.h"
#include "tests/device/native/AudioSettingsQueue.h"
#include "original-snapshot-cancel-vm.inc"

// The separate unchanged normal NavigationUi TU is compiled without unrelated
// feature observers. It preserves its actual Snapshot resolver/apply/token/
// sequence logic. Its object layout never crosses the feature macro boundary.
void* originalNavigation();
void deleteOriginalNavigation(void*);
QJsonObject observeOriginalNavigation(void*,QQuickItem*,QQuickWindow*,bool);
QJsonObject applyOriginalNavigation(void*,QQuickItem*,QQuickWindow*,bool,const QJsonObject&,const std::function<bool(QQuickItem*)>&);

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
class SnapshotSignalReceiver:public QObject {
    Q_OBJECT
public:std::function<void(QVariant)> action;
public slots:void receive(QVariant value) {action(value);}
};
#include "snapshot-cancel-originals-test.moc"

class HostApplication : public QGuiApplication {
public:using QGuiApplication::QGuiApplication;
    bool isHMDMode() const {return hmd;}bool hmd{true};
};
#undef qApp
#define qApp static_cast<HostApplication*>(QCoreApplication::instance())
class TestScriptingInterface : public QObject {
public:
    static TestScriptingInterface* original;
    static TestScriptingInterface* getInstance() {return original;}
    QVariantMap featurePicoSnapshotCancel(const QVariantMap&);
    std::function<QVariantMap(QVariantMap)> capture,script;
    QVariantMap featureSnapshotCaptureOriginals(QVariantMap value) {value.remove("action");return capture(value);}
    QVariantMap featureSnapshotScriptOriginals(QVariantMap value) {value.remove("action");return script(value);}
    QString _testResultsLocation,_featureObservationInstance{QString(32,'e')};
    overte::e2e::FeatureLifecycle* _featureLifecycle{nullptr};
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureSnapshotQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QSet<QString> _featureSnapshotCancelQueries;quint64 _featureSnapshotCancelSequence{0};
    QVariantMap _featureScriptWorkCommand,_featureScriptWorkResult;
};
TestScriptingInterface* TestScriptingInterface::original=nullptr;
#include "original-snapshot-cancel-tsi.inc"
class OffscreenQmlSurface : public QObject {
public:QQuickWindow* window{nullptr};QQuickWindow* getWindow() {return window;}
};
class TabletProxy : public QObject {
public:QQuickItem* root{nullptr};OffscreenQmlSurface* surface{nullptr};
    QQuickItem* getTabletRoot() {return root;}OffscreenQmlSurface* getTabletSurface() {return surface;}
};
class TabletScriptingInterface : public QObject {
public:QSharedPointer<TabletProxy> tablet;
    QSharedPointer<TabletProxy> getTablet(const QString&) {return tablet;}
};
namespace DependencyManager {
static QSharedPointer<TabletScriptingInterface> original;
template<class T> bool isSet() {return bool(original);}
template<class T> QSharedPointer<T> get() {return qSharedPointerCast<T>(original);}
}
static const QString SYSTEM_TABLET("com.highfidelity.interface.tablet.system");
static QString BRIDGE_DIRECTORY;
static bool bridgeEnabled() {return QCoreApplication::arguments().contains("--testScript");}
static std::function<bool(QQuickItem*)> vrPointer;
static bool sendPointerClick(QQuickItem* item,OffscreenQmlSurface*) {return vrPointer(item);}
#include "original-snapshot-cancel-writer.inc"
// Original provider method, with explicit tablet locator and VR pointer seams.
// The complete normal resolver/apply and real original Review remain real.
class TabletBridge : public QObject {
public:
    struct Navigation {
        void* owner;
        QJsonObject observe(QQuickItem* root,QQuickWindow* window,bool shown) {return observeOriginalNavigation(owner,root,window,shown);}
        QJsonObject apply(QQuickItem* root,QQuickWindow* window,bool shown,const QJsonObject& input,const std::function<bool(QQuickItem*)>& click) {
            return applyOriginalNavigation(owner,root,window,shown,input,click);
        }
    } _navigation;
    QString _lastSnapshotCancelCommand;
    QMap<QString,std::shared_ptr<overte::e2e::PicoSnapshotFastCancel>> _snapshotCancelJobs;
#include "original-snapshot-cancel-bridge.inc"
};

int main(int argc,char** argv) {
    HostApplication app(argc,argv);assert(argc>=4);const auto mode=QString::fromLocal8Bit(argv[3]);
    QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[2])+"/interface/resources/qml");
    SnapshotServices services;KeyboardServices keyboard;
    engine.rootContext()->setContextProperty("Snapshot",&services);engine.rootContext()->setContextProperty("KeyboardScriptingInterface",&keyboard);
    QQuickWindow window;window.resize(800,1100);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(800,1100));
    QQmlComponent component(&engine,QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])));
    auto page=qobject_cast<QQuickItem*>(component.create());if(!page) {qFatal("%s",qPrintable(component.errorString()));}
    page->setParent(&root);page->setParentItem(&root);page->setSize(root.size());QTest::qWait(30);
    auto fromScript=[&](QVariantMap message) {
        message.insert("type","snapshot");assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,QVariant(message))));
    };
    fromScript({{"action","captureSettings"},{"setting",mode!="wrong-mode"}});QCoreApplication::processEvents();
    auto uiObject=originalNavigation();auto ui=std::make_shared<overte::e2e::PicoSnapshotCancelInput>();
    ui->observe=[&](auto root,auto window) {return observeOriginalNavigation(uiObject,root,window,true);};
    ui->apply=[&](auto root,auto window,const QJsonObject& input,const auto& click) {return applyOriginalNavigation(uiObject,root,window,true,input,click);};
    const QString run(32,'a'),job(32,'b');
    Snapshot vm;ScriptManager manager;overte::e2e::SnapshotCaptureOriginals native;SnapshotCapture accepted;
    QVariantMap resources{{"nativeReviewEnabled",true},{"activeRequests",0},{"taking360",false},{"waitingOnSnapshot",false},
        {"projectionTimerActive",false},{"projectionImagesBytes",qulonglong(0)}};
    auto sourceCommand=[&](const QString& operation) {return QVariantMap{{"schemaVersion",1},
        {"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"runId",run},{"operation",operation}};};
    if(app.arguments().contains("--testScript")) {assert(!native.snapshot(sourceCommand("arm"),resources).isEmpty());}
    int captures=0,cancels=0,rendered=0;
    // Actual outgoing QML signals drive this explicit synthetic VM service.
    // Original caller/work/bridge/recorder bodies and real Qt timers are used;
    // this host check does not compile V8 or claim real render/device evidence.
    SnapshotSignalReceiver receiver;
    receiver.action=[&](QVariant message) {
        const auto action=message.toMap().value("action").toString();
        if(action=="takeSnapshot") {
            ++captures;fromScript({{"action","clearPreviousImages"}});
            if(mode=="ack-only") {return;}
            for(int index=1;index<=2;++index) {
                auto timer=std::make_unique<QTimer>();timer->setSingleShot(true);timer->start(index==1 ? 350 : 60000);
                if(index==1) {QObject::connect(timer.get(),&QTimer::timeout,[&] {++rendered;});}
                manager._timerFunctionMap.emplace(index,std::make_pair(std::move(timer),ScriptManager::CallbackData{2}));
            }
            manager._featureWorkActivity[2].timerRegistrations+=2;
            {ScriptManager::FeatureNativeCallScope scope(&manager,"featureCaptureEvent",2);vm.featureCaptureEvent("pending","snap_100_1","animated",1);}
            if(mode=="native-started") {accepted=std::make_shared<SnapshotCaptureRequest>("snap_100_1");native.begin(accepted);resources["activeRequests"]=1;}
            if(mode=="generation") {QQuickItem alternate(window.contentItem());alternate.setSize(root.size());ui->observe(&alternate,&window);}
        } else if(action=="cancelSnapshotCapture") {
            ++cancels;manager._timerFunctionMap.clear();
            {ScriptManager::FeatureNativeCallScope scope(&manager,"featureCaptureEvent",2);vm.featureCaptureEvent("cancelled","snap_100_1","animated",1);}
            fromScript({{"action","captureStatus"},{"phase","cancelled"}});
        }
    };
    assert(QObject::connect(page,SIGNAL(sendToScript(QVariant)),&receiver,SLOT(receive(QVariant))));
    if(mode=="upload") {vm._uploads.insert("original-upload-map-entry",nullptr);}
    const auto click=[&](QQuickItem* item) {
        QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());return true;
    };
    auto makeInput=[&](const QString& id,const QString& action) {
        const auto controls=ui->observe(&root,&window);QJsonObject selected;
        for(const auto& row:controls.value("controls").toArray()) {if(row.toObject().value("id")==id) {selected=row.toObject();}}
        assert(!selected.isEmpty());
        return QJsonObject{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"bridgeId",controls.value("bridgeId")},{"generation",controls.value("generation")},
            {"sequence",controls.value("lastCommandSequence").toDouble()+1},{"observedElapsedMs",controls.value("elapsedMs")},
            {"controlId",id},{"controlToken",selected.value("token")},{"action",action}};
    };
    if(mode!="unowned-name") {
        const auto focus=makeInput("snapshot.name","activate");
        assert(ui->apply(&root,&window,focus,click).value("performed")==true);
        auto replace=makeInput("snapshot.name","replace");replace.insert("text","parity-"+run.left(16)+"-animated");
        assert(ui->apply(&root,&window,replace,click).value("performed")==true);
        if(app.arguments().contains("--testScript")) {assert(overte::e2e::snapshotReviewObservation(&root).value("review").toMap().value("captureName")==replace.value("text").toString());}
    }
    const auto input=makeInput("snapshot.capture","activate");
    if(mode=="stale") {QTest::qWait(1600);}
    TestScriptingInterface test;TestScriptingInterface::original=&test;
    test.capture=[&](QVariantMap query) {return native.snapshot(query,resources);};
    test.script=[&](QVariantMap query) {return vm.featureSnapshotScriptOriginals(query);};
    QTemporaryDir directory;assert(directory.isValid());test._testResultsLocation=directory.path();
    overte::e2e::FeatureLifecycle lifecycle(&test);test._featureLifecycle=&lifecycle;
    if(app.arguments().contains("--testScript")) {assert(lifecycle.start(directory.path()));}
    BRIDGE_DIRECTORY=directory.path();
    DependencyManager::original=QSharedPointer<TabletScriptingInterface>::create();
    DependencyManager::original->tablet=QSharedPointer<TabletProxy>::create();
    OffscreenQmlSurface surface;surface.window=&window;
    DependencyManager::original->tablet->root=&root;DependencyManager::original->tablet->surface=&surface;
    DependencyManager::original->tablet->setProperty("tabletShown",true);
    TabletBridge bridge;bridge._navigation.owner=uiObject;vrPointer=click;
    bridge.installSnapshotCancelProvider();
    auto query=[&](const QString& operation) {
        return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"action","feature-pico-snapshot-cancel"},{"runId",run},{"jobId",job},{"operation",operation},
            {"request",operation=="start" ? input.toVariantMap() : QVariantMap{}}};
    };
    const auto start=query("start");
    if(mode=="complete" && app.arguments().contains("--testScript")) {
        QVariantMap late;QElapsedTimer elapsed;elapsed.start();
        std::thread worker([&] {late=test.featurePicoSnapshotCancel(start);});worker.join();
        assert(late.isEmpty() && elapsed.elapsed()<1800 && captures==0 && bridge._snapshotCancelJobs.isEmpty());
        assert(test.featurePicoSnapshotCancel(start).isEmpty());
        QCoreApplication::sendPostedEvents();QCoreApplication::processEvents();
        assert(captures==0 && bridge._snapshotCancelJobs.isEmpty());
    }
    assert(writeJson(BRIDGE_DIRECTORY+"/snapshot-cancel-ui-command.json",QJsonObject::fromVariantMap(start)));
    bridge.snapshotCancelTick();
    QFile status(BRIDGE_DIRECTORY+"/snapshot-cancel-ui-status.json");assert(status.open(QIODevice::ReadOnly));
    auto packet=QJsonDocument::fromJson(status.readAll()).object().value("packet").toObject().toVariantMap();status.close();
    auto original=packet.value("source").toMap();
    if(!app.arguments().contains("--testScript")) {assert(packet.isEmpty() && captures==0);deleteOriginalNavigation(uiObject);return 0;}
    assert(test.featurePicoSnapshotCancel(start).isEmpty()); // Original query consumed, never replay capture.
    const auto captureCount=captures;bridge.snapshotCancelTick();assert(captures==captureCount);
    const auto owner=bridge._snapshotCancelJobs.value(job);assert(owner);
    for(int index=0;index<60 && owner->summary().value("timerActive").toBool();++index) {QTest::qWait(10);}
    auto lastQuery=query("observe");packet=test.featurePicoSnapshotCancel(lastQuery);original=packet.value("source").toMap();
    assert(original.value("timerActive")==false);
    if(mode=="complete") {
        assert(captures==1 && cancels==1 && rendered==0 && manager._timerFunctionMap.empty());
        assert(original.value("phase")=="complete" && original.value("pending").toMap().value("script").toMap().value("history").toMap().value("sequence")==1);
        const auto before=original;lastQuery=query("retire");packet=test.featurePicoSnapshotCancel(lastQuery);original=packet.value("source").toMap();
        assert(original.value("retired")==true && original.value("cancelled")==before.value("cancelled"));
        test.featurePicoSnapshotCancel(query("start"));assert(captures==1 && cancels==1);
    } else {
        assert(original.value("phase")=="failed" && cancels==0);
        assert(captures==(mode=="upload" || mode=="stale" || mode=="unowned-name" || mode=="wrong-mode" ? 0 : 1));
    }
    std::puts(QJsonDocument::fromVariant(QVariantMap{{"command",lastQuery},{"packet",packet}}).toJson(QJsonDocument::Compact).constData());
    manager._timerFunctionMap.clear();accepted.reset();deleteOriginalNavigation(uiObject);delete page;
}
