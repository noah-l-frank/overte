// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QMap>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QRegularExpression>
#include <QSharedPointer>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <memory>
namespace overte::e2e {
// Passive actual storage notifications. Render fields are recorded on their
// original render update thread, never read concurrently from the GUI. Only
// weak handles survive a notification; no cache lookup, GPU access or deletion.
class CreatePolyvoxResources {
public:
    static CreatePolyvoxResources& get(){static CreatePolyvoxResources value;return value;}
    bool arm(const QString& run){
        if(!gate() || QThread::currentThread()!=QCoreApplication::instance()->thread() || !identifier(run)){return false;}
        QMutexLocker lock(&_mutex);if(!_valid){return false;}
        if(!_runs.contains(run)){if(_runs.size()>=4){return false;}_runs.insert(run,{});}return true;
    }
    bool entity(const QString& run,const QUuid& id,const std::shared_ptr<void>& mesh){
        if(!gate() || id.isNull() || QThread::currentThread()!=QCoreApplication::instance()->thread()){return false;}
        QMutexLocker lock(&_mutex);if(!_valid || !_runs.contains(run)){return false;}
        auto& state=_runs[run];const auto key=id.toString(QUuid::WithoutBraces);
        if(!state.bindings.contains(key)){if(state.bindings.size()>=32){return fail();}state.bindings.insert(key,{});}
        auto& binding=state.bindings[key];binding.entityMesh=remember(state.meshes,mesh,nullptr,128);return _valid;
    }
    void rendered(const QUuid& id,const std::shared_ptr<void>& renderer,QObject* guard,
                  const std::shared_ptr<void>& mesh,const QList<QSharedPointer<QObject>>& textures){
        if(!gate()){return;}QMutexLocker lock(&_mutex);if(!_valid){return;}
        if(id.isNull() || !renderer || !guard || textures.size()!=3){fail();return;}
        const auto key=id.toString(QUuid::WithoutBraces);
        for(auto run=_runs.begin();run!=_runs.end();++run){
            auto& state=run.value();if(!state.bindings.contains(key)){continue;}auto& binding=state.bindings[key];
            binding.renderer=remember(state.renderers,renderer,guard,64);binding.rendererMesh=remember(state.meshes,mesh,nullptr,128);
            binding.textures.clear();for(const auto& texture:textures){binding.textures.append(rememberTexture(state.textures,texture));}
            if(binding.renderObservations>=1000000000){fail();return;}++binding.renderObservations;
        }
    }
    QVariantMap snapshot(const QString& run){
        if(!gate() || QThread::currentThread()!=QCoreApplication::instance()->thread()){return {};}
        QMutexLocker lock(&_mutex);if(!_valid || !_runs.contains(run)){return {};}
        auto& state=_runs[run];if(state.sequence>=1000000000){fail();return {};}
        QVariantList bindings;for(auto it=state.bindings.cbegin();it!=state.bindings.cend();++it){
            QVariantList textures;for(const auto& id:it->textures){textures.append(nullable(id));}
            bindings.append(QVariantMap{{"entityId",it.key()},{"entityMesh",nullable(it->entityMesh)},
                {"renderer",nullable(it->renderer)},{"rendererMesh",nullable(it->rendererMesh)},
                {"textures",textures},{"renderObservations",it->renderObservations}});
        }
        QVariantList textures;for(auto it=state.textures.cbegin();it!=state.textures.cend();++it){
            textures.append(QVariantMap{{"id",it.key()},{"firstObservedEpochMs",it->epoch},
                {"alive",!it->object.isNull() || !it->guard.isNull()}});
        }
        return {{"createPolyvoxResourcesVersion",1},{"instance",_instance},{"sourceSequence",++state.sequence},
            {"bindings",bindings},{"meshes",history(state.meshes)},{"renderers",history(state.renderers)},{"textures",textures}};
    }
private:
    struct Original{qint64 epoch;std::weak_ptr<void> object;QPointer<QObject> guard;};
    struct Texture{qint64 epoch;QWeakPointer<QObject> object;QPointer<QObject> guard;};
    struct Binding{QString entityMesh,renderer,rendererMesh;QStringList textures;int renderObservations{0};};
    struct State{QMap<QString,Binding> bindings;QMap<QString,Original> meshes,renderers;QMap<QString,Texture> textures;int sequence{0};};
    QMutex _mutex;QMap<QString,State> _runs;bool _valid{true};qint64 _epoch{0};
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    static bool identifier(const QString& value){return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch();}
    static bool gate(){return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    static QVariant nullable(const QString& value){return value.isEmpty() ? QVariant() : QVariant(value);}
    bool fail(){_valid=false;return false;}
    qint64 epoch(){const auto now=QDateTime::currentMSecsSinceEpoch();if(now<=0 || now<_epoch){fail();return 0;}return _epoch=now;}
    QString remember(QMap<QString,Original>& rows,const std::shared_ptr<void>& value,QObject* guard,int limit){
        if(!value){return {};}
        for(auto it=rows.cbegin();it!=rows.cend();++it){
            if(!it->object.owner_before(value) && !value.owner_before(it->object)){
                const auto original=it->object.lock();
                if(!original || original.get()!=value.get() || it->guard.data()!=guard){fail();return {};}return it.key();
            }
        }
        const auto now=epoch();if(!now || rows.size()>=limit){fail();return {};}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');rows.insert(id,{now,value,guard});return id;
    }
    QString rememberTexture(QMap<QString,Texture>& rows,const QSharedPointer<QObject>& value){
        if(!value){return {};}
        for(auto it=rows.cbegin();it!=rows.cend();++it){
            const auto original=it->object.toStrongRef();if(original && original.data()==value.data()){
                if(it->guard.data()!=value.data()){fail();return {};}return it.key();
            }
        }
        const auto now=epoch();if(!now || rows.size()>=96){fail();return {};}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');rows.insert(id,{now,value.toWeakRef(),value.data()});return id;
    }
    static QVariantList history(const QMap<QString,Original>& rows){
        QVariantList result;for(auto it=rows.cbegin();it!=rows.cend();++it){result.append(QVariantMap{{"id",it.key()},
            {"firstObservedEpochMs",it->epoch},{"alive",!it->object.expired() || !it->guard.isNull()}});}return result;
    }
};
}
#endif
