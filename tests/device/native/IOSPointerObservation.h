// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QInputEvent>
#include <QJsonDocument>
#include <QMap>
#include <QMouseEvent>
#include <QPointer>
#include <QPointingDevice>
#include <QSet>
#include <QThread>
#include <QTouchEvent>
#include <QUuid>
#include <QVariantMap>
#include <atomic>
#include <cmath>

namespace overte::e2e {
// Passive original Qt dispatches. No event filter, synthesis, processEvents,
// requested contact, reset, weak-to-strong promotion or product state mutation.
class IOSPointerObservation {
public:
    static IOSPointerObservation& instance() { static IOSPointerObservation source;return source; }
    static bool enabled() {
        auto app=QCoreApplication::instance();return app && app->arguments().contains("--testScript");
    }
    static void startup() { if (enabled()) { instance().startBeforeFirstWindow(); } }
    void startBeforeFirstWindow() {
        if (!enabled()) { return; }
        if (!mainThread()) { _complete=false;return; }
        if (_started) { _complete=false;return; }
        _started=true;_startEpoch=QDateTime::currentMSecsSinceEpoch();_startMono=_clock.elapsed();
        _initialWindows=QGuiApplication::allWindows().size();_initialButtons=static_cast<int>(QGuiApplication::mouseButtons());
        // The constructor hook precedes the first product window. A late
        // attachment or a preexisting Qt press cannot manufacture empty touch
        // history. The getter never starts this source or clears its poison.
        if (_initialWindows!=0 || _initialButtons!=0) { _complete=false; }
    }
    quint64 enter(QObject* target,QEvent* event) {
        if (!enabled() || !event || !pointerType(event->type())) { return 0; }
        if (!mainThread()) { _complete=false;return 0; }
        if (!_started || !_complete || _dispatches.size()>=1024 || _events.size()>=3072 || !target) { _complete=false;return 0; }
        const auto input=static_cast<QInputEvent*>(event);const auto device=input->device();
        const auto deviceId=weakIdentity(_devices,device,true),targetId=weakIdentity(_targets,target,false);
        if (deviceId.isEmpty() || targetId.isEmpty()) { _complete=false;return 0; }
        const auto id=nonce();QVariantList points;int button=0,buttons=0,mouseSource=0;QVariantList position;
        const auto kind=typeName(event->type());
        if (kind.startsWith("mouse-")) {
            auto mouse=static_cast<QMouseEvent*>(event);button=static_cast<int>(mouse->button());buttons=static_cast<int>(mouse->buttons());mouseSource=static_cast<int>(mouse->source());
            position={mouse->position().x(),mouse->position().y()};
            if (!std::isfinite(mouse->position().x()) || !std::isfinite(mouse->position().y())) { _complete=false;return 0; }
        } else {
            auto touch=static_cast<QTouchEvent*>(event);
            if (touch->points().size()>16) { _complete=false;return 0; }
            for (const auto& point:touch->points()) {
                if (!std::isfinite(point.position().x()) || !std::isfinite(point.position().y())) { _complete=false;return 0; }
                points.append(QVariantMap{{"id",point.id()},{"state",static_cast<int>(point.state())},{"position",QVariantList{point.position().x(),point.position().y()}}});
            }
        }
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=_clock.elapsed();
        const bool nested=_batches.contains(event);QString batch;
        if (nested) { batch=_batches[event].id;_batches[event].depth++; }
        else { batch=nonce();_batches.insert(event,Batch{batch,1}); }
        QVariantMap row{{"id",id},{"batch",batch},{"kind",kind},{"device",deviceId},{"target",targetId},
            {"qtTimestamp",static_cast<double>(input->timestamp())},{"button",button},{"buttons",buttons},{"mouseSource",mouseSource},
            {"position",position},{"points",points},{"enteredSequence",_events.size()+1},{"enteredEpochMs",epoch},{"enteredMonotonicMs",mono},
            {"returnedSequence",0},{"returnedEpochMs",0},{"returnedMonotonicMs",0},{"deliveryResult",QVariant()},
            {"finallySequence",0},{"finallyEpochMs",0},{"finallyMonotonicMs",0}};
        const auto ordinal=static_cast<quint64>(_dispatches.size()+1);_dispatches.append(row);_active.insert(ordinal,event);
        edge(id,"entered",epoch,mono);
        if (!nested) { apply(row); }
        return ordinal;
    }
    void returned(quint64 ordinal,bool result) {
        if (!ordinal) { return; }
        if (!mainThread() || !_active.contains(ordinal)) { _complete=false;return; }
        auto row=_dispatches[ordinal-1].toMap();if (row.value("returnedSequence").toInt()!=0) { _complete=false;return; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=_clock.elapsed();
        row["returnedSequence"]=_events.size()+1;row["returnedEpochMs"]=epoch;row["returnedMonotonicMs"]=mono;row["deliveryResult"]=result;
        _dispatches[ordinal-1]=row;edge(row.value("id").toString(),"returned",epoch,mono);
    }
    void finished(quint64 ordinal) {
        if (!ordinal) { return; }
        if (!mainThread() || !_active.contains(ordinal)) { _complete=false;return; }
        auto row=_dispatches[ordinal-1].toMap();const auto event=_active.take(ordinal);
        if (row.value("returnedSequence").toInt()==0) { _complete=false; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=_clock.elapsed();
        row["finallySequence"]=_events.size()+1;row["finallyEpochMs"]=epoch;row["finallyMonotonicMs"]=mono;_dispatches[ordinal-1]=row;
        edge(row.value("id").toString(),"finally",epoch,mono);
        auto batch=_batches.find(event);
        if (batch==_batches.end() || --batch->depth<0) { _complete=false; }
        else if (batch->depth==0) { _batches.erase(batch); }
    }
    QVariantMap snapshot(bool actualWorldTapActive) {
        if (!enabled() || !mainThread()) { return {}; }
        const auto weak=[](const QList<Weak>& rows) { QVariantList values;
            for (const auto& row:rows) { auto original=row.original;original["alive"]=!row.pointer.isNull();values.append(original); }return values; };
        QVariantList contacts;for (const auto& row:_contacts) { contacts.append(row); }
        return {{"iosPointerSourceVersion",1},{"instance",_instance},{"bornEpochMs",_born},{"complete",_complete && _started},
            {"startup",QVariantMap{{"observed",_started},{"epochMs",_startEpoch},{"monotonicMs",_startMono},
                {"windowCount",_initialWindows},{"mouseButtons",_initialButtons}}},
            {"eventSequence",_events.size()},{"events",_events},{"dispatches",_dispatches},
            {"pendingDispatches",_active.size()},{"contacts",contacts},{"ends",_ends},
            {"devices",weak(_devices)},{"targets",weak(_targets)},
            {"qtMouseButtons",static_cast<int>(QGuiApplication::mouseButtons())},{"worldTapActive",actualWorldTapActive}};
    }
private:
    struct Weak { QPointer<QObject> pointer;QVariantMap original; };
    struct Batch { QString id;int depth; };
    IOSPointerObservation():_born(QDateTime::currentMSecsSinceEpoch()) { _clock.start(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool mainThread() { auto app=QCoreApplication::instance();return app && app->thread()==QThread::currentThread(); }
    static bool pointerType(QEvent::Type type) {
        return type==QEvent::MouseButtonPress || type==QEvent::MouseButtonDblClick || type==QEvent::MouseButtonRelease || type==QEvent::MouseMove
            || type==QEvent::TouchBegin || type==QEvent::TouchUpdate || type==QEvent::TouchEnd || type==QEvent::TouchCancel;
    }
    static QString typeName(QEvent::Type type) {
        switch(type) {
            case QEvent::MouseButtonPress:return "mouse-press";case QEvent::MouseButtonDblClick:return "mouse-double";
            case QEvent::MouseButtonRelease:return "mouse-release";case QEvent::MouseMove:return "mouse-move";
            case QEvent::TouchBegin:return "touch-begin";case QEvent::TouchUpdate:return "touch-update";
            case QEvent::TouchEnd:return "touch-end";case QEvent::TouchCancel:return "touch-cancel";
            default:return {};
        }
    }
    QString weakIdentity(QList<Weak>& rows,const QObject* object,bool device) {
        if (!object) { _complete=false;return {}; }
        for (const auto& row:rows) { if (row.pointer.data()==object) { return row.original.value("id").toString(); } }
        if (rows.size()>=(device ? 16 : 64)) { _complete=false;return {}; }
        QVariantMap original{{"id",nonce()},{"bornEpochMs",QDateTime::currentMSecsSinceEpoch()}};
        if (device) { original["deviceType"]=static_cast<int>(static_cast<const QInputDevice*>(object)->type()); }
        else { original["className"]=QString::fromLatin1(object->metaObject()->className()); }
        // QPointer is weak; this cast permits const QInputDevice identity only.
        rows.append(Weak{const_cast<QObject*>(object),original});return original.value("id").toString();
    }
    void edge(const QString& id,const QString& kind,qint64 epoch,qint64 mono) {
        if (_events.size()>=3072) { _complete=false;return; }
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"dispatch",id},{"kind",kind},{"epochMs",epoch},{"monotonicMs",mono}});
    }
    void end(const QString& key,const QVariantMap& row) {
        if (!_contacts.contains(key)) { _complete=false;return; }
        auto contact=_contacts.take(key);contact["endDispatch"]=row.value("id");_ends.append(contact);
    }
    void apply(const QVariantMap& row) {
        const auto device=row.value("device").toString(),kind=row.value("kind").toString();
        const auto add=[&](const QString& key,const QString& channel,int point) {
            if (_contacts.contains(key) || _contacts.size()>=32) { _complete=false;return; }
            _contacts[key]=QVariantMap{{"kind",channel},{"device",device},{"point",point},{"target",row.value("target")},
                {"startDispatch",row.value("id")},{"bornEpochMs",row.value("enteredEpochMs")}};
        };
        if (kind.startsWith("mouse-")) {
            const int button=row.value("button").toInt(),buttons=row.value("buttons").toInt();
            const auto key=device+":mouse:"+QString::number(button);
            if (kind=="mouse-press" || kind=="mouse-double") { if (button<=0 || !(buttons&button)) { _complete=false; }else { add(key,"mouse",button); } }
            else if (kind=="mouse-release") { if (button<=0 || (buttons&button)) { _complete=false; }else { end(key,row); } }
            int observed=0;for (const auto& contact:_contacts) { if (contact.value("device")==device && contact.value("kind")=="mouse") { observed|=contact.value("point").toInt(); } }
            if (observed!=buttons) { _complete=false; }return;
        }
        if (kind=="touch-cancel") {
            const auto keys=_contacts.keys();for (const auto& key:keys) { const auto c=_contacts[key];if (c.value("device")==device && c.value("kind")=="touch") { end(key,row); } }return;
        }
        QSet<int> seen;
        for (const auto& value:row.value("points").toList()) {
            const auto point=value.toMap();const int id=point.value("id").toInt(),state=point.value("state").toInt();
            if (seen.contains(id)) { _complete=false;continue; }seen.insert(id);const auto key=device+":touch:"+QString::number(id);
            if (state==static_cast<int>(QEventPoint::State::Pressed)) { add(key,"touch",id); }
            else if (state==static_cast<int>(QEventPoint::State::Released)) { end(key,row); }
            else if ((state!=static_cast<int>(QEventPoint::State::Updated) && state!=static_cast<int>(QEventPoint::State::Stationary)) || !_contacts.contains(key)) { _complete=false; }
        }
        if (kind=="touch-begin" && seen.isEmpty()) { _complete=false; }
        if (kind=="touch-end") { for (const auto& c:_contacts) { if (c.value("device")==device && c.value("kind")=="touch") { _complete=false; } } }
    }
    const QString _instance{nonce()};const qint64 _born;QElapsedTimer _clock;
    bool _started{false};std::atomic_bool _complete{true};qint64 _startEpoch{0},_startMono{0};int _initialWindows{-1},_initialButtons{-1};
    QList<Weak> _devices,_targets;QVariantList _events,_dispatches,_ends;QMap<QString,QVariantMap> _contacts;
    QMap<quint64,const QEvent*> _active;QMap<const QEvent*,Batch> _batches;
};

class IOSPointerDispatch {
public:
    IOSPointerDispatch(QObject* object,QEvent* event):_ordinal(IOSPointerObservation::enabled() ? IOSPointerObservation::instance().enter(object,event) : 0) {}
    ~IOSPointerDispatch() { if (_ordinal) { IOSPointerObservation::instance().finished(_ordinal); } }
    void returned(bool result) { if (_ordinal) { IOSPointerObservation::instance().returned(_ordinal,result); } }
private:
    const quint64 _ordinal;
};
} // namespace overte::e2e
#endif
