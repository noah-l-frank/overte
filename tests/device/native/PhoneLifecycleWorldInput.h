// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QJsonObject>
#include <QKeyEvent>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QTimer>
#include <QUuid>
#include <QVariantMap>
#include <QWidget>
#include <memory>

namespace overte::e2e {
// Ordinary hardware ArrowUp through the original rendered QWidget and all its
// unchanged native/Offscreen input filters. Never sets a mapping or drive key.
class PhoneLifecycleWorldInput:public QObject {
public:
    explicit PhoneLifecycleWorldInput(QObject* parent=nullptr):QObject(parent) {
        _clock.start();_timer.setSingleShot(true);_timer.setTimerType(Qt::PreciseTimer);
        connect(&_timer,&QTimer::timeout,this,[this] { release("hold-deadline"); });
        connect(qGuiApp,&QGuiApplication::applicationStateChanged,this,[this](Qt::ApplicationState state) {
            if(state!=Qt::ApplicationActive)release("focus-lost");
        });
        qApp->installEventFilter(this);
    }
    ~PhoneLifecycleWorldInput() override { release("owner-destroyed"); }
    QVariantMap request(const QVariantMap& command,QWidget* actualWidget,const QVariantMap& measured) {
        if(!gui() || _busy || !_valid)return {};
        const auto json=QJsonObject::fromVariantMap(command);
        const auto id=json.value("commandId").toString(),run=json.value("runId").toString();
        const auto operation=json.value("operation").toString(),gesture=json.value("gestureId").toString();
        if(command.keys()!=QStringList{"action","commandId","gestureId","operation","runId","schemaVersion"}
                || json.value("schemaVersion")!=QJsonValue(1) || json.value("action")!=QJsonValue("phone-lifecycle-world-input")
                || !hex(id) || !hex(run) || !json.value("gestureId").isString()
                || !QStringList{"observe","hold","release"}.contains(operation)
                || (operation=="release" ? !hex(gesture) : !gesture.isEmpty()))return {};
        const auto epoch=now();if(!epoch)return {};
        if(_pending && elapsed()>=10000)release("hold-deadline");
        bool performed=false;
        if(operation!="observe") {
            if(_commands.contains(id) || _commands.size()>=256)return {};
            _commands.insert(id);
            if(operation=="hold") {
                if(_pending || _rows.size()>=32 || !actualWidget || actualWidget->thread()!=qApp->thread()
                        || QGuiApplication::applicationState()!=Qt::ApplicationActive
                        || !actualWidget->isVisible() || !actualWidget->isEnabled() || measured.value("keyboardPluginActive")!=QVariant(true)
                        || measured.value("upPressed").toDouble()!=0)return {};
                _widget=actualWidget;_run=run;_gesture=nonce();_started=_clock.elapsed();_pending=true;
                _rows.append(QVariantMap{{"gestureId",_gesture},{"runId",run},{"commandId",id},{"createdEpochMs",epoch},
                    {"pressEpochMs",0},{"releaseEpochMs",0},{"releaseReason",""},{"pressObserved",false},{"releaseObserved",false}});
                // Only this exact original event reaching this original widget
                // creates a dispatched-gesture history entry. ACKs do not.
                _press=std::make_unique<QKeyEvent>(QEvent::KeyPress,Qt::Key_Up,Qt::NoModifier,QString(),false,1);
                _busy=true;_dispatching=_press.get();
                QCoreApplication::sendEvent(actualWidget,_press.get());_dispatching=nullptr;_busy=false;
                performed=_rows.last().value("pressObserved").toBool();
                if(!_widget) { _valid=false;return {}; }
                if(_pending) {
                    const auto remaining=10000-elapsed();
                    if(remaining<=0)release("hold-deadline");else _timer.start(int(remaining));
                }
            } else if(_pending && _run==run && _gesture==gesture)performed=release("explicit");
            else {
                // Idempotent release only reads its original closed event.
                for(const auto& row:_rows)if(row.value("runId")==run && row.value("gestureId")==gesture)
                    performed=row.value("releaseObserved").toBool();
            }
        }
        if(!_valid)return {};
        const auto captured=now();if(!captured)return {};
        QVariantList rows;for(const auto& row:_rows)rows.append(row);
        return {{"phoneLifecycleWorldInputVersion",1},{"instance",_instance},{"sequence",++_sequence},
            {"commandId",id},{"runId",run},{"capturedEpochMs",captured},{"performed",performed},
            {"pending",_pending},{"pendingRun",_pending ? _run : QString()},{"pendingGesture",_pending ? _gesture : QString()},
            {"elapsedMs",_pending ? elapsed() : 0},{"timerActive",_timer.isActive()},{"gestures",rows}};
    }
protected:
    bool eventFilter(QObject* actualDestination,QEvent* event) override {
        if(actualDestination!=_widget || !_pending)return false;
        if(event!=_dispatching) {
            if((event->type()==QEvent::KeyPress || event->type()==QEvent::KeyRelease) && static_cast<QKeyEvent*>(event)->key()==Qt::Key_Up)_valid=false;
            return false;
        }
        if(event->type()==QEvent::KeyPress && event==_press.get()) {
            auto& row=_rows.last();if(row.value("pressObserved").toBool()) { _valid=false;return false; }
            row["pressObserved"]=true;row["pressEpochMs"]=now();
        } else if(event->type()==QEvent::KeyRelease) {
            auto& row=_rows.last();if(row.value("releaseObserved").toBool()) { _valid=false;return false; }
            row["releaseObserved"]=true;row["releaseEpochMs"]=now();
        }
        return false;
    }
private:
    bool release(const QString& reason) {
        if(!_pending || _releasing)return false;
        const bool wasBusy=_busy;_busy=true;_releasing=true;_timer.stop();
        if(_widget) {
            QKeyEvent releaseEvent(QEvent::KeyRelease,Qt::Key_Up,Qt::NoModifier,QString(),false,1);
            _dispatching=&releaseEvent;QCoreApplication::sendEvent(_widget,&releaseEvent);_dispatching=nullptr;
        }
        _rows.last()["releaseReason"]=reason;const bool observed=_rows.last().value("releaseObserved").toBool();
        _pending=false;_press.reset();_busy=wasBusy;_releasing=false;if(!observed)_valid=false;return observed;
    }
    static bool gui() { return qApp && QThread::currentThread()==qApp->thread() && QCoreApplication::arguments().contains("--testScript"); }
    static bool hex(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    qint64 now() { const auto value=QDateTime::currentMSecsSinceEpoch();if(value<=0 || value<_epoch) { _valid=false;return 0; }_epoch=value;return value; }
    qint64 elapsed() {const auto value=_clock.elapsed()-_started;if(value<0)_valid=false;return value;}
    QString _instance{nonce()},_run,_gesture;QPointer<QWidget> _widget;std::unique_ptr<QKeyEvent> _press;QEvent* _dispatching{nullptr};
    QTimer _timer;QElapsedTimer _clock;qint64 _started{0},_epoch{0};quint64 _sequence{0};bool _pending{false},_busy{false},_valid{true},_releasing{false};
    QSet<QString> _commands;QList<QVariantMap> _rows;
};
} // namespace overte::e2e
#endif
