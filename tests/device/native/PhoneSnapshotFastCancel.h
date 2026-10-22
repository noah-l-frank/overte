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
            QQuickItem* root,QQuickWindow* window,const std::shared_ptr<SnapshotUi>& ui,const Read& read,const Click& click) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
                || !valid(run) || !valid(job) || !QStringList{"start","observe","retire"}.contains(operation)
                || (operation!="start" && !input.isEmpty())) { return {}; }
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
                const auto original=current();
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
        const auto native=original.value("native").toMap();const auto review=original.value("review").toMap().value("review").toMap();
        if (review.isEmpty() || review.value("capturing").toBool() || review.value("processing").toBool()
                || !review.value("exportTicket").toString().isEmpty() || review.value("exportBusy").toBool()
                || !review.value("uploadPath").toString().isEmpty() || !native.value("captures").toList().isEmpty()
                || !native.value("uploads").toStringList().isEmpty()) { return false; }
        QMap<QString,QString> latest;
        for (const auto& value:events(original)) { const auto row=value.toMap();latest[row.value("id").toString()]=row.value("kind").toString(); }
        for (const auto& phase:latest) { if (phase=="pending" || phase=="processing") { return false; } }
        return true;
    }
    QVariantMap current() {
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
                || !review.value("present").toBool() || began>captured || captured-began>=1500) { return {}; }
        return {{"capturedEpochMs",captured},{"native",native},{"review",review}};
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
        const auto actual=current();
        return {{"snapshotFastCancelVersion",1},{"instance",_instance},{"job",_job},{"runId",_run},{"phase",_phase},{"error",_error},
            {"startedEpochMs",_started},{"completedEpochMs",_finished},{"observedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"timerActive",_timer.isActive()},{"retired",_retired},{"request",_request},{"captureCommand",_input.toVariantMap()},
            {"captureInput",_captureInput},{"cancelCommand",_cancelCommand.toVariantMap()},{"cancelInput",_cancelInput},
            {"before",_before},{"pending",_pending},{"cancelled",_cancelled},{"retirement",_retirement},{"current",actual}};
    }
    QString _instance,_job,_run,_phase,_error,_request,_scriptInstance;int _scriptBefore{0},_captureBefore{0};
    QPointer<QQuickItem> _root;QPointer<QQuickWindow> _window;std::shared_ptr<SnapshotUi> _ui;Read _read;Click _click;
    QTimer _timer;QElapsedTimer _clock;bool _retired{false};qint64 _started{0},_finished{0};
    QJsonObject _input,_cancelCommand;QVariantMap _captureInput,_cancelInput,_before,_pending,_cancelled,_retirement;
};
} // namespace overte::e2e
#endif
