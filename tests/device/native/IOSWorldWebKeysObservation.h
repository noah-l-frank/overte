// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <QGuiApplication>
#include <QInputMethodEvent>
#include <QKeyEvent>
#include <QPointer>
#include <QMap>
#include <QSet>
#include <cstdlib>
#include <atomic>

namespace overte::e2e {
// Actual QApplication::notify entry/return/finally. This source never releases
// keys, closes an editor, promotes weak ownership, or manufactures empty state.
class IOSWorldWebKeysObservation {
public:
    static IOSWorldWebKeysObservation& instance() { static IOSWorldWebKeysObservation source;return source; }
    static bool enabled() { const auto app=QCoreApplication::instance();return app && app->arguments().contains("--testScript"); }
    static void startup() { if (enabled()) { instance().start(); } }
    quint64 enter(QObject* target,QEvent* event) {
        if (!enabled() || !event || (event->type()!=QEvent::KeyPress && event->type()!=QEvent::KeyRelease && event->type()!=QEvent::InputMethod)) { return 0; }
        if (!mainThread() || !_started || !_complete || !target || _dispatches.size()>=1024 || _events.size()>=3072) { _complete=false;return 0; }
        const auto targetId=identity(_targets,target);if (targetId.isEmpty()) { return 0; }
        QVariantMap detail;QString deviceId;QString kind;
        if (event->type()==QEvent::InputMethod) {
            const auto input=static_cast<QInputMethodEvent*>(event);kind="input-method";
            if (input->commitString().size()>8192 || input->preeditString().size()>8192) { _complete=false;return 0; }
            detail={{"commit",input->commitString()},{"preedit",input->preeditString()},
                {"replacementStart",input->replacementStart()},{"replacementLength",input->replacementLength()}};
        } else {
            const auto input=static_cast<QKeyEvent*>(event);kind=event->type()==QEvent::KeyPress ? "key-press" : "key-release";
            deviceId=identity(_devices,input->device());if (deviceId.isEmpty() || input->text().size()>8192) { _complete=false;return 0; }
            detail={{"key",input->key()},{"text",input->text()},{"modifiers",static_cast<int>(input->modifiers())},
                {"scanCode",static_cast<qulonglong>(input->nativeScanCode())},{"virtualKey",static_cast<qulonglong>(input->nativeVirtualKey())},
                {"autoRepeat",input->isAutoRepeat()},{"count",input->count()},{"qtTimestamp",static_cast<double>(input->timestamp())}};
        }
        const bool nested=_batches.contains(event);QString batch;
        if (nested) { batch=_batches[event].id;++_batches[event].depth; }
        else { batch=nonce();_batches.insert(event,Batch{batch,1}); }
        const auto id=nonce();const auto epoch=QDateTime::currentMSecsSinceEpoch();const auto mono=_clock.elapsed();
        QVariantMap row{{"id",id},{"batch",batch},{"kind",kind},{"target",targetId},{"device",deviceId},{"detail",detail},
            {"enteredSequence",_events.size()+1},{"enteredEpochMs",epoch},{"enteredMonotonicMs",mono},
            {"returnedSequence",0},{"returnedEpochMs",0},{"returnedMonotonicMs",0},{"deliveryResult",QVariant()},
            {"finallySequence",0},{"finallyEpochMs",0},{"finallyMonotonicMs",0}};
        const auto ordinal=static_cast<quint64>(_dispatches.size()+1);_dispatches.append(row);_active.insert(ordinal,event);edge(id,"entered",epoch,mono);
        if (!nested) {
            if (kind=="input-method") {
                _preedit[targetId]=QVariantMap{{"target",targetId},{"text",detail.value("preedit")},{"dispatch",id}};
            } else if (!detail.value("autoRepeat").toBool()) {
                const auto key=deviceId+":"+QString::number(detail.value("scanCode").toULongLong())+":"+QString::number(detail.value("key").toInt());
                if (kind=="key-press") {
                    if (_down.contains(key) || _down.size()>=64) { _complete=false; }
                    else { _down.insert(key,QVariantMap{{"device",deviceId},{"key",detail.value("key")},{"scanCode",detail.value("scanCode")},
                        {"target",targetId},{"pressDispatch",id},{"releaseDispatch",QString()}}); }
                } else {
                    if (!_down.contains(key)) { _complete=false; }
                    else { auto original=_down.take(key);original["releaseDispatch"]=id;_ended.append(original); }
                }
            }
        }
        return ordinal;
    }
    void returned(quint64 ordinal,bool result) {
        if (!ordinal) { return; }
        if (!mainThread() || !_active.contains(ordinal)) { _complete=false;return; }
        auto row=_dispatches[ordinal-1].toMap();if (row.value("returnedSequence").toInt()!=0) { _complete=false;return; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();const auto mono=_clock.elapsed();
        row["returnedSequence"]=_events.size()+1;row["returnedEpochMs"]=epoch;row["returnedMonotonicMs"]=mono;row["deliveryResult"]=result;
        _dispatches[ordinal-1]=row;edge(row.value("id").toString(),"returned",epoch,mono);
    }
    void finished(quint64 ordinal) {
        if (!ordinal) { return; }
        if (!mainThread() || !_active.contains(ordinal)) { _complete=false;return; }
        auto row=_dispatches[ordinal-1].toMap();const auto event=_active.take(ordinal);
        if (row.value("returnedSequence").toInt()==0) { _complete=false; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();const auto mono=_clock.elapsed();
        row["finallySequence"]=_events.size()+1;row["finallyEpochMs"]=epoch;row["finallyMonotonicMs"]=mono;
        _dispatches[ordinal-1]=row;edge(row.value("id").toString(),"finally",epoch,mono);
        auto batch=_batches.find(event);
        if (batch==_batches.end() || --batch->depth<0) { _complete=false; }
        else if (batch->depth==0) { _batches.erase(batch); }
    }
    QVariantMap read(const QString& request,const QString& run) {
        if (!enabled() || !mainThread() || _readSequence>=1000000000) { return {}; }
        const auto before=clock();const auto source=[&]() -> QVariantMap {
            if (!enabled() || !mainThread()) { return {}; }
            const auto weak=[](const QList<Weak>& rows) { QVariantList result;
                for (const auto& row:rows) { auto original=row.original;original["alive"]=!row.pointer.isNull();result.append(original); }return result; };
            QVariantList down,preedit;for (const auto& row:_down) { down.append(row); }for (const auto& row:_preedit) { preedit.append(row); }
            return {{"iosWorldWebKeySourceVersion",1},{"instance",_instance},{"bornEpochMs",_born},{"complete",_complete && _started},
                {"startup",QVariantMap{{"observed",_started},{"epochMs",_startEpoch},{"monotonicMs",_startMono},
                    {"windowCount",_initialWindows},{"modifiers",_initialModifiers}}},
                {"eventSequence",_events.size()},{"events",_events},{"dispatches",_dispatches},{"pendingDispatches",_active.size()},
                {"down",down},{"ended",_ended},{"preedit",preedit},{"devices",weak(_devices)},{"targets",weak(_targets)},
                {"qtModifiers",static_cast<int>(QGuiApplication::keyboardModifiers())}};
        }();const auto after=clock();
        // This source retains real per-character Qt dispatches. Its explicit
        // independent carrier is larger than NativeReadBracket's old default;
        // no other source's bound is changed or bypassed.
        if (source.isEmpty() || QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).size()>1040000) { return {}; }
        return {{"iosWorldWebKeysVersion",1},{"requestId",request},{"runId",run},{"instance",_readInstance},
            {"sequence",static_cast<double>(++_readSequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-main-ios-world-web-keys"},{"clockBefore",before},{"clockAfter",after},{"source",source}};
    }
private:
    struct Weak { QPointer<QObject> pointer;QVariantMap original; };
    struct Batch { QString id;int depth; };
    IOSWorldWebKeysObservation():_born(QDateTime::currentMSecsSinceEpoch()) { _clock.start(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool mainThread() { const auto app=QCoreApplication::instance();return app && app->thread()==QThread::currentThread(); }
    QVariantMap clock() const { return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"monotonicMs",static_cast<double>(_clock.elapsed())}}; }
    void start() {
        if (!mainThread() || _started) { _complete=false;return; }
        _started=true;_startEpoch=QDateTime::currentMSecsSinceEpoch();_startMono=_clock.elapsed();
        _initialWindows=QGuiApplication::allWindows().size();_initialModifiers=static_cast<int>(QGuiApplication::keyboardModifiers());
        if (_initialWindows!=0 || _initialModifiers!=0) { _complete=false; }
    }
    QString identity(QList<Weak>& rows,const QObject* object) {
        if (!object) { _complete=false;return {}; }
        for (const auto& row:rows) { if (row.pointer.data()==object) { return row.original.value("id").toString(); } }
        if (rows.size()>=64) { _complete=false;return {}; }
        QVariantMap original{{"id",nonce()},{"bornEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"className",QString::fromLatin1(object->metaObject()->className())}};
        rows.append(Weak{const_cast<QObject*>(object),original});return original.value("id").toString();
    }
    void edge(const QString& id,const QString& kind,qint64 epoch,qint64 mono) {
        if (_events.size()>=3072 || epoch<_lastEpoch || mono<_lastMono
                || (_lastEpoch && std::llabs(epoch-_lastEpoch-mono+_lastMono)>250)) { _complete=false;return; }
        _lastEpoch=epoch;_lastMono=mono;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"dispatch",id},{"kind",kind},{"epochMs",epoch},{"monotonicMs",mono}});
    }
    QElapsedTimer _clock;const qint64 _born;QString _instance=nonce(),_readInstance=nonce();quint64 _readSequence {0};
    bool _started {false};std::atomic_bool _complete {true};
    qint64 _startEpoch {0},_startMono {0},_lastEpoch {0},_lastMono {0};int _initialWindows {-1},_initialModifiers {-1};
    QList<Weak> _devices,_targets;QVariantList _events,_dispatches,_ended;
    QMap<QString,QVariantMap> _down,_preedit;QMap<quint64,QEvent*> _active;QMap<QEvent*,Batch> _batches;
};
class IOSWorldWebKeyDispatch {
public:
    IOSWorldWebKeyDispatch(QObject* object,QEvent* event):_ordinal(IOSWorldWebKeysObservation::enabled() ? IOSWorldWebKeysObservation::instance().enter(object,event) : 0) {}
    ~IOSWorldWebKeyDispatch() { if (_ordinal) { IOSWorldWebKeysObservation::instance().finished(_ordinal); } }
    void returned(bool result) { if (_ordinal) { IOSWorldWebKeysObservation::instance().returned(_ordinal,result); } }
private: const quint64 _ordinal;
};
} // namespace overte::e2e
#endif
