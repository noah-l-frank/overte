// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <QMutex>
#include <QMutexLocker>
#include <QMap>
#include <memory>
#include <exception>

namespace overte::e2e {
// The actual queued Qt functor owns Token. Neither the ledger nor a read does.
class IOSSnapshotFileWorkObservation {
public:
    struct Token { QString id; };
    using Responsibility=std::shared_ptr<Token>;
    static IOSSnapshotFileWorkObservation& instance() {static auto* value=new IOSSnapshotFileWorkObservation;return *value;}
    Responsibility queued(const QVariantMap& query) {
        QMutexLocker guard(&_mutex);
        if (!_complete || _jobs.size()>=1024) {_complete=false;return {};}
        auto token=std::make_shared<Token>();token->id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        Job job;job.query=query;job.actual=token;job.queued=stamp();_jobs.insert(token->id,job);return token;
    }
    void entered(const Responsibility& token) {
        if (!token) {return;}QMutexLocker guard(&_mutex);auto& job=_jobs[token->id];
        if (job.entered || job.finished) {_complete=false;return;}job.entered=stamp();
    }
    void publication(const Responsibility& token,bool actual) {
        if (!token) {return;}QMutexLocker guard(&_mutex);auto& job=_jobs[token->id];
        if (!job.entered || job.publication.isValid() || job.finished) {_complete=false;return;}
        job.publication=actual;job.published=stamp();
    }
    void finished(const Responsibility& token,bool returned) {
        if (!token) {return;}QMutexLocker guard(&_mutex);auto& job=_jobs[token->id];
        if (!job.entered || job.finished) {_complete=false;return;}
        if (returned) {job.returned=stamp();}job.finished=stamp();
    }
    class Body {
    public:
        explicit Body(const Responsibility& actual):_actual(actual),_exceptions(std::uncaught_exceptions()) {
            instance().entered(_actual);
        }
        ~Body() {instance().finished(_actual,std::uncaught_exceptions()==_exceptions);}
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:
        Responsibility _actual;int _exceptions;
    };
    bool allReadJobsRetired() {
        QMutexLocker guard(&_mutex);if (!_complete) {return false;}
        for (const auto& job:_jobs) {if (!job.actual.expired() || !job.finished) {return false;}}
        return true;
    }
    QVariantMap read(const QString& request,const QString& run) {
        const auto app=QCoreApplication::instance();
        if (!app || QThread::currentThread()!=app->thread() || _sequence>=1000000000
                || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        const auto before=clock();QVariantList jobs;bool complete;
        {
            QMutexLocker guard(&_mutex);
            for (auto it=_jobs.begin();it!=_jobs.end();++it) {
                auto& job=it.value();const bool alive=!job.actual.expired();
                if (!alive && !job.expired) {job.expired=stamp();if (!job.finished) {_complete=false;}}
                // Native file queries own a controlled 16-hex run prefix. The
                // full candidate/run binding remains the outer owner's duty.
                if (!job.query.value("prefix").toString().startsWith("parity-"+run.left(16)+"-")) {continue;}
                jobs.push_back(QVariantMap{{"id",it.key()},{"query",job.query},{"queuedEpochMs",job.queued},
                    {"enteredEpochMs",optional(job.entered)},{"returnedEpochMs",optional(job.returned)},
                    {"finallyEpochMs",optional(job.finished)},{"expiredEpochMs",optional(job.expired)},
                    {"publication",job.publication.isValid() ? job.publication : QVariant()},
                    {"publishedEpochMs",optional(job.published)},{"alive",alive}});
            }
            complete=_complete;
        }
        QVariantMap source{{"complete",complete},{"jobs",jobs}};
        if (QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>1572864) {
            QMutexLocker guard(&_mutex);_complete=false;return {};
        }
        const auto after=clock();
        const auto epochBefore=before.value("epochMs").toLongLong(),epochAfter=after.value("epochMs").toLongLong();
        const auto monoBefore=before.value("monotonicMs").toLongLong(),monoAfter=after.value("monotonicMs").toLongLong();
        if (epochBefore<_readEpoch || monoBefore<_readMono || epochAfter<epochBefore || monoAfter<monoBefore
                || (_readEpoch && qAbs(epochBefore-_readEpoch-monoBefore+_readMono)>250)
                || qAbs(epochAfter-epochBefore-monoAfter+monoBefore)>250) {
            QMutexLocker guard(&_mutex);_complete=false;source["complete"]=false;
        }
        _readEpoch=epochAfter;_readMono=monoAfter;
        return {{"iosSnapshotFileWorkVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-main-snapshot-file-work"},{"clockBefore",before},{"clockAfter",after},{"source",source}};
    }
private:
    struct Job {
        QVariantMap query;std::weak_ptr<Token> actual;QVariant publication;
        qint64 queued{0},entered{0},returned{0},finished{0},expired{0},published{0};
    };
    IOSSnapshotFileWorkObservation() {_timer.start();}
    static QVariant optional(qint64 actual) {return actual ? QVariant(actual) : QVariant();}
    qint64 stamp() {
        const auto actual=QDateTime::currentMSecsSinceEpoch();if (actual<=0 || actual<_epoch) {_complete=false;}_epoch=actual;return actual;
    }
    QVariantMap clock() const {return {{"epochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",_timer.elapsed()}};}
    QMutex _mutex;QMap<QString,Job> _jobs;bool _complete{true};qint64 _epoch{0};quint64 _sequence{0};QElapsedTimer _timer;
    qint64 _readEpoch{0},_readMono{0};
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
}
#endif
