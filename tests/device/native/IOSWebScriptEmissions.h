// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QMetaType>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QUrl>
#include <QVariant>
#include <atomic>
#include <exception>
#include <memory>

namespace overte::e2e::web_script_emissions {
inline std::atomic<bool>& failure() {static std::atomic<bool> actual{false};return actual;}
inline void invalid() noexcept {failure().store(true);}
inline bool enabled() noexcept {
    try {if(!QCoreApplication::instance()){return false;}const auto args=QCoreApplication::arguments();
        const auto a=args.indexOf("--testScript"),b=args.indexOf("--testResultsLocation");
        return a>=0 && a+1<args.size() && !args[a+1].isEmpty() && b>=0 && b+1<args.size() && !args[b+1].isEmpty();
    }catch(...){invalid();return false;}
}
inline QString nonce(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
// Strictly closed parity reply traffic only. Never retain arbitrary API text,
// login/protocol payloads, duplicate JSON members or escaped secret substrings.
// Member order/JSON whitespace may differ from the ordinary Script's encoder.
inline bool echo(const QVariant& message) {
    const auto json=QJsonValue::fromVariant(message);QJsonObject object;
    if(json.isString()){
        const auto raw=json.toString();if(raw.toUtf8().size()>4096){return false;}
        const auto trimmed=raw.trimmed();if(!trimmed.startsWith('{') || !trimmed.endsWith('}')){return false;}
        const auto parts=trimmed.mid(1,trimmed.size()-2).split(',');if(parts.size()!=4){return false;}
        const QRegularExpression member("\\A[ \\t\\r\\n]*\"(contract|action|surface|sequence)\"[ \\t\\r\\n]*:[ \\t\\r\\n]*(\"(?:overte-web-parity-v1|echo|tablet|world)\"|[1-9][0-9]{0,6})[ \\t\\r\\n]*\\z");
        QSet<QString> seen;
        for(const auto& part:parts){const auto match=member.match(part);if(!match.hasMatch() || seen.contains(match.captured(1))){return false;}
            const auto key=match.captured(1),value=match.captured(2);seen.insert(key);
            if(key=="sequence"){if(value.startsWith('"') || value.toLongLong()>1000000){return false;}object.insert(key,QJsonValue(static_cast<double>(value.toLongLong())));}
            else {if(!value.startsWith('"')){return false;}object.insert(key,value.mid(1,value.size()-2));}
        }
    }else if(json.isObject()){object=json.toObject();}else{return false;}
    const auto keys=object.keys();const auto sequence=object.value("sequence");const auto number=sequence.toDouble(-1);
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"contract","action","sequence","surface"}
        && object.value("contract")==QJsonValue("overte-web-parity-v1") && object.value("action")==QJsonValue("echo")
        && (object.value("surface")==QJsonValue("tablet") || object.value("surface")==QJsonValue("world"))
        && sequence.isDouble() && number>=1 && number<=1000000 && number==static_cast<quint64>(number);
}
struct Object {QString id;QPointer<QObject> value;QVariantMap born,expired;};
struct Call {QString id,object,surface,target;QVariant message,caller;QVariantMap entered,returned,finished;quint64 sequence{0};};
using CallPointer=std::shared_ptr<Call>;
struct Queue {QString id,route;CallPointer call;QVariantMap created,entered,returned,finished,expired;std::weak_ptr<void> capture;quint64 sequence{0};};
struct Capture {CallPointer call;std::shared_ptr<Queue> row;std::shared_ptr<void> life;};
struct Sink {QString id,kind;CallPointer call;QVariantMap identity,entered,returned,finished;QVariant message;quint64 sequence{0};};
struct State {QMutex mutex;const QString instance{nonce()};QElapsedTimer timer;qint64 epoch{0},mono{0};
    quint64 sequence{0},callSequence{0},queueSequence{0},sinkSequence{0};bool complete{true};
    QList<std::shared_ptr<Object>> objects;QList<CallPointer> calls;QList<std::shared_ptr<Queue>> queues;QList<std::shared_ptr<Sink>> sinks;
    State(){timer.start();}};
inline State& state(){static State actual;return actual;}
inline QVariantMap clock(State& actual){const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if(epoch<=0 || mono<0 || epoch<actual.epoch || mono<actual.mono || (actual.epoch && qAbs(epoch-actual.epoch-mono+actual.mono)>250)){actual.complete=false;}
    actual.epoch=epoch;actual.mono=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};}
inline CallPointer& currentReference(){static thread_local CallPointer actual;return actual;}
inline bool& continuation(){static thread_local bool actual{false};return actual;}
inline CallPointer current() noexcept {return currentReference();}
class Scope final {
public:
    explicit Scope(CallPointer call,bool continued=false) noexcept:_previous(currentReference()),_continued(continuation()){
        currentReference()=std::move(call);continuation()=continued;
    }
    ~Scope(){currentReference()=std::move(_previous);continuation()=_continued;}
    Scope(const Scope&)=delete;Scope& operator=(const Scope&)=delete;
private:CallPointer _previous;bool _continued;
};
inline std::shared_ptr<Object> object(State& actual,QObject* target){
    for(const auto& row:actual.objects){if(row->value==target){return row;}}
    if(!target || actual.objects.size()>=1024){actual.complete=false;return {};}
    auto row=std::make_shared<Object>();row->id=nonce();row->value=target;row->born=clock(actual);actual.objects.push_back(row);return row;
}
// One actual native API call, with its original Script VM provenance if present.
// Explicit queued recursion continues the same original call exactly once.
class Api final {
public:
    Api(const QString& surface,QObject* target,const QString& name,const QVariant& message,const QVariantMap& caller) noexcept:_exceptions(std::uncaught_exceptions()){
        try{if(!enabled()){return;}
            const auto original=current();bool continued=false;
            if(continuation() && original){auto& actual=state();QMutexLocker guard(&actual.mutex);
                for(const auto& obj:actual.objects){if(obj->id==original->object && obj->value==target && original->surface==surface
                        && original->target==name && original->message==message){_call=original;continued=true;break;}}}
            continuation()=false;
            if(!continued && echo(message)){
                auto& actual=state();QMutexLocker guard(&actual.mutex);
                if((surface!="tablet" && surface!="world") || name.isEmpty() || name.toUtf8().size()>512 || actual.calls.size()>=512){actual.complete=false;}
                else if(const auto obj=object(actual,target)){
                    _call=std::make_shared<Call>();_call->id=nonce();_call->sequence=++actual.callSequence;
                    _call->object=obj->id;_call->surface=surface;_call->target=name;_call->message=message;
                    if(caller.value("method")==QVariant("emitScriptEvent")){_call->caller=caller;}
                    _call->entered=clock(actual);actual.calls.push_back(_call);_own=true;
                }
            }
            _scope=std::make_unique<Scope>(_call);
        }catch(...){invalid();}
    }
    ~Api() noexcept{try{if(_own && _call){auto& actual=state();QMutexLocker guard(&actual.mutex);
            if(std::uncaught_exceptions()==_exceptions){_call->returned=clock(actual);}_call->finished=clock(actual);}}
        catch(...){invalid();}}
    CallPointer call() const noexcept{return _call;}
    Api(const Api&)=delete;Api& operator=(const Api&)=delete;
private:CallPointer _call;std::unique_ptr<Scope> _scope;bool _own{false};int _exceptions;
};
inline Capture queued(CallPointer call,const QString& route,const QVariant& message={}) noexcept{
    Capture value;value.call=std::move(call);
    try{if(!enabled() || (!value.call && !echo(message))){return value;}auto& actual=state();QMutexLocker guard(&actual.mutex);
        if(actual.queues.size()>=2048 || (route!="tablet-proxy" && route!="tablet-surface" && route!="tablet-window" && route!="world-surface")){actual.complete=false;return value;}
        value.life=std::make_shared<int>(0);value.row=std::make_shared<Queue>();value.row->id=nonce();value.row->call=value.call;
        value.row->sequence=++actual.queueSequence;value.row->route=route;value.row->created=clock(actual);value.row->capture=value.life;
        actual.queues.push_back(value.row);
    }catch(...){invalid();}return value;
}
class Dispatch final {
public:
    explicit Dispatch(const Capture& capture,bool continued=false) noexcept:_capture(capture),_scope(capture.call,continued),_exceptions(std::uncaught_exceptions()){
        try{if(_capture.row){auto& actual=state();QMutexLocker guard(&actual.mutex);if(!_capture.row->entered.isEmpty()){actual.complete=false;return;}
            _capture.row->entered=clock(actual);_entered=true;}}catch(...){invalid();}}
    ~Dispatch() noexcept{try{if(_entered){auto& actual=state();QMutexLocker guard(&actual.mutex);
            if(std::uncaught_exceptions()==_exceptions){_capture.row->returned=clock(actual);}_capture.row->finished=clock(actual);}}
        catch(...){invalid();}}
    Dispatch(const Dispatch&)=delete;Dispatch& operator=(const Dispatch&)=delete;
private:Capture _capture;Scope _scope;int _exceptions;bool _entered{false};
};
inline QString fixture(const QVariantMap& identity){
    if(identity.value("surface")==QVariant("tablet")){return identity.value("source").toMap().value("fixtureUrl").toString();}
    if(identity.value("surface")!=QVariant("world-entity")){return {};}
    const QUrl url(identity.value("sourceUrl").toString(),QUrl::StrictMode);
    const auto match=QRegularExpression("\\A(/feature-fixture/v1/runs/[0-9a-f]{32}/)tickets/[0-9a-f]{32}/(?:index|reference)\\.html\\z").match(url.path());
    if(!match.hasMatch()){return {};}auto root=url;root.setPath(match.captured(1));return root.toString(QUrl::FullyEncoded);
}
class SinkScope final {
public:
    SinkScope(const QString& kind,const QVariantMap& identity,const QVariant& message) noexcept:_exceptions(std::uncaught_exceptions()){
        try{if(!enabled() || !echo(message) || fixture(identity).isEmpty()){return;}auto& actual=state();QMutexLocker guard(&actual.mutex);
            if((kind!="script-event-slot" && kind!="page-reply") || actual.sinks.size()>=2048){actual.complete=false;return;}
            _row=std::make_shared<Sink>();_row->id=nonce();_row->sequence=++actual.sinkSequence;_row->kind=kind;_row->identity=identity;
            _row->call=current();_row->message=message;_row->entered=clock(actual);actual.sinks.push_back(_row);
        }catch(...){invalid();}}
    ~SinkScope() noexcept{try{if(_row){auto& actual=state();QMutexLocker guard(&actual.mutex);
            if(std::uncaught_exceptions()==_exceptions){_row->returned=clock(actual);}_row->finished=clock(actual);}}
        catch(...){invalid();}}
    SinkScope(const SinkScope&)=delete;SinkScope& operator=(const SinkScope&)=delete;
private:std::shared_ptr<Sink> _row;int _exceptions;
};
inline QVariant nullable(const QVariantMap& value){return value.isEmpty()?QVariant():QVariant(value);}
inline QVariantMap observe(const QVariantMap& query){
    if(!enabled() || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()){return {};}
    const auto json=QJsonObject::fromVariantMap(query);const auto keys=json.keys();const auto root=json.value("fixtureUrl").toString(),run=json.value("runId").toString();
    const QUrl url(root,QUrl::StrictMode);
    if(QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","action","commandId","runId","fixtureUrl"}
            || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("feature-ios-web-script-emissions")
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(json.value("commandId").toString()).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() || root.size()>512
            || root.contains(QRegularExpression("[\\x00-\\x20\\x7f]")) || !url.isValid() || (url.scheme()!="http" && url.scheme()!="https")
            || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment()
            || url.path()!="/feature-fixture/v1/runs/"+run+"/" || url.toString(QUrl::FullyEncoded)!=root){return {};}
    auto& actual=state();QMutexLocker guard(&actual.mutex);const auto before=clock(actual);QVariantList objects,calls,queues,sinks;
    for(const auto& row:actual.objects){if(row->value.isNull() && row->expired.isEmpty()){row->expired=clock(actual);}
        objects.push_back(QVariantMap{{"id",row->id},{"born",row->born},{"expired",nullable(row->expired)},{"alive",!row->value.isNull()}});}
    for(const auto& row:actual.calls){calls.push_back(QVariantMap{{"id",row->id},{"sequence",static_cast<qulonglong>(row->sequence)},
        {"object",row->object},{"surface",row->surface},{"target",row->target},{"message",row->message},{"caller",row->caller},
        {"entered",row->entered},{"returned",nullable(row->returned)},{"finally",nullable(row->finished)}});}
    for(const auto& row:actual.queues){if(row->capture.expired() && row->expired.isEmpty()){row->expired=clock(actual);}
        queues.push_back(QVariantMap{{"id",row->id},{"sequence",static_cast<qulonglong>(row->sequence)},{"call",row->call?QVariant(row->call->id):QVariant()},{"route",row->route},
            {"created",row->created},{"entered",nullable(row->entered)},{"returned",nullable(row->returned)},{"finally",nullable(row->finished)},
            {"captureAlive",!row->capture.expired()},{"expired",nullable(row->expired)}});}
    for(const auto& row:actual.sinks){if(fixture(row->identity)!=root){continue;}
        sinks.push_back(QVariantMap{{"id",row->id},{"sequence",static_cast<qulonglong>(row->sequence)},{"kind",row->kind},
            {"call",row->call?QVariant(row->call->id):QVariant()},{"identity",row->identity},{"message",row->message},
            {"entered",row->entered},{"returned",nullable(row->returned)},{"finally",nullable(row->finished)}});}
    if(actual.sequence>=9007199254740991ULL){actual.complete=false;return {};}
    const auto after=clock(actual);QVariantMap result{{"iosWebScriptEmissionsVersion",1},{"commandId",query.value("commandId")},{"runId",run},{"fixtureUrl",root},
        {"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},{"processId",QCoreApplication::applicationPid()},
        {"clockDomain","native-process-ios-web-script-emissions"},{"clockBefore",before},{"clockAfter",after},{"complete",actual.complete && !failure().load()},
        {"callSequence",static_cast<qulonglong>(actual.callSequence)},{"queueSequence",static_cast<qulonglong>(actual.queueSequence)},
        {"sinkSequence",static_cast<qulonglong>(actual.sinkSequence)},{"objects",objects},{"calls",calls},{"queues",queues},{"sinks",sinks}};
    if(QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>2097152){actual.complete=false;return {};}
    return result;
}
} // namespace overte::e2e::web_script_emissions
Q_DECLARE_METATYPE(overte::e2e::web_script_emissions::Capture)
#endif
