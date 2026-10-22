// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "NormalControlUi.h"
#include "PhoneSnapshotReviewObservation.h"
#include <QTimer>
#include <QMap>
#include <memory>

namespace overte::e2e {
// Bounded local target automation. It never pauses the event loop, changes a
// capture delay, calls a script handler or invokes Snapshot.cancelCapture.
// Input receipts, original pending/cancel observations and actual timer state
// remain separate. Even complete here is not a file/quiet/feature verdict.
class PhoneSnapshotFastCancel : public QObject {
public:
    using Read=std::function<QVariantMap()>;
    using Click=std::function<bool(QQuickItem*)>;
    PhoneSnapshotFastCancel() : _instance(nonce()) {
        _timer.setTimerType(Qt::PreciseTimer);_timer.setInterval(2);
        connect(&_timer,&QTimer::timeout,this,[this] { advance(); });
    }
    QVariantMap request(const QString& run,const QString& job,const QString& operation,const QJsonObject& input,
            QQuickItem* root,QQuickWindow* window,const std::shared_ptr<SnapshotUi>& ui,const Read& read,const Click& click,
            const QVariantMap& closedWork=QVariantMap{}) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
                || !valid(run) || !valid(job) || !QStringList{"start","observe","retire"}.contains(operation)
                || (operation!="start" && !input.isEmpty())) { return {}; }
        _closedWork=closedWork;
        if (_job.isEmpty()) {
            if (operation!="start" || !root || !window || !ui || !read || !click
                    || input.value("action")!="activate" || input.value("controlId")!="snapshot.capture"
                    || input.value("commandId")!=job) { return {}; }
            const auto keys=input.keys();
            if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","controlId",
                    "controlToken","instance","generation","sequence","observedElapsedMs"}) { return {}; }
            _job=job;_run=run;_root=root;_window=window;_ui=ui;_read=read;_click=click;_input=input;
            _phase="preparing";_started=QDateTime::currentMSecsSinceEpoch();_clock.start();
            const auto original=current();
            if (original.isEmpty() || !idle(original)) { fail("original-capture-state-unavailable");return observation(); }
            _before=original;
            const auto native=original.value("native").toMap();
            _scriptInstance=native.value("scriptHistory").toMap().value("instance").toString();
            _scriptBefore=native.value("scriptHistory").toMap().value("sequence").toInt();
            _captureBefore=native.value("history").toMap().value("sequence").toInt();
            _captureInput=_ui->apply(_root,_window,_input,_click).toVariantMap();
            if (!_captureInput.value("performed").toBool()) { fail("capture-input-not-delivered");return observation(); }
            _phase="capturing";_timer.start();
        } else {
            if (_run!=run || _job!=job || (operation=="start" && input!=_input)) { return {}; }
            if (operation=="retire") {
                // Preserve the failed/complete original. Never cancel product
                // work or remove files to manufacture an empty observation.
                const auto original=current(true);
                if (_timer.isActive() || (_phase!="complete" && _phase!="failed") || original.isEmpty() || !idle(original)) { return {}; }
                if (!_retired) { _retirement=original; }_retired=true;
            }
        }
        return observation();
    }
    QVariantMap summary() const {
        return {{"job",_job},{"runId",_run},{"instance",_instance},{"phase",_phase},{"timerActive",_timer.isActive()},{"retired",_retired}};
    }
private:
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool valid(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QVariantList events(const QVariantMap& original) {
        return original.value("native").toMap().value("scriptHistory").toMap().value("events").toList();
    }
    static bool idle(const QVariantMap& original) {
        const auto native=original.value("native").toMap();const auto view=original.value("review").toMap();const auto review=view.value("review").toMap();
        if ((review.isEmpty() && (view.value("present")!=false || !original.contains("scriptWork")))
                || review.value("capturing").toBool() || review.value("processing").toBool()
                || !review.value("exportTicket").toString().isEmpty() || review.value("exportBusy").toBool()
                || !review.value("uploadPath").toString().isEmpty() || !native.value("captures").toList().isEmpty()
                || !native.value("uploads").toStringList().isEmpty()) { return false; }
        QMap<QString,QString> latest;
        for (const auto& value:events(original)) { const auto row=value.toMap();latest[row.value("id").toString()]=row.value("kind").toString(); }
        for (const auto& phase:latest) { if (phase=="pending" || phase=="processing") { return false; } }
        return true;
    }
    bool closedIdle(qint64 captured) const {
        const auto selected=_cancelled.isEmpty() ? _pending : _cancelled;
        const auto caller=events(selected).isEmpty() ? QVariantMap{} : events(selected).last().toMap().value("caller").toMap();
        const auto source=_closedWork.value("source").toMap(),work=source.value("work").toMap();
        const auto compilation=caller.value("compilation").toMap();const int id=compilation.value("scriptId").toInt();
        const auto originalWork=caller.value("snapshotWork").toMap();
        const auto requested=_closedWork.value("requestedEpochMs").toLongLong(),completed=_closedWork.value("capturedEpochMs").toLongLong();
        if (caller.isEmpty() || _closedWork.value("processId").toLongLong()!=QCoreApplication::applicationPid()
                || !valid(_closedWork.value("requestId").toString()) || source.value("complete")!=true
                || source.value("manager")!=caller.value("manager") || source.value("code")!=caller.value("code")
                || source.value("compiled").toMap().value("complete")!=true || work.value("scriptWorkVersion")!=2
                || work.value("requestId")!=_closedWork.value("requestId") || requested<=0 || completed<requested
                || completed>captured || captured-requested>=1500 || work.value("requestedEpochMs").toLongLong()!=requested
                || work.value("capturedEpochMs").toLongLong()<requested || work.value("capturedEpochMs").toLongLong()>completed
                || work.value("evaluating")!=false || id<=0) { return false; }
        QSet<int> known;bool original=false;
        for (const auto& item:source.value("compiled").toMap().value("compilations").toList()) {
            const auto row=item.toMap();const auto script=row.value("scriptId").toInt();
            if (script<=0 || known.contains(script)) { return false; }known.insert(script);
            if (row==compilation) { original=true; }
        }
        if (!original) { return false; }
        for (const auto& item:work.value("timers").toList()) {
            const auto script=item.toMap().value("functionScriptId").toInt();
            if (script==id || !known.contains(script)) { return false; }
        }
        bool own=false;quint64 signalCount=0,timerCount=0;
        const auto activity=work.value("activity").toList();
        if (work.value("timerEntries").toInt()!=work.value("timers").toList().size()
                || work.value("activityEntries").toInt()!=activity.size()) { return false; }
        for (const auto& item:activity) {
            const auto row=item.toMap();const auto script=row.value("scriptId").toInt();
            signalCount+=row.value("signalCallbacks").toULongLong();timerCount+=row.value("timerCallbacks").toULongLong();
            if ((script==id || !known.contains(script)) && (row.value("signalCallbacks").toULongLong()!=0 || row.value("timerCallbacks").toULongLong()!=0)) { return false; }
            if (script==id) {
                if (own) { return false; }own=true;
                for (const auto& key:QStringList{"signalInvocations","timerInvocations","timerRegistrations"}) {
                    if (row.value(key).toULongLong()<originalWork.value(key).toULongLong()) { return false; }
                }
            }
        }
        return own && signalCount==work.value("signalCallbacks").toULongLong() && timerCount==work.value("timerCallbacks").toULongLong();
    }
    QVariantMap current(bool allowClosed=false) {
        if (!_root || !_window || !_ui || !_read || !_click || _root->window()!=_window
                || QThread::currentThread()!=thread() || QGuiApplication::applicationState()!=Qt::ApplicationActive) { return {}; }
        const auto began=QDateTime::currentMSecsSinceEpoch();const auto native=_read();
        const auto review=phoneSnapshotReviewObservation(_root);
        const auto captured=QDateTime::currentMSecsSinceEpoch();
        const auto history=native.value("history").toMap(),script=native.value("scriptHistory").toMap();
        if (native.value("phoneSnapshotObservationVersion")!=1 || !native.value("nativeReview").toBool()
                || history.value("complete")!=true || script.value("complete")!=true || !valid(script.value("instance").toString())
                || history.value("sequence").toInt()!=history.value("events").toList().size()
                || script.value("sequence").toInt()!=script.value("events").toList().size()
                || began>captured || captured-began>=1500) { return {}; }
        QVariantMap result{{"capturedEpochMs",captured},{"native",native},{"review",review}};
        if (!review.value("present").toBool() || !review.value("review").toMap().value("visible").toBool()) {
            if (!allowClosed || (review.value("present")!=true && (review.value("present")!=false || !review.value("review").isNull()))
                    || !closedIdle(captured)) { return {}; }
            result.insert("scriptWork",_closedWork);
            if (!idle(result)) { return {}; }
        }
        if (!_lastCurrent.isEmpty() && !historyPrefix(_lastCurrent,result)) { return {}; }
        _lastCurrent=result;return result;
    }
    static bool historyPrefix(const QVariantMap& before,const QVariantMap& after) {
        const auto a=before.value("native").toMap(),b=after.value("native").toMap();
        if (after.value("capturedEpochMs").toLongLong()<before.value("capturedEpochMs").toLongLong()
                || a.value("storageRoot")!=b.value("storageRoot")) { return false; }
        for (const auto& key:QStringList{"history","scriptHistory"}) {
            const auto first=a.value(key).toMap(),last=b.value(key).toMap();const auto old=first.value("events").toList(),now=last.value("events").toList();
            if (first.value("instance")!=last.value("instance") || now.size()<old.size() || now.mid(0,old.size())!=old) { return false; }
        }
        return true;
    }
    void fail(const QString& error) { _timer.stop();_phase="failed";_error=error;_finished=QDateTime::currentMSecsSinceEpoch(); }
    bool prefix(const QVariantMap& original) const {
        const auto native=original.value("native").toMap();const auto script=native.value("scriptHistory").toMap();
        if (script.value("instance")!=_scriptInstance || native.value("history").toMap().value("sequence").toInt()!=_captureBefore
                || native.value("history")!=_before.value("native").toMap().value("history")
                || !native.value("captures").toList().isEmpty() || !native.value("uploads").toStringList().isEmpty()) { return false; }
        const auto before=events(_before),after=events(original);
        return after.size()>=before.size() && after.mid(0,before.size())==before;
    }
    void advance() {
        if (_phase!="capturing" && _phase!="cancelling") { _timer.stop();return; }
        if (!_clock.isValid() || _clock.elapsed()>=(_phase=="capturing" ? 300 : 5000)) { fail("original-capture-window-expired");return; }
        const auto original=current();
        if (original.isEmpty() || !prefix(original)) { fail("original-capture-source-changed");return; }
        const auto rows=events(original);const auto review=original.value("review").toMap().value("review").toMap();
        if (_phase=="capturing") {
            if (rows.size()==_scriptBefore) { return; }
            if (rows.size()!=_scriptBefore+1) { fail("capture-left-pre-render-window");return; }
            const auto pending=rows.last().toMap(),caller=pending.value("caller").toMap();
            const auto work=caller.value("snapshotWork").toMap();auto timers=work.value("timers").toList();QList<int> intervals;
            bool active=true;
            for (const auto& value:timers) { const auto timer=value.toMap();intervals.append(timer.value("intervalMs").toInt());
                active=active && timer.value("active").toBool() && timer.value("singleShot").toBool() && timer.value("remainingMs",QVariant(-1)).toInt()>=0; }
            std::sort(intervals.begin(),intervals.end());
            if (pending.value("kind")!="pending" || pending.value("mode")!="animated" || !review.value("capturing").toBool()
                    || review.value("processing").toBool() || pending.value("capturedEpochMs").toLongLong()<_started
                    || caller.value("method")!="featureCaptureEvent" || work.value("scriptId")!=caller.value("compilation").toMap().value("scriptId")
                    || !active || intervals!=QList<int>{350,60000}) { fail("original-pending-capture-unqualified");return; }
            const auto controls=_ui->observe(_root,_window);
            if (controls.value("instance")!=_input.value("instance") || controls.value("generation")!=_input.value("generation")
                    || controls.value("lastCommandSequence")!=_input.value("sequence")) { fail("capture-input-context-changed");return; }
            QJsonObject cancel;
            for (const auto& value:controls.value("controls").toArray()) { const auto row=value.toObject();if (row.value("id")=="snapshot.cancel-capture") { cancel=row; } }
            if (cancel.isEmpty() || !cancel.value("enabled").toBool() || !cancel.value("inputReady").toBool()) { return; }
            _pending=original;_request=pending.value("id").toString();
            _cancelCommand={{"schemaVersion",1},{"commandId",nonce()},{"action","activate"},{"controlId","snapshot.cancel-capture"},
                {"controlToken",cancel.value("token")},{"instance",controls.value("instance")},{"generation",controls.value("generation")},
                {"sequence",controls.value("lastCommandSequence").toDouble()+1},{"observedElapsedMs",controls.value("elapsedMs")}};
            if (_clock.elapsed()>=300) { fail("original-capture-window-expired");return; }
            _cancelInput=_ui->apply(_root,_window,_cancelCommand,_click).toVariantMap();
            if (!_cancelInput.value("performed").toBool()) { fail("cancel-input-not-delivered");return; }
            _phase="cancelling";
        } else {
            if (rows.size()==_scriptBefore+1) { return; }
            if (rows.size()!=_scriptBefore+2) { fail("capture-left-pre-render-window");return; }
            const auto cancelled=rows.last().toMap();
            if (cancelled.value("kind")!="cancelled" || cancelled.value("id")!=_request
                    || !cancelled.value("caller").toMap().value("snapshotWork").toMap().value("timers").toList().isEmpty()) {
                fail("original-cancel-context-unqualified");return;
            }
            if (!idle(original)) { return; }
            _cancelled=original;_timer.stop();_phase="complete";_finished=QDateTime::currentMSecsSinceEpoch();
        }
    }
    QVariantMap observation() {
        const auto actual=current(_phase=="complete" || _phase=="failed");
        return {{"snapshotFastCancelVersion",1},{"instance",_instance},{"job",_job},{"runId",_run},{"phase",_phase},{"error",_error},
            {"startedEpochMs",_started},{"completedEpochMs",_finished},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"timerActive",_timer.isActive()},{"retired",_retired},{"request",_request},{"captureCommand",_input.toVariantMap()},
            {"captureInput",_captureInput},{"cancelCommand",_cancelCommand.toVariantMap()},{"cancelInput",_cancelInput},
            {"before",_before},{"pending",_pending},{"cancelled",_cancelled},{"retirement",_retirement},{"current",actual}};
    }
    QString _instance,_job,_run,_phase,_error,_request,_scriptInstance;int _scriptBefore{0},_captureBefore{0};
    QPointer<QQuickItem> _root;QPointer<QQuickWindow> _window;std::shared_ptr<SnapshotUi> _ui;Read _read;Click _click;
    QTimer _timer;QElapsedTimer _clock;bool _retired{false};qint64 _started{0},_finished{0};
    QJsonObject _input,_cancelCommand;QVariantMap _captureInput,_cancelInput,_before,_pending,_cancelled,_retirement,_closedWork,_lastCurrent;
};
} // namespace overte::e2e
#endif
