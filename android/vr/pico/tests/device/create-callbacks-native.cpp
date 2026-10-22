// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#define OVERTE_E2E_FEATURE_TESTS
#include "CreateCallbackObservation.h"
#include "RequiredModuleObservation.h"
#include <QHash>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QObject>
#include <QRegularExpression>
#include <QSet>
#include <QSharedPointer>
#include <QThread>
#include <QTextStream>
#include <cassert>
#include <thread>
#include <vector>

struct Manager {
    overte::e2e::RequiredModuleObservation code;
    std::shared_ptr<overte::e2e::CreateCallbackObservation> callbacks {std::make_shared<overte::e2e::CreateCallbackObservation>()};
    QVariantMap featureLoadMembership() const {return code.loadMembership();}
    QVariantMap featureCompiledSources() const {return code.compiledSources();}
    auto featureCreateCallbacks() const {return callbacks;}
};
using ScriptManagerPointer=QSharedPointer<Manager>;
struct ScriptEngines {
    QMutex _allScriptsMutex;QSet<ScriptManagerPointer> _allKnownScriptManagers;quint64 _featureKnownScriptRevision {0};
    QVariantMap featureCreateCallbackObservation();
};
std::shared_ptr<ScriptEngines> engines;
bool enginesAvailable=true;int engineGets=0;
struct DependencyManager {
    template<typename T> static bool isSet(){return enginesAvailable;}
    template<typename T> static std::shared_ptr<T> get(){++engineGets;return engines;}
};
struct Lifecycle {QVariantMap snapshot() const {return {{"launches",1}};}};
class TestScriptingInterface:public QObject {
public:
    QVariantMap featureCreateCallbacks(const QString& requestId);
    QString _testResultsLocation {"/owned-private-result"},_featureObservationInstance {QString(32,'f')};
    std::shared_ptr<Lifecycle> _featureLifecycle {std::make_shared<Lifecycle>()};
    quint64 _featureCreateCallbacksSequence {0};QHash<QString,QVariantMap> _featureCreateCallbacksResults;
};
#include "OriginalCreateCallbacks.inc"
QVariantMap source(const std::shared_ptr<overte::e2e::CreateCallbackObservation>& value){return value->snapshot();}
int dispatches(const QVariantMap& value){return value["proxies"].toList().first().toMap()["dispatches"].toInt();}
bool complete(const std::shared_ptr<overte::e2e::CreateCallbackObservation>& value){return source(value)["complete"].toBool();}

int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);engines=std::make_shared<ScriptEngines>();TestScriptingInterface target;
    auto manager=ScriptManagerPointer::create();
    if (!app.arguments().contains("--testScript")) {
        assert(source(manager->callbacks).isEmpty());assert(target.featureCreateCallbacks(QString(32,'a')).isEmpty());return 0;
    }
    manager->code.assignedLoadURL(QUrl("file:///original/defaultScripts.js"),1);
    manager->code.compiled(17,"file:///original/create/edit.js","original callback code");
    engines->_allKnownScriptManagers.insert(manager);engines->_featureKnownScriptRevision=1;
    const auto proxy=manager->callbacks->born("WindowScriptingInterface","browseChanged(QString)");assert(proxy.size()==32);
    const auto callback=manager->callbacks->connected(proxy,17);assert(callback.size()==32);
    enginesAvailable=false;assert(target.featureCreateCallbacks(QString(32,'a')).isEmpty());assert(engineGets==0);enginesAvailable=true;
    QThread idle;auto foreign=new TestScriptingInterface;foreign->moveToThread(&idle);
    assert(foreign->featureCreateCallbacks(QString(32,'a')).isEmpty());assert(engineGets==0);
    idle.start();assert(QMetaObject::invokeMethod(foreign,[&]{foreign->moveToThread(app.thread());},Qt::BlockingQueuedConnection));
    idle.quit();assert(idle.wait(1000));delete foreign;
    const auto first=target.featureCreateCallbacks(QString(32,'a'));
    assert(first["processId"].toLongLong()==app.applicationPid());assert(first["sequence"].toULongLong()==1);
    auto dispatch=manager->callbacks->dispatch(proxy);assert(dispatches(source(manager->callbacks))==1);
    manager->callbacks->disconnected(proxy,callback);
    assert(source(manager->callbacks)["callbacks"].toList().first().toMap()["disconnectedEpochMs"].toLongLong()>0);
    assert(dispatches(source(manager->callbacks))==1); // A self-disconnected live callback remains a resource.
    const auto during=target.featureCreateCallbacks(QString(32,'c'));
    auto nested=manager->callbacks->dispatch(proxy);assert(dispatches(source(manager->callbacks))==2);
    nested.reset();assert(dispatches(source(manager->callbacks))==1);
    dispatch.reset();assert(dispatches(source(manager->callbacks))==0);
    manager->callbacks->retired(proxy);assert(complete(manager->callbacks));
    assert(source(manager->callbacks)["proxies"].toList().first().toMap()["retiredEpochMs"].toLongLong()>0);
    assert(target.featureCreateCallbacks(QString(32,'a'))==first); // Original native packet, original times.
    const auto after=target.featureCreateCallbacks(QString(32,'d'));
    for (const auto& packet:{first,during,after}) { QTextStream(stdout)<<QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact)<<'\n'; }
    auto pending=ScriptManagerPointer::create();engines->_allKnownScriptManagers.insert(pending);++engines->_featureKnownScriptRevision;
    assert(engines->featureCreateCallbackObservation()["managers"].toList().size()==2); // Unassigned/finished members are retained.
    for(int i=1;i<510;++i){const auto id=QString::number(i,16).rightJustified(32,'0');assert(!target.featureCreateCallbacks(id).isEmpty());}
    assert(target.featureCreateCallbacks(QString(32,'b')).isEmpty());assert(target.featureCreateCallbacks(QString(32,'a'))==first);
    target._featureLifecycle.reset();assert(target.featureCreateCallbacks(QString(32,'a')).isEmpty());
    auto retained=std::make_shared<overte::e2e::CreateCallbackObservation>();const auto p=retained->born("WindowScriptingInterface","saveFileChanged(QString)");
    auto active=retained->dispatch(p);retained->retired(p);assert(!complete(retained));active.reset();assert(!complete(retained));
    auto exhausted=std::make_shared<overte::e2e::CreateCallbackObservation>();
    for(int i=0;i<128;++i){auto id=exhausted->born("WindowScriptingInterface","browseChanged(QString)");assert(!id.isEmpty());exhausted->retired(id);}
    assert(complete(exhausted));assert(exhausted->born("WindowScriptingInterface","browseChanged(QString)").isEmpty());assert(!complete(exhausted));
    auto stress=std::make_shared<overte::e2e::CreateCallbackObservation>();const auto s=stress->born("WindowScriptingInterface","browseChanged(QString)");
    std::thread writer([&]{for(int i=0;i<128;++i){auto lease=stress->dispatch(s);}});
    for(int i=0;i<128;++i){assert(complete(stress));}writer.join();assert(dispatches(source(stress))==0);
    auto duplicate=std::make_shared<overte::e2e::CreateCallbackObservation>();const auto d=duplicate->born("WindowScriptingInterface","saveFileChanged(QString)");
    const auto c=duplicate->connected(d,17);duplicate->disconnected(d,c);duplicate->disconnected(d,c);assert(!complete(duplicate));
    auto bounded=std::make_shared<overte::e2e::CreateCallbackObservation>();const auto b=bounded->born("WindowScriptingInterface","browseChanged(QString)");
    for(int i=0;i<512;++i){const auto id=bounded->connected(b,17);assert(!id.isEmpty());bounded->disconnected(b,id);}
    assert(complete(bounded));assert(bounded->connected(b,17).isEmpty());assert(!complete(bounded));
    return 0;
}
