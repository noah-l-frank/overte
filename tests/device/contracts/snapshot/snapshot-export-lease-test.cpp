// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QGuiApplication>
#include <QElapsedTimer>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQmlFileSelector>
#include <QSignalSpy>
#include <QImage>
#include <QDir>
#include <QPointer>
#include <QtTest/QTest>
#include <cassert>
#include <thread>
#if defined(OVERTE_PICO_SETUP)
#include "android/common/snapshot/src/NativeSnapshotAdapter.h"
#endif
#include "interface/src/ui/SnapshotStorage.h"
#include "tests/device/native/PicoSnapshotExportControls.h"
#include "tests/device/native/PicoSnapshotExportLease.h"
#include <jni.h>
extern "C" jboolean Java_org_overte_snapshot_SnapshotAdapter_nativeFeatureEnabled(JNIEnv*,jclass);

class SnapshotServices : public QObject {
    Q_OBJECT
public:
    Q_INVOKABLE QStringList getAvailableSnapshotFormats() const {return {"png","jpg","webp"};}
    Q_INVOKABLE QString getSnapshotFormat() const {return "png";}
    Q_INVOKABLE void setSnapshotFormat(const QString&) {}
    Q_INVOKABLE QString snapshotFileUrl(const QString& value) const {return QUrl::fromLocalFile(value).toString();}
};
class KeyboardServices : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool use3DKeyboard MEMBER use3DKeyboard)
    Q_PROPERTY(bool raised MEMBER raised)
public:bool use3DKeyboard{true},raised{false};
};
#include "snapshot-export-lease-test.moc"

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "tests/device/native/AudioSettingsQueue.h"
#include "tests/device/native/FeatureLifecycle.h"
#include "tests/device/native/PrivatePreviewFiles.h"
#include "tests/device/native/PicoSnapshotExportCommand.h"
#include <QTemporaryDir>
#include <QSharedPointer>
#include <QSemaphore>
#include <limits>
#include <map>
class HostApplication : public QGuiApplication {
public:using QGuiApplication::QGuiApplication;bool isHMDMode() const {return hmd;}bool hmd{true};
};
#undef qApp
#define qApp static_cast<HostApplication*>(QCoreApplication::instance())
// Only application/registry/VR surface services are explicit host seams. The
// getter bodies, weak bounded queue, original QML/backend and JNI TU are real.
class OffscreenQmlSurface : public QObject {public:QQuickWindow* window{nullptr};QQuickWindow* getWindow(){return window;}};
class TabletProxy : public QObject {
public:using QObject::QObject;QQuickItem* root{nullptr};OffscreenQmlSurface* surface{nullptr};
    QQuickItem* getTabletRoot(){return root;}OffscreenQmlSurface* getTabletSurface(){return surface;}
};
class TabletScriptingInterface : public QObject {
public:TabletProxy* featureExistingTablet(const QString&) const;std::map<QString,TabletProxy*> _tabletProxies;
};
#include "original-snapshot-existing-tablet.inc"
static QSharedPointer<TabletScriptingInterface> originalTablets;
class DependencyManager {
public:static int gets;
    template<typename T>static bool isSet(){return !originalTablets.isNull();}
    template<typename T>static QSharedPointer<T> get(){++gets;return qSharedPointerCast<T>(originalTablets);}
};
int DependencyManager::gets=0;
class TestScriptingInterface : public QObject {
public:
    QVariantMap featurePicoSnapshotExports(const QVariantMap&);
    QString _testResultsLocation,_featureObservationInstance{QString(32,'e')};
    overte::e2e::FeatureLifecycle* _featureLifecycle{nullptr};
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureSnapshotQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QSet<QString> _featureSnapshotExportQueries;quint64 _featureSnapshotExportSequence{0};
};
#include "original-snapshot-export-getter.inc"

static void getterBoundaries(QQuickItem* root,QQuickWindow* window) {
    QTemporaryDir privateState;assert(privateState.isValid());
    overte::e2e::FeatureLifecycle lifecycle(qApp);assert(lifecycle.start(privateState.path()));
    TestScriptingInterface source;source._testResultsLocation=privateState.path();source._featureLifecycle=&lifecycle;
    auto command=[] {return QVariantMap{{"schemaVersion",1},{"action","feature-pico-snapshot-exports"},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"runId",QString(32,'a')},{"operation","observe"},{"exportRequest",""},{"resourceId",""}};};
    assert(source.featurePicoSnapshotExports(command()).isEmpty() && DependencyManager::gets==0);
    originalTablets=QSharedPointer<TabletScriptingInterface>::create();
    assert(originalTablets->featureExistingTablet("com.highfidelity.interface.tablet.system")==nullptr);
    assert(source.featurePicoSnapshotExports(command()).isEmpty() && originalTablets->_tabletProxies.empty());
    auto tablet=new TabletProxy(originalTablets.data());OffscreenQmlSurface surface;surface.window=window;tablet->surface=&surface;tablet->root=root;
    originalTablets->_tabletProxies.insert({"com.highfidelity.interface.tablet.system",tablet});
    assert(originalTablets->featureExistingTablet("com.highfidelity.interface.tablet.system")==tablet);
    auto invalid=command();invalid.insert("expectedSaved",true);const auto before=source._featureSnapshotExportQueries.size();
    assert(source.featurePicoSnapshotExports(invalid).isEmpty() && source._featureSnapshotExportQueries.size()==before);
    qApp->hmd=false;assert(source.featurePicoSnapshotExports(command()).isEmpty() && source._featureSnapshotExportQueries.size()==before);qApp->hmd=true;
    // Actual uninitialized JNI stays unavailable even with a current original
    // native lease; no empty export/destination inventories are manufactured.
    const auto request=command();assert(source.featurePicoSnapshotExports(request).isEmpty());
    assert(source._featureSnapshotExportQueries.contains(request.value("commandId").toString()));
    const auto consumed=source._featureSnapshotExportQueries.size();assert(source.featurePicoSnapshotExports(request).isEmpty());
    assert(source._featureSnapshotExportQueries.size()==consumed);
    QThread worker;worker.start();QSemaphore entered,release,back;
    originalTablets->moveToThread(&worker);
    QMetaObject::invokeMethod(originalTablets.data(),[&] {entered.release();release.acquire();},Qt::QueuedConnection);
    assert(entered.tryAcquire(1,1000));QElapsedTimer clock;clock.start();
    assert(source.featurePicoSnapshotExports(command()).isEmpty() && clock.elapsed()<1000);
    const auto blockedCount=source._featureSnapshotExportQueries.size();assert(!source._featureSnapshotQueue->settled());
    assert(source.featurePicoSnapshotExports(command()).isEmpty() && source._featureSnapshotExportQueries.size()==blockedCount);
    release.release();auto held=originalTablets;
    QMetaObject::invokeMethod(held.data(),[held,&back] {held->moveToThread(qApp->thread());back.release();},Qt::QueuedConnection);
    assert(back.tryAcquire(1,2000));assert(source._featureSnapshotQueue->settled());
    worker.quit();assert(worker.wait(1000));originalTablets.clear();
}
#else
using HostApplication=QGuiApplication;
#endif

int main(int argc,char** argv) {
    HostApplication app(argc,argv);assert(argc>=3);
    const bool enabled=QString::fromLocal8Bit(argv[1])=="enabled";
    assert((Java_org_overte_snapshot_SnapshotAdapter_nativeFeatureEnabled(nullptr,nullptr)==JNI_TRUE)==enabled);
    NativeSnapshotAdapter first;
    if(!enabled) {
        assert(first.featureOriginalLease().isEmpty());
        assert(NativeSnapshotAdapter::featureExportObservation().isEmpty());
        assert(NativeSnapshotAdapter::featureReadbackCommand("{}").isEmpty());return 0;
    }
    const auto original=first.featureOriginalLease();
    assert(original.value("snapshotExportLeaseVersion")==1 && !original.value("handle").toString().isEmpty()
        && original.value("ticket").toString().isEmpty() && !original.value("busy").toBool());
    std::thread foreign([&] {assert(first.featureOriginalLease().isEmpty());});foreign.join();
    NativeSnapshotAdapter second;assert(second.featureOriginalLease().value("handle").toString().toLongLong()>original.value("handle").toString().toLongLong());
    // No JVM has initialized the real JNI endpoint. No success/empty-inventory
    // original may be invented from that unavailable backend.
    assert(NativeSnapshotAdapter::featureExportObservation().isEmpty());assert(NativeSnapshotAdapter::featureReadbackCommand("{}").isEmpty());
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    QQmlEngine engine;QQmlFileSelector selector(&engine);selector.setExtraSelectors({"android"});
    const auto rootPath=QString::fromLocal8Bit(argv[2]);engine.addImportPath(rootPath+"/interface/resources/qml");
    SnapshotServices snapshot;KeyboardServices keyboard;
    engine.rootContext()->setContextProperty("Snapshot",&snapshot);engine.rootContext()->setContextProperty("KeyboardScriptingInterface",&keyboard);
    QQuickWindow window;window.resize(800,1100);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(800,1100));
    auto lease=[&] {return overte::e2e::picoSnapshotExportLease(&root,&window);};
    assert(lease()==QVariantMap({{"present",false}}));
    QQmlComponent component(&engine,QUrl::fromLocalFile(rootPath+"/scripts/system/snapshot/NativeSnapshotReview.qml"));
    auto page=qobject_cast<QQuickItem*>(component.create());if(!page) {qFatal("%s",qPrintable(component.errorString()));}
    page->setParent(&root);page->setParentItem(&root);page->setSize(root.size());QTest::qWait(30);
    const auto current=lease();assert(current.value("present").toBool());
    getterBoundaries(&root,&window);
    const auto native=page->findChild<NativeSnapshotAdapter*>();assert(native && current.value("native").toMap()==native->featureOriginalLease());
    const auto directory=overte::snapshot::storageRoot();assert(QDir().mkpath(directory));
    const auto path=QDir(directory).filePath("parity-aaaaaaaaaaaaaaaa-still-png-snap_original.png");
    QImage image(20,16,QImage::Format_RGB32);image.fill(Qt::red);assert(image.save(path,"PNG"));
    QVariantMap message{{"type","snapshot"},{"action","showPreviousImages"},{"image_data",QVariantList{QVariantMap{{"localPath",path}}}},
        {"options",QVariantMap{{"isLoggedIn",true},{"canShare",true}}}};
    assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,QVariant(message))));QTest::qWait(40);
    auto find=[&](const QString& action) {
        QQuickItem* found=nullptr;
        std::function<void(QQuickItem*)> walk=[&](QQuickItem* item) {
            const auto id=overte::e2e::picoSnapshotExportControlId(item);
            if(id.startsWith("snapshot."+action+'.')) {assert(!found);found=item;}
            for(auto child:item->childItems()) {walk(child);}
        };walk(page);
        assert(found);return found;
    };
    QSignalSpy completed(native,&NativeSnapshotAdapter::completed);QSignalSpy outgoing(page,SIGNAL(sendToScript(QVariant)));
    QList<QVariantMap> leaseEvents;QObject::connect(native,&NativeSnapshotAdapter::stateChanged,[&] {leaseEvents.append(native->featureOriginalLease());});
    for(const auto& action:QStringList{"save","share"}) {
        auto button=find(action);QJsonObject metadata;const auto id=overte::e2e::picoSnapshotExportControlId(button);
        overte::e2e::appendPicoSnapshotExportControl(metadata,button,id);
        assert(metadata.value("path")==path && metadata.value("inputReady").toBool());
        assert(!overte::e2e::picoSnapshotExportControlSource(button,id).isEmpty());
        // Actual ordinary pointer -> original QML -> real NativeSnapshotAdapter
        // request/ticket -> original queued JNI-unavailable error. No Save or
        // Share outcome is inferred from the pointer delivery.
        const auto before=completed.size();leaseEvents.clear();
        QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,button->mapToScene(QPointF(button->width()/2,button->height()/2)).toPoint());
        bool pendingObserved=false;for(const auto& observed:leaseEvents) {if(observed.value("busy").toBool() && !observed.value("ticket").toString().isEmpty()) {pendingObserved=true;}}
        assert(pendingObserved);
        assert(native->featureOriginalLease().value("handle")==current.value("native").toMap().value("handle"));
        QCoreApplication::processEvents();QTest::qWait(15);assert(!native->busy() && completed.size()==before+1);
        assert(completed.last().at(1).toString()=="error" && page->property("statusError").toBool());
    }
    auto upload=find("upload");QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,upload->mapToScene(QPointF(upload->width()/2,upload->height()/2)).toPoint());
    bool sent=false;for(const auto& row:outgoing) {const auto value=row[0].toMap();if(value.value("action")=="shareSnapshotForUrl") {assert(value.value("data")==path);sent=true;}}
    assert(sent && page->property("uploadPath")==path);
    const QPointer<NativeSnapshotAdapter> retained=native;page->setParentItem(nullptr);
    assert(lease()==QVariantMap({{"present",false}}) && retained); // no retirement claim
    delete page;assert(!retained);
#endif
}
