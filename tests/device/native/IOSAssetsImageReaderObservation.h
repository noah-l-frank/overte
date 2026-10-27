// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <ResourceCache.h>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <atomic>
#include <exception>
#include <memory>

namespace overte::e2e {
// ImageReader observations only. No KTX task, arbitrary QByteArray copy,
// QRunnable base, pool, decoder or GPU completion is established here.
// Independent source1; ModelOrigin History5 and its existing joins are separate.
class IOSAssetsImageReaderObservation {
public:
    static void unavailable() noexcept {failed().store(true);}
    static bool enabled() noexcept {
        QT_TRY {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
        QT_CATCH (...) {unavailable();return false;}
    }
    static quint64 created(const QWeakPointer<Resource>& lease,const QString& resourceId,const std::shared_ptr<void>& marker,
            const std::shared_ptr<const void>& source,const QUrl& url,qsizetype bytes) noexcept {
        if (!enabled()) {return 0;}
        QT_TRY {
            if (!main()) {unavailable();return 0;}
            auto resource=lease.toStrongRef();
            const auto resourceUrl=url.toEncoded(QUrl::FullyEncoded);
            if (!resource || resourceId.size()!=32 || !marker || !source || resource->thread()!=QCoreApplication::instance()->thread()
                    || resourceUrl.size()>4096 || bytes<0) {unavailable();return 0;}
            auto& owner=state();QMutexLocker lock(&owner.mutex);
            if (owner.tasks.size()>=64) {unavailable();return 0;}
            Task row;row.object=resource.data();row.lease=lease;row.marker=marker;row.source=source;
            row.value={{"id",nonce()},{"resourceId",resourceId},
                {"resourceUrlFullyEncodedBytes",qlonglong(resourceUrl.size())},
                {"resourceUrlFullyEncodedSha256",QString::fromLatin1(QCryptographicHash::hash(resourceUrl,QCryptographicHash::Sha256).toHex())},
                {"constructorContentBytes",qlonglong(bytes)},
                {"constructorEntered",owner.clock()},{"constructorReturned",QVariant()},
                {"runEntered",QVariant()},{"runReturned",QVariant()},{"runUnwound",QVariant()},
                {"readEntered",QVariant()},{"readReturned",QVariant()},{"readUnwound",QVariant()}};
            owner.tasks.append(row);return quint64(owner.tasks.size());
        } QT_CATCH (...) {unavailable();return 0;}
    }
    static void constructed(quint64 task) noexcept {phase(task,"constructorReturned");}
    class Body {
    public:
        Body(quint64 task,bool run) noexcept : _task(task),_run(run),_exceptions(std::uncaught_exceptions()) {phase(_task,_run ? "runEntered" : "readEntered");}
        ~Body() {
            const bool unwound=std::uncaught_exceptions()>_exceptions;
            phase(_task,_run ? (unwound ? "runUnwound" : "runReturned") : (unwound ? "readUnwound" : "readReturned"));
        }
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:quint64 _task;bool _run;int _exceptions;
    };
    class Dispatch {
    public:
        Dispatch(quint64 task,Resource* target,const std::shared_ptr<const void>& gpu,int width,int height,const char* branch) noexcept
            : _previous(activeDispatch()) {
            _token=beginDispatch(task,target,gpu,width,height,branch);
            activeDispatch()=_token;
        }
        void returned(bool accepted) noexcept {_returned=true;invoked(_token,accepted);}
        ~Dispatch() {if (_token && !_returned) {unavailable();}activeDispatch()=_previous;}
        Dispatch(const Dispatch&)=delete;Dispatch& operator=(const Dispatch&)=delete;
    private:quint64 _previous{0},_token{0};bool _returned{false};
    };
    class Receiver {
    public:
        Receiver(Resource* target,const std::shared_ptr<const void>& source,const std::shared_ptr<const void>& gpu,int width,int height) noexcept
            : _token(receiving(target,source,gpu,width,height)),_exceptions(std::uncaught_exceptions()) {}
        ~Receiver() {received(_token,std::uncaught_exceptions()>_exceptions);}
        Receiver(const Receiver&)=delete;Receiver& operator=(const Receiver&)=delete;
    private:quint64 _token{0};int _exceptions;
    };
    static QVariantMap snapshot() noexcept {
        if (!enabled() || !main()) {return {};}
        QT_TRY {
            auto& owner=state();QMutexLocker lock(&owner.mutex);QVariantList tasks,dispatches,receivers;
            for (const auto& row:owner.tasks) {
                auto value=row.value;value["derivedMarkerAlive"]=!row.marker.expired();value["originalLeaseAlive"]=!row.lease.isNull();
                value["resourceObjectAlive"]=!row.object.isNull();value["sourceOwnersAlive"]=!row.source.expired();tasks.append(value);
            }
            for (const auto& row:owner.dispatches) {auto value=row.value;value["gpuOwnersAlive"]=row.gpuKnown && !row.gpu.expired();dispatches.append(value);}
            for (const auto& row:owner.receivers) {
                auto value=row.value;value["gpuOwnersAlive"]=row.gpuKnown && !row.gpu.expired();
                value["sourceOwnersAlive"]=!row.source.expired();receivers.append(value);
            }
            // Preserve recorded rows; observer/cap failure is sticky, not a reset.
            return {{"assetImageReaderHistoryVersion",1},{"instance",owner.instance},{"complete",!failed().load()},
                {"clockDomain","native-assets-image-reader-observer"},{"clock",owner.clock()},
                {"tasks",tasks},{"dispatches",dispatches},{"receivers",receivers},
                {"queuedReceiverAttributionAvailable",false},{"ktxCompletionAvailable",false},
                {"byteCopyCompletionAvailable",false},{"basePoolCompletionAvailable",false},
                {"decoderCompletionAvailable",false},{"gpuCompletionAvailable",false},{"resourceRetirementAvailable",false}};
        } QT_CATCH (...) {unavailable();return {};}
    }
private:
    struct Task {QWeakPointer<Resource> lease;QPointer<Resource> object;std::weak_ptr<void> marker;std::weak_ptr<const void> source;QVariantMap value;};
    struct Event {QPointer<Resource> object;std::weak_ptr<const void> gpu,source;const void* gpuAddress{nullptr};
        bool gpuKnown{false};int width{0},height{0};quint64 task{0},receipt{0};QVariantMap value;};
    struct State {
        State() {timer.start();}
        QVariantMap clock() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",timer.elapsed()}};}
        QMutex mutex;QElapsedTimer timer;QString instance{nonce()};QVector<Task> tasks;QVector<Event> dispatches,receivers;
    };
    static std::atomic<bool>& failed() noexcept {static std::atomic<bool> value{false};return value;}
    static_assert(std::atomic<bool>::is_always_lock_free,"ImageReader failure health must not acquire a lock");
    static State& state() {static State value;return value;}
    static quint64& activeDispatch() noexcept {static thread_local quint64 value{0};return value;}
    static bool main() noexcept {const auto app=QCoreApplication::instance();return app && QThread::currentThread()==app->thread();}
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static void phase(quint64 token,const char* field) noexcept {
        if (!token) {return;}
        QT_TRY {
            auto& owner=state();QMutexLocker lock(&owner.mutex);
            if (token>quint64(owner.tasks.size())) {unavailable();return;}
            auto& row=owner.tasks[int(token-1)];
            if (!row.value.value(field).isNull()) {unavailable();return;}
            row.value[field]=owner.clock();
        } QT_CATCH (...) {unavailable();}
    }
    static quint64 beginDispatch(quint64 token,Resource* target,const std::shared_ptr<const void>& gpu,int width,int height,const char* branch) noexcept {
        if (!token) {return 0;}
        QT_TRY {
            auto& owner=state();QMutexLocker lock(&owner.mutex);
            if (token>quint64(owner.tasks.size()) || owner.dispatches.size()>=256) {unavailable();return 0;}
            auto& parent=owner.tasks[int(token-1)];
            if (!target || parent.object.data()!=target || parent.value.value("readEntered").isNull()) {unavailable();return 0;}
            Event row;row.object=parent.object;row.task=token;row.gpu=gpu;row.gpuAddress=gpu.get();row.gpuKnown=bool(gpu);row.width=width;row.height=height;
            row.value={{"id",nonce()},{"taskId",parent.value.value("id")},{"branch",QString::fromLatin1(branch)},{"width",width},{"height",height},
                {"gpuKnown",row.gpuKnown},{"entered",owner.clock()},{"invokeReturned",QVariant()},{"invokeAccepted",QVariant()}};
            owner.dispatches.append(row);return quint64(owner.dispatches.size());
        } QT_CATCH (...) {unavailable();return 0;}
    }
    static void invoked(quint64 token,bool accepted) noexcept {
        if (!token) {return;}
        QT_TRY {
            auto& owner=state();QMutexLocker lock(&owner.mutex);
            if (token>quint64(owner.dispatches.size())) {unavailable();return;}
            auto& row=owner.dispatches[int(token-1)];
            if (!row.value.value("invokeReturned").isNull()) {unavailable();return;}
            row.value["invokeReturned"]=owner.clock();row.value["invokeAccepted"]=accepted;
        } QT_CATCH (...) {unavailable();}
    }
    static quint64 receiving(Resource* target,const std::shared_ptr<const void>& source,const std::shared_ptr<const void>& gpu,int width,int height) noexcept {
        if (!enabled()) {return 0;}
        QT_TRY {
            if (!main()) {unavailable();return 0;}
            auto& owner=state();QMutexLocker lock(&owner.mutex);QString resourceId;
            for (const auto& row:owner.tasks) {if (row.object.data()==target) {resourceId=row.value.value("resourceId").toString();break;}}
            if (resourceId.isEmpty()) {return 0;}
            if (owner.receivers.size()>=256) {unavailable();return 0;}
            Event row;row.object=target;row.gpu=gpu;row.source=source;row.gpuAddress=gpu.get();row.gpuKnown=bool(gpu);row.width=width;row.height=height;
            row.value={{"id",nonce()},{"resourceId",resourceId},{"width",width},{"height",height},{"gpuKnown",row.gpuKnown},
                {"entered",owner.clock()},{"returned",QVariant()},{"unwound",QVariant()},{"dispatchId",QVariant()},
                {"attribution","unavailable-queued-or-other-producer"},{"sourceKnown",bool(source)}};
            const auto active=activeDispatch();
            // A matching value/URL or a lone pending row does not prove which
            // queued producer supplied a Qt event. Only an actual synchronous
            // invoke scope on this thread can provide direct attribution.
            if (active) {
                if (active>quint64(owner.dispatches.size())) {unavailable();return 0;}
                auto& dispatch=owner.dispatches[int(active-1)];
                if (dispatch.object.data()==target && dispatch.gpuAddress==gpu.get()
                        && !dispatch.gpu.owner_before(gpu) && !gpu.owner_before(dispatch.gpu)
                        && dispatch.width==width && dispatch.height==height) {
                    if (dispatch.receipt) {unavailable();return 0;}
                    dispatch.receipt=quint64(owner.receivers.size()+1);row.task=dispatch.task;
                    row.value["dispatchId"]=dispatch.value.value("id");row.value["attribution"]="synchronous-invoke-scope";
                }
            }
            owner.receivers.append(row);return quint64(owner.receivers.size());
        } QT_CATCH (...) {unavailable();return 0;}
    }
    static void received(quint64 token,bool unwound) noexcept {
        if (!token) {return;}
        QT_TRY {
            auto& owner=state();QMutexLocker lock(&owner.mutex);
            if (token>quint64(owner.receivers.size())) {unavailable();return;}
            auto& row=owner.receivers[int(token-1)];
            if (!row.value.value("returned").isNull() || !row.value.value("unwound").isNull()) {unavailable();return;}
            row.value[unwound ? "unwound" : "returned"]=owner.clock();
        } QT_CATCH (...) {unavailable();}
    }
};
} // namespace overte::e2e
#endif
