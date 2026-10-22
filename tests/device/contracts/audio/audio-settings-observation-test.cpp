// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Compile the whole original getter with explicit AudioClient/Audio/NodeList
// boundaries. The audio engine, microphone and mixer are not run here.
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QSemaphore>
#include <QJsonDocument>
#include <QSharedPointer>
#include <QTemporaryDir>
#include <QThread>
#include <cassert>
#include <cstdio>
#include <functional>
#include <memory>
#include "tests/device/native/AudioSettingsObservation.h"
#include "libraries/audio-client/src/RecordedPreviewDeferred.h"
#include "tests/device/native/PrivatePreviewFiles.h"

class InputBoundary:public QObject {
    Q_OBJECT
    Q_PROPERTY(bool peakValuesEnabled READ peakValuesEnabled)
public:
    bool peak{false};int reads{0};
    bool peakValuesEnabled(){assert(thread()==QThread::currentThread());++reads;return peak;}
};
class DevicesBoundary:public QObject {
    Q_OBJECT
    Q_PROPERTY(InputBoundary* input READ input)
public:
    QPointer<InputBoundary> original;bool destroyInput{false};
    InputBoundary* input(){assert(thread()==QThread::currentThread());if(destroyInput){delete original.data();return nullptr;}return original.data();}
};
class AudioScriptingInterface:public QObject {};
namespace scripting {
class Audio:public AudioScriptingInterface {
    Q_OBJECT
    Q_PROPERTY(DevicesBoundary* devices READ devices)
public:
    DevicesBoundary* original{nullptr};
    DevicesBoundary* devices(){assert(thread()==QThread::currentThread());return original;}
};
}
class AudioClient:public QObject {
public:
    int reads{0};bool malformed{false};
    QVariantMap featureRecordedVoiceObservation(){assert(thread()==QThread::currentThread());++reads;
        return {{"active",false},{"cycle",malformed?QVariant(0):QVariant::fromValue(qulonglong(0))}};}
    overte::e2e::RecordedPreviewDeferred deferred;
    QVariantMap featureRecordedVoiceLifetime(){assert(thread()==QThread::currentThread());
        return {{"audioPreviewLifetimeVersion",1},{"deferred",deferred.snapshot(this)},
            {"previewTimer",QVariantMap{{"created",false},{"id",""},{"createdEpochMs",0},{"alive",false},{"active",false}}},
            {"pendingLoopbackBytes",0},{"pendingLoopbackCapacityBytes",0},{"loopbackDeviceAssigned",false},
            {"retainedPreviewBytes",0},{"previewBufferCapacityBytes",0},{"previewTapStateEmpty",true}};
    }
    bool getRecording()const{return false;}bool isMuted()const{return false;}
    bool getLocalEcho()const{return false;}bool getServerEcho()const{return false;}
};
class NodeList:public QObject {
public:
    int reads{0};
    float getAvatarGain(const QUuid& id){assert(thread()==QThread::currentThread()&&id.isNull());++reads;return -.5f;}
    float getInjectorGain(){assert(thread()==QThread::currentThread());return -.25f;}
};
struct DependencyManager {
    static int gets;
    template<class T> static QSharedPointer<T>& original(){static QSharedPointer<T> value;return value;}
    template<class T> static bool isSet(){return !original<T>().isNull();}
    template<class T> static QSharedPointer<T> get(){++gets;assert(isSet<T>());return original<T>();}
};
int DependencyManager::gets{0};
class Application:public QCoreApplication {
public:using QCoreApplication::QCoreApplication;bool hmd{true};bool isHMDMode()const{return hmd;}
};
#undef qApp
#define qApp static_cast<Application*>(QCoreApplication::instance())
struct LifecycleBoundary {QVariantMap snapshot()const{return {{"owned",true}};}};
class TestScriptingInterface:public QObject {
public:
    QString _testResultsLocation;
    std::shared_ptr<LifecycleBoundary> _featureLifecycle{std::make_shared<LifecycleBoundary>()};
    std::shared_ptr<overte::e2e::AudioSettingsObservation> _featureAudioSettings;
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAudioSettingsQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QVariantMap featureAudioSettingsObservation(const QVariantMap& command);
};
#include "original-audio-settings-getter.inc"

QVariantMap command(){return {{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
    {"action","feature-audio-settings-observe"},{"runId",QString(32,'a')}};}
int main(int argc,char** argv){
    Application app(argc,argv);QTemporaryDir directory;assert(directory.isValid());
    assert(QFile::setPermissions(directory.path(),QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));
    TestScriptingInterface source;source._testResultsLocation=directory.path();
    assert(source.featureAudioSettingsObservation(command()).isEmpty());assert(DependencyManager::gets==0);
    auto client=QSharedPointer<AudioClient>::create();auto nodes=QSharedPointer<NodeList>::create();
    auto script=QSharedPointer<scripting::Audio>::create();DevicesBoundary devices;InputBoundary input;
    devices.original=&input;script->original=&devices;
    for(const auto& name:overte::e2e::audioSettingsBooleans())script->setProperty(name.toUtf8(),false);
    for(const auto& name:overte::e2e::audioSettingsNumbers())script->setProperty(name.toUtf8(),.5);
    script->setProperty("context","VR");
    DependencyManager::original<AudioClient>()=client;DependencyManager::original<AudioScriptingInterface>()=script;
    // Missing original NodeList must not cause any dependency get/creation.
    assert(source.featureAudioSettingsObservation(command()).isEmpty());assert(DependencyManager::gets==0);
    DependencyManager::original<NodeList>()=nodes;
    if(!QCoreApplication::arguments().contains("--testScript")){
        assert(source.featureAudioSettingsObservation(command()).isEmpty());assert(DependencyManager::gets==0);return 0;
    }
    app.hmd=false;assert(source.featureAudioSettingsObservation(command()).isEmpty());assert(DependencyManager::gets==0);app.hmd=true;
    auto invalid=command();invalid.insert("expectedMuted",false);
    assert(source.featureAudioSettingsObservation(invalid).isEmpty());assert(DependencyManager::gets==0);
    source._testResultsLocation.clear();assert(source.featureAudioSettingsObservation(command()).isEmpty());
    assert(DependencyManager::gets==0);source._testResultsLocation=directory.path();
    auto malformed=command();malformed.insert("schemaVersion",true);assert(source.featureAudioSettingsObservation(malformed).isEmpty());
    QThread worker;worker.start();client->moveToThread(&worker);nodes->moveToThread(&worker);
    // A live blocked worker is bounded. Its canceled original callback is
    // retained until Qt actually destroys the original queued functor.
    QSemaphore entered,release;
    assert(QMetaObject::invokeMethod(client.data(),[&]{entered.release();release.acquire();},Qt::QueuedConnection));
    assert(entered.tryAcquire(1,1000));QElapsedTimer bounded;bounded.start();
    assert(source.featureAudioSettingsObservation(command()).isEmpty());assert(bounded.elapsed()<1000);
    assert(client->reads==0&&!source._featureAudioSettingsQueue->settled());
    assert(source.featureAudioSettingsObservation(command()).isEmpty());assert(client->reads==0);
    release.release();assert(QMetaObject::invokeMethod(client.data(),[]{},Qt::BlockingQueuedConnection));
    assert(source._featureAudioSettingsQueue->settled());assert(client->reads==0); // No late read/result adoption.
    auto request=command();auto packet=source.featureAudioSettingsObservation(request);assert(!packet.isEmpty());
    assert(client->reads==1&&nodes->reads==1&&input.reads==1);
    auto original=packet.value("source").toMap();assert(!original.value("inputPeakValuesEnabled").toBool());
    // Real typed QObject* properties are converted through their actual Qt
    // metaobjects; the observer does not get a synthetic devices/input ID.
    assert(!original.value("devicesId").toString().isEmpty());assert(original.value("devicesId")!=original.value("inputId"));
    assert(source.featureAudioSettingsObservation(request).isEmpty());assert(client->reads==1);
    input.peak=true;auto next=source.featureAudioSettingsObservation(command());assert(!next.isEmpty());
    assert(next.value("source").toMap().value("inputPeakValuesEnabled").toBool());
    for(const auto& role:{"clientId","devicesId","inputId","nodesId","scriptId"})
        assert(original.value(role)==next.value("source").toMap().value(role));
    std::puts(QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).constData());
    std::puts(QJsonDocument::fromVariant(next).toJson(QJsonDocument::Compact).constData());
    // A wrong native preview type stays unavailable, never interpreted as 0.
    QMetaObject::invokeMethod(client.data(),[&]{client->malformed=true;},Qt::BlockingQueuedConnection);
    assert(source.featureAudioSettingsObservation(command()).isEmpty());
    QMetaObject::invokeMethod(client.data(),[&]{client->malformed=false;},Qt::BlockingQueuedConnection);
    script->setProperty("muted",1);assert(source.featureAudioSettingsObservation(command()).isEmpty());script->setProperty("muted",false);
    auto foreign=command();foreign.insert("runId",QString(32,'f'));assert(source.featureAudioSettingsObservation(foreign).isEmpty());
    InputBoundary replacement;devices.original=&replacement;
    assert(source.featureAudioSettingsObservation(command()).isEmpty());devices.original=&input;
    assert(source.featureAudioSettingsObservation(command()).isEmpty()); // No re-adoption after replacement.
    // Actual child death occurs inside its owning script-thread getter,
    // between devices discovery and input read. No dangling child is used.
    TestScriptingInterface childDeath;childDeath._testResultsLocation=directory.path();DevicesBoundary doomedDevices;auto doomedInput=new InputBoundary;
    doomedDevices.original=doomedInput;doomedDevices.destroyInput=true;script->original=&doomedDevices;
    assert(childDeath.featureAudioSettingsObservation(command()).isEmpty());assert(doomedDevices.original.isNull());script->original=&devices;
    // A queued context destroyed before dispatch retires its original functor;
    // neither a dangling receiver nor any late successful fact is adopted.
    overte::e2e::AudioSettingsQueue queue;auto doomed=new QObject;doomed->moveToThread(&worker);
    QPointer<QObject> doomedWeak(doomed);int lateReads{0};
    assert(QMetaObject::invokeMethod(client.data(),[&]{entered.release();release.acquire();},Qt::QueuedConnection));
    assert(entered.tryAcquire(1,1000));
    assert(QMetaObject::invokeMethod(doomed,[doomed]{delete doomed;},Qt::QueuedConnection));
    assert(queue.read("client",doomed,[&](QObject*){++lateReads;return overte::e2e::AudioSettingsPart{{{"late",true}},{}};}).values.isEmpty());
    assert(!queue.settled());release.release();
    assert(QMetaObject::invokeMethod(client.data(),[]{},Qt::BlockingQueuedConnection));
    assert(doomedWeak.isNull()&&queue.settled()&&lateReads==0);
    // Original TSI dispatch is independently bounded if its live GUI queue is
    // blocked by this host test. Returning to the GUI may only retire it.
    TestScriptingInterface dispatch;dispatch._testResultsLocation=directory.path();int delivered{0};QThread caller;
    QObject calling;calling.moveToThread(&caller);caller.start();
    const auto originalGets=DependencyManager::gets;
    assert(QMetaObject::invokeMethod(&calling,[&]{assert(dispatch.featureAudioSettingsObservation(command()).isEmpty());++delivered;},Qt::QueuedConnection));
    bounded.restart();while(!dispatch._featureAudioSettingsQueue->settled()){QThread::msleep(1);if(bounded.elapsed()>1500)break;}
    // Ensure caller completed its bounded wait without pumping the GUI queue.
    assert(QMetaObject::invokeMethod(&calling,[]{},Qt::BlockingQueuedConnection));
    assert(delivered==1&&DependencyManager::gets==originalGets);
    assert(dispatch.featureAudioSettingsObservation(command()).isEmpty());assert(DependencyManager::gets==originalGets);
    QCoreApplication::processEvents();assert(dispatch._featureAudioSettingsQueue->settled());
    assert(DependencyManager::gets==originalGets);
    TestScriptingInterface liveDispatch;liveDispatch._testResultsLocation=directory.path();QSemaphore completed;
    QVariantMap dispatched;
    assert(QMetaObject::invokeMethod(&calling,[&]{dispatched=liveDispatch.featureAudioSettingsObservation(command());completed.release();},Qt::QueuedConnection));
    bounded.restart();while(!completed.tryAcquire(1,0) && bounded.elapsed()<2000){QCoreApplication::processEvents();QThread::msleep(1);}
    assert(!dispatched.isEmpty()&&liveDispatch._featureAudioSettingsQueue->settled());
    assert(QMetaObject::invokeMethod(&calling,[&]{calling.moveToThread(app.thread());},Qt::BlockingQueuedConnection));caller.quit();assert(caller.wait(3000));
    // The weak originals also detect actual QObject death independently.
    overte::e2e::AudioSettingsObservation weak;QObject a,b,c,d;auto dying=std::make_unique<QObject>();
    auto req=command();assert(weak.admit(req));const QMap<QString,QPointer<QObject>> roles{{"client",&a},{"devices",&b},
        {"input",dying.get()},{"nodes",&c},{"script",&d}};
    assert(!weak.snapshot(req,roles,{{"original",true}}).isEmpty());dying.reset();req=command();assert(weak.admit(req));
    auto replaced=roles;replaced["input"]=&replacement;assert(weak.snapshot(req,replaced,{{"original",true}}).isEmpty());
    QMetaObject::invokeMethod(client.data(),[&]{client->moveToThread(app.thread());nodes->moveToThread(app.thread());},Qt::BlockingQueuedConnection);
    worker.quit();assert(worker.wait(3000));return 0;
}
#include "audio-settings-observation-test.moc"
