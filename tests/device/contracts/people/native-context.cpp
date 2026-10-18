// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Native services are explicit boundaries; all People controls are production QML.
#include <QtQuickTest/quicktest.h>
#include <QQmlContext>
#include <QQmlEngine>
#include <QObject>
#include <QCoreApplication>
#include <QVariant>
class NativeContext : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool active MEMBER active CONSTANT)
    Q_PROPERTY(bool mounted MEMBER mounted CONSTANT)
    Q_PROPERTY(bool canKick MEMBER canKick CONSTANT)
    Q_PROPERTY(bool use3DKeyboard MEMBER use3DKeyboard CONSTANT)
    Q_PROPERTY(bool raised MEMBER raised NOTIFY changed)
    Q_PROPERTY(bool password MEMBER password NOTIFY changed)
    Q_PROPERTY(bool punctuationMode MEMBER punctuationMode NOTIFY changed)
    Q_PROPERTY(QString findableBy MEMBER findableBy NOTIFY changed)
    Q_PROPERTY(QString username MEMBER username NOTIFY myUsernameChanged)
    Q_PROPERTY(QString metaverseServerURL MEMBER endpoint CONSTANT)
public:
    bool active{false}, mounted{false}, canKick{false}, use3DKeyboard{false}, raised{false}, password{false}, punctuationMode{false};
    QString findableBy{"all"}, username{"fixture"}, endpoint{"https://directory.invalid"};
    Q_INVOKABLE bool isLoggedIn() const { return true; }
    Q_INVOKABLE bool has3DHTML() const { return false; }
    Q_INVOKABLE bool getIgnoreStatus(QString) const { return false; }
    Q_PROPERTY(double avatarGain MEMBER avatarGain NOTIFY changed)
    double avatarGain{1.0};
    Q_INVOKABLE double getAvatarGain(QString) const { return avatarGain; }
    Q_INVOKABLE void setAvatarGain(QString, double value) { avatarGain=value; emit changed(); }
    Q_INVOKABLE bool getPersonalMuteStatus(QString) const { return false; }
    Q_INVOKABLE void palAction(QString,QString) {}
    Q_INVOKABLE void goToUser(QString,bool) {}
    Q_INVOKABLE void triggerHapticPulse(double,double,int) {}
    Q_INVOKABLE int deviceIdByTouchPoint(double,double) { return 0; }
    Q_INVOKABLE bool isLeftHand(int) { return false; }
    Q_INVOKABLE bool isRightHand(int) { return false; }
    Q_INVOKABLE void synthesizeKeyPress(QString,QObject* = nullptr) {}
    Q_INVOKABLE bool isOptionChecked(QString) const { return false; }
    Q_INVOKABLE QVariant getValue(QString, QVariant fallback = QVariant()) const { return fallback; }
    Q_INVOKABLE void setValue(QString,QVariant) {}
    Q_INVOKABLE bool gradientsSupported() const { return false; }
    Q_INVOKABLE bool hmdHandMouseActive() const { return false; }
signals:
    void changed();
    void myUsernameChanged();
};
class Setup : public QObject {
    Q_OBJECT
    NativeContext services;
public slots:
    void applicationAvailable() { QCoreApplication::setOrganizationName("OverteHostTests"); QCoreApplication::setOrganizationDomain("invalid.overte.test"); }
    void qmlEngineAvailable(QQmlEngine* engine) {
        for (const char* name : {"Account","AccountServices","GlobalServices","HMD","Users","UserActivityLogger", "PlatformInfo",
            "KeyboardScriptingInterface","Controller","MenuInterface","Settings","AddressManager","MyAvatar"}) {
            engine->rootContext()->setContextProperty(QString::fromLatin1(name), &services);
        }
    }
};
QUICK_TEST_MAIN_WITH_SETUP(people_connection, Setup)
#include "native-context.moc"
