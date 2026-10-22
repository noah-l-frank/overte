// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDataStream>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <atomic>
#include <functional>
#include <memory>
namespace overte::e2e {
inline bool avatarPreferenceKey(const QString& key) {
    // The actual QSettings key API drops empty slash components. Include
    // those aliases in mutation tracking while retaining every original raw
    // key in snapshots; the native headPitch Handle itself uses "Avatar/".
    const auto normalized=key.split('/',Qt::SkipEmptyParts).join('/');
    return normalized=="Avatar" || normalized.startsWith("Avatar/")
        || normalized=="fullPrivate/Avatar" || normalized.startsWith("fullPrivate/Avatar/");
}
inline QVariantMap avatarPreferenceRaw(bool present,const QVariant& value) {
    QByteArray bytes;QDataStream stream(&bytes,QIODevice::WriteOnly);stream.setVersion(QDataStream::Qt_5_15);stream<<value;
    if(stream.status()!=QDataStream::Ok || bytes.size()>65536) {return {};}
    return {{"present",present},{"typeId",value.userType()},{"typeName",value.typeName() ? QVariant(QString::fromLatin1(value.typeName())) : QVariant()},
        {"base64",QString::fromLatin1(bytes.toBase64())},{"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}};
}
// Read-only snapshots cover the original lazy Handle fields as well as the
// actual Manager mutations. A Handle's get()/maybeInit() cannot be used as a
// passive baseline: it may initialize and insert a previously absent key.
class AvatarPreferenceBarrier {
public:
    class Mutation {
    public:
        Mutation(AvatarPreferenceBarrier& owner,const QString& key):_owner(owner) {
            _tracked=QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")
                && (key.isEmpty() || key.split('/',Qt::SkipEmptyParts).join('/')=="fullPrivate" || avatarPreferenceKey(key));
            if(_tracked) {++_owner._attempts;_owner._mutex.lock();++_owner._pending;}
        }
        ~Mutation() {
            if(_tracked) {
                if(_owner._pending<1 || _owner._sequence>=9007199254740991LL) {_owner._valid=false;}
                else {--_owner._pending;++_owner._sequence;}
                --_owner._attempts;_owner._mutex.unlock();
            }
        }
        Mutation(const Mutation&)=delete;Mutation& operator=(const Mutation&)=delete;
    private:AvatarPreferenceBarrier& _owner;bool _tracked{false};
    };
    bool reading()const {
        if(!_mutex.tryLock()) {return false;}
        const bool result=_reader==QThread::currentThread();_mutex.unlock();return result;
    }
    QVariantMap read(const std::function<QVariantMap()>& cache,const std::function<QVariantMap()>& writer) {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !cache || !writer || !_mutex.tryLock()) {return {};}
        if(!_valid || _pending || _attempts.load()!=0) {_mutex.unlock();return {};}
        QElapsedTimer elapsed;elapsed.start();const auto started=QDateTime::currentMSecsSinceEpoch(),sequence=_sequence;
        if(started<=0 || started<_epoch) {_valid=false;_mutex.unlock();return {};}
        const auto original=_reader;_reader=QThread::currentThread();const auto first=cache();_reader=original;_mutex.unlock();
        if(first.isEmpty()) {return {};}
        // No preference/Manager mutex spans the original worker queue or file.
        const auto actualWriter=writer();if(!_mutex.tryLock()) {return {};}
        _reader=QThread::currentThread();const auto last=cache();_reader=original;
        const auto finished=QDateTime::currentMSecsSinceEpoch(),duration=elapsed.elapsed();
        const bool valid=_valid && !_pending && _attempts.load()==0 && sequence==_sequence && finished>=started && finished>=_epoch
            && finished-started<=1500 && duration<=1500 && first==last && !actualWriter.isEmpty();
        if(valid) {_epoch=finished;}
        _mutex.unlock();
        return valid ? QVariantMap{{"avatarPreferenceBarrierVersion",1},{"instance",_instance},{"mutationSequence",sequence},
            {"capturedEpochMs",finished},{"elapsedMs",duration},{"cache",first},{"writer",actualWriter}} : QVariantMap{};
    }
private:
    mutable QRecursiveMutex _mutex;QThread* _reader{nullptr};std::atomic<qint64>_attempts{0};qint64 _pending{0},_sequence{0},_epoch{0};bool _valid{true};
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
}
#endif
