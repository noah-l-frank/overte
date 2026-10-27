// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include <QCryptographicHash>
#include <QFileInfo>
#include <QMutex>
#include <QMutexLocker>
#include <QHash>
#include <QSet>
#include <QStringList>
#include <QRegularExpression>
#include <atomic>
#include <memory>

namespace overte::e2e {
// Values and weak diagnostic leases only. No ScriptEngine, uploader, callback
// or product resource is retained. Existing HTTP/upload source wires stay
// literal; the relationship uses their actual original event/upload IDs.
class IOSSnapshotCausalDispatch {
public:
    struct Lease {
        IOSSnapshotCausalDispatch* owner;QString id;
        Lease(IOSSnapshotCausalDispatch* book,const QString& value) : owner(book),id(value) {}
        ~Lease() noexcept {owner->released(id);}
    };
    using Pointer=std::shared_ptr<Lease>;
    static IOSSnapshotCausalDispatch* get() noexcept {
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)
        try {if (!enabled()) {return nullptr;}static auto* book=new IOSSnapshotCausalDispatch;return book;}
        catch (...) {return nullptr;}
#else
        return nullptr;
#endif
    }
    static Pointer current() noexcept {return local();}
    class Scope {
    public:
        Scope(const Pointer& lease,const QString& stage) noexcept : _lease(lease),_previous(local()) {
            local()=lease;if (lease) {_hop=lease->owner->entered(lease->id,stage);}
        }
        ~Scope() noexcept {
            if (_lease) {_lease->owner->left(_lease->id,_hop);}local()=_previous;
        }
        Scope(const Scope&)=delete;Scope& operator=(const Scope&)=delete;
    private:
        Pointer _lease,_previous;QString _hop;
    };
    Pointer begin(const QString& path,const QVariantMap& caller,const QVariantMap& http) noexcept {
        Pointer lease;protect([&] {
            QMutexLocker lock(&_mutex);if (!enabled() || _calls.size()>=64) {fail();return;}
            const auto name=QFileInfo(path).fileName();
            const bool owned=QFileInfo(path).isAbsolute() && QRegularExpression(
                "\\Aparity-[0-9a-f]{16}-(?:still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,16}_[0-9]{1,10}\\.(?:png|jpg|jpeg|gif|webp)\\z").match(name).hasMatch();
            const auto id=uuid();lease=std::make_shared<Lease>(this,id);
            Entry entry;entry.original={{"instance",id},{"bornEpochMs",epoch()},
                {"file",QVariantMap{{"privateName",owned},{"name",owned?name:QString()},
                    {"nameSha256",QString::fromLatin1(QCryptographicHash::hash(name.toUtf8(),QCryptographicHash::Sha256).toHex())}}},
                {"caller",caller},{"http",http}};
            entry.lease=lease;_calls.insert(id,entry);_order.append(id);
        });return lease;
    }
    void associated(const QString& upload) noexcept {
        const auto lease=current();if (!lease) {return;}
        protect([&] {
            QMutexLocker lock(&_mutex);
            if (lease->owner!=this || !_calls.contains(lease->id) || upload.isEmpty()
                    || !_calls[lease->id].upload.isEmpty() || _uploads.contains(upload)) {fail();return;}
            _calls[lease->id].upload=upload;_calls[lease->id].associated=epoch();_uploads.insert(upload);
        });
    }
    QVariantMap read(const QString& request,const QString& run) noexcept {
        QVariantMap result;protect([&] {
            // Freeze event mutation before the original bracket begins. Every
            // returned event then predates clockBefore without being retimed.
            QMutexLocker lock(&_mutex);
            result=_bracket.read("iosSnapshotCausalDispatchVersion","native-process-snapshot-causal-dispatch",request,run,[&] {
                QVariantList calls;
                for (const auto& id:_order) {
                    const auto& entry=_calls[id];auto row=entry.original;row["hops"]=entry.hops;
                    row["upload"]=entry.upload.isEmpty()?QVariant():QVariant(entry.upload);
                    row["associatedEpochMs"]=entry.associated?QVariant(entry.associated):QVariant();
                    row["releasedEpochMs"]=entry.released?QVariant(entry.released):QVariant();
                    row["leaseAlive"]=!entry.lease.expired();calls.append(row);
                }
                return QVariantMap{{"complete",!_failed.load(std::memory_order_acquire)},{"calls",calls}};
            });
        });return result;
    }
private:
    struct Entry {
        QVariantMap original;QVariantList hops;std::weak_ptr<Lease> lease;
        QString upload;qint64 associated {0},released {0};
    };
    static Pointer& local() noexcept {static thread_local Pointer value;return value;}
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    static QString uuid() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    void fail() noexcept {_failed.store(true,std::memory_order_release);}
    template<typename Function> void protect(Function&& function) noexcept {
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)
        try {function();}catch (...) {fail();}
#else
        fail();
#endif
    }
    qint64 epoch() {const auto now=QDateTime::currentMSecsSinceEpoch();if (now<=0 || now<_epoch) {fail();}_epoch=now;return now;}
    QString entered(const QString& id,const QString& stage) noexcept {
        QString result;protect([&] {
            QMutexLocker lock(&_mutex);
            if (!_calls.contains(id) || _calls[id].released!=0 || _calls[id].hops.size()>=16
                    || (stage!="window" && stage!="application" && stage!="snapshot" && stage!="snapshot-queue")) {fail();return;}
            result=uuid();_calls[id].hops.append(QVariantMap{{"instance",result},{"stage",stage},
                {"enteredEpochMs",epoch()},{"leftEpochMs",QVariant()}});
        });return result;
    }
    void left(const QString& id,const QString& hop) noexcept {
        protect([&] {
            QMutexLocker lock(&_mutex);if (!_calls.contains(id) || hop.isEmpty()) {fail();return;}
            auto& rows=_calls[id].hops;
            for (int index=0;index<rows.size();++index) {
                auto row=rows[index].toMap();if (row.value("instance")!=QVariant(hop)) {continue;}
                if (row.value("leftEpochMs").isValid()) {fail();return;}
                row["leftEpochMs"]=epoch();rows[index]=row;return;
            }
            fail();
        });
    }
    void released(const QString& id) noexcept {
        protect([&] {QMutexLocker lock(&_mutex);if (!_calls.contains(id) || _calls[id].released) {fail();return;}_calls[id].released=epoch();});
    }
    QMutex _mutex;NativeReadBracket _bracket;QHash<QString,Entry> _calls;QStringList _order;QSet<QString> _uploads;
    std::atomic_bool _failed {false};qint64 _epoch {0};
};
} // namespace overte::e2e
#endif
