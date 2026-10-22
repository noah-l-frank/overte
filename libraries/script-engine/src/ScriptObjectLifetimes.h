// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QMap>
#include <QMetaObject>
#include <QObject>
#include <QRegularExpression>
#include <QVariantList>
#include <QVariantMap>
#include <QThread>
#include <mutex>

namespace overte::e2e {
// Observe actual QObject destruction, including deleteLater after the public
// running/membership table has dropped the manager. No strong object reference,
// stop/quit/delete/event pumping, VM evaluation or requested outcome is held.
class ScriptObjectLifetimes {
public:
    void created(const QString& id,QObject* manager,QObject* engine) {
        if (!enabled()) {return;}
        {
            std::lock_guard<std::mutex> lock(_mutex);
            if (!_valid || !identity(id) || !manager || !engine || manager==engine
                    || _objects.contains(id) || _objects.size()>=128 || !advance()) {_valid=false;return;}
            _objects.insert(id,Row{QVariantMap{{"instance",id},{"registeredEpochMs",_epoch},
                {"managerAlive",true},{"engineAlive",true},{"workerCreated",false},{"workerAlive",false},
                {"managerDestroyedEpochMs",0},{"engineDestroyedEpochMs",0},
                {"workerCreatedEpochMs",0},{"workerDestroyedEpochMs",0}}, {},false,reinterpret_cast<quintptr>(manager),reinterpret_cast<quintptr>(engine)});
        }
        // Constructors own these actual objects until registration completes.
        // Never hold the source mutex while acquiring a QObject connection lock.
        auto managerConnection=QObject::connect(manager,&QObject::destroyed,manager,
            [this,id] {destroyed(id,"manager");},Qt::DirectConnection);
        auto engineConnection=QObject::connect(engine,&QObject::destroyed,engine,
            [this,id] {destroyed(id,"engine");},Qt::DirectConnection);
        std::lock_guard<std::mutex> lock(_mutex);
        auto& row=_objects[id];row.managerConnection=managerConnection;
        row.tracked=bool(managerConnection)&&bool(engineConnection);
        if (!row.tracked) {_valid=false;}
    }

    void worker(const QString& id,QThread* actual) {
        if (!enabled()) {return;}
        {
            std::lock_guard<std::mutex> lock(_mutex);
            if (!_valid || !_objects.contains(id) || !actual) {_valid=false;return;}
            auto& row=_objects[id];auto& value=row.value;
            if (!row.tracked || reinterpret_cast<quintptr>(actual)==row.managerAddress || reinterpret_cast<quintptr>(actual)==row.engineAddress
                    || !value.value("managerAlive").toBool() || value.value("workerCreated").toBool()
                    || !advance()) {_valid=false;return;}
            row.tracked=false;value["workerCreated"]=true;value["workerAlive"]=true;value["workerCreatedEpochMs"]=_epoch;
        }
        auto connection=QObject::connect(actual,&QObject::destroyed,actual,
            [this,id] {destroyed(id,"worker");},Qt::DirectConnection);
        std::lock_guard<std::mutex> lock(_mutex);
        _objects[id].tracked=bool(connection);if (!connection) {_valid=false;}
    }

    // ScriptManager::disconnectNonEssentialSignals disconnects every outgoing
    // manager signal. Reattach ONLY this observer on the same original object.
    void reconnect(const QString& id,QObject* actual) {
        if (!enabled()) {return;}
        QMetaObject::Connection previous;
        {
            std::lock_guard<std::mutex> lock(_mutex);
            if (!_valid || !_objects.contains(id) || !actual) {_valid=false;return;}
            auto& row=_objects[id];
            if (reinterpret_cast<quintptr>(actual)!=row.managerAddress || !row.value.value("managerAlive").toBool()) {_valid=false;return;}
            previous=row.managerConnection;row.tracked=false;
        }
        QObject::disconnect(previous);
        auto connection=QObject::connect(actual,&QObject::destroyed,actual,
            [this,id] {destroyed(id,"manager");},Qt::DirectConnection);
        std::lock_guard<std::mutex> lock(_mutex);
        auto& row=_objects[id];row.managerConnection=connection;row.tracked=bool(connection);
        if (!connection) {_valid=false;}
    }

    QVariantMap snapshot() {
        if (!enabled()) {return {};}
        std::lock_guard<std::mutex> lock(_mutex);
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (!_valid || now<=0 || now<_epoch) {_valid=false;return {};}
        _epoch=now;QVariantList values;
        for (auto it=_objects.cbegin();it!=_objects.cend();++it) {
            if (!it.value().tracked) {return {};}
            values.append(it.value().value);
        }
        return {{"complete",true},{"revision",static_cast<qulonglong>(_revision)},
            {"capturedEpochMs",now},{"objects",values}};
    }
private:
    struct Row {QVariantMap value;QMetaObject::Connection managerConnection;bool tracked;quintptr managerAddress,engineAddress;};
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    static bool identity(const QString& id) {return QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch();}
    bool advance() {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch || _revision>=1000000000) {return false;}
        _epoch=now;++_revision;return true;
    }
    void destroyed(const QString& id,const QString& kind) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_valid || !_objects.contains(id)) {_valid=false;return;}
        auto& value=_objects[id].value;const auto alive=kind+"Alive";
        if (!value.value(alive).toBool() || !advance()) {_valid=false;return;}
        value[alive]=false;value[kind+"DestroyedEpochMs"]=_epoch;
    }
    std::mutex _mutex;QMap<QString,Row> _objects;bool _valid{true};qint64 _epoch{0};quint64 _revision{0};
};

inline ScriptObjectLifetimes& scriptObjectLifetimes() {
    // QObject death callbacks may arrive during application shutdown. The
    // bounded test-only metadata outlives them and owns no product object.
    static auto* source=new ScriptObjectLifetimes;
    return *source;
}
} // namespace overte::e2e
#endif
