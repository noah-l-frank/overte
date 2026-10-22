// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Compile the whole original getter with explicit AudioClient/Audio/NodeList
// boundaries. The audio engine, microphone and mixer are not run here.
#include <QCoreApplication>
#include <QJsonDocument>
#include <QSharedPointer>
#include <QTemporaryDir>
#include <QThread>
#include <cassert>
#include <cstdio>
#include <functional>
#include <memory>
#include "tests/device/native/AudioSettingsObservation.h"
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
    InputBoundary* original{nullptr};
    InputBoundary* input(){assert(thread()==QThread::currentThread());return original;}
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
    // The weak originals also detect actual QObject death independently.
    overte::e2e::AudioSettingsObservation weak;QObject a,b,c,d;auto dying=std::make_unique<QObject>();
    auto req=command();assert(weak.admit(req));const QMap<QString,QObject*> roles{{"client",&a},{"devices",&b},
        {"input",dying.get()},{"nodes",&c},{"script",&d}};
    assert(!weak.snapshot(req,roles,{{"original",true}}).isEmpty());dying.reset();req=command();assert(weak.admit(req));
    auto replaced=roles;replaced["input"]=&replacement;assert(weak.snapshot(req,replaced,{{"original",true}}).isEmpty());
    QMetaObject::invokeMethod(client.data(),[&]{client->moveToThread(app.thread());nodes->moveToThread(app.thread());},Qt::BlockingQueuedConnection);
    worker.quit();assert(worker.wait(3000));return 0;
}
#include "audio-settings-observation-test.moc"
