// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Qt receiver/input/filter/timer and unchanged KeyboardMouse methods.
// Avatar physics and application/backend identity are explicit host seams.
#include <QApplication>
#include <QWidget>
#include <QTest>
#include <QThread>
#include <QJsonDocument>
#include <unordered_set>
#include <cstdio>
#include "tests/device/native/PhoneLifecycleWorldInput.h"
#include "tests/device/native/PhoneLifecycleMotion.h"
namespace controller {
enum class ChannelType {BUTTON};
struct Input { int id;int channel;Input(int device,int channel,ChannelType):id(device),channel(channel){}int getChannel()const{return channel;} };
class InputDevice {
public:float getButton(int channel)const;std::unordered_set<int> _buttonPressedMap;
};
}
class KeyboardMouseDevice:public QObject {
public:
    enum {KEYBOARD_MASK=0x00ff};
    class InputDevice:public controller::InputDevice {public:controller::Input makeInput(Qt::Key code)const;int _deviceID{19};};
    std::shared_ptr<InputDevice> _inputDevice=std::make_shared<InputDevice>();bool enabled{true};
    bool isActive()const{return enabled;}void keyPressEvent(QKeyEvent*);void keyReleaseEvent(QKeyEvent*);QVariantMap e2eForwardKeyObservation()const;
};
// ORIGINAL_KEYBOARD_METHODS
class Receiver:public QWidget {
public:KeyboardMouseDevice keyboard;int presses{0},releases{0};bool swallow{false};
    void keyPressEvent(QKeyEvent* event)override{++presses;if(!swallow)keyboard.keyPressEvent(event);event->accept();}
    void keyReleaseEvent(QKeyEvent* event)override{++releases;keyboard.keyReleaseEvent(event);event->accept();}
};
class HostApplication:public QApplication {
public:using QApplication::QApplication;Receiver* widget{nullptr};QWidget* phoneLifecycleInputWidget(){return widget;}
};
// ORIGINAL_TEST_BINDING
static void need(bool value){if(!value)throw std::runtime_error("Original lifecycle world input contract");}
int main(int argc,char**argv) {
    HostApplication app(argc,argv);Receiver widget;app.widget=&widget;widget.resize(640,900);widget.show();widget.activateWindow();QTest::qWait(60);
    const QString mode=argv[1],run(32,'a');TestScriptingInterface test;
    auto sample=[&] {overte::e2e::PhoneLifecycleMotion::get().sample(widget.keyboard.e2eForwardKeyObservation(),{1.0,2.0,3.0},{0.0,0.0,0.0},{0.0,0.0,0.0},true);};
    auto request=[&](const QString& operation,const QString& gesture=QString(),const QString& runId=QString()) {
        return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"action","phone-lifecycle-world-input"},
            {"operation",operation},{"runId",runId.isEmpty() ? run : runId},{"gestureId",gesture}};
    };
    sample();const auto before=test.phoneLifecycleWorldInput(request("observe"));need(!before.isEmpty());
    if(mode=="inactive") {widget.keyboard.enabled=false;sample();need(test.phoneLifecycleWorldInput(request("hold")).isEmpty() && widget.presses==0);return 0;}
    if(mode=="preexisting") {QKeyEvent actual(QEvent::KeyPress,Qt::Key_Up,Qt::NoModifier);QCoreApplication::sendEvent(&widget,&actual);sample();need(test.phoneLifecycleWorldInput(request("hold")).isEmpty() && widget.presses==1);return 0;}
    if(mode=="swallowed")widget.swallow=true;
    const auto command=request("hold");const auto held=test.phoneLifecycleWorldInput(command);need(!held.isEmpty());
    const auto original=held.value("source").toMap();need(original.value("pending")==true && original.value("gestures").toList().size()==1);
    const auto event=original.value("gestures").toList().first().toMap();const auto gesture=event.value("gestureId").toString();
    need(event.value("pressObserved")==true && event.value("pressEpochMs").toLongLong()>0 && widget.presses==1);
    need(test.phoneLifecycleWorldInput(command).isEmpty() && widget.presses==1);sample();
    const auto observed=test.phoneLifecycleWorldInput(request("observe"));need(observed.value("motion").toMap().value("upPressed").toDouble()==(mode=="swallowed" ? 0 : 1));
    if(mode=="foreign-release") {const auto rejected=test.phoneLifecycleWorldInput(request("release",gesture,QString(32,'b')));need(rejected.value("source").toMap().value("pending")==true && widget.releases==0);}
    if(mode=="foreign-key") {QKeyEvent foreign(QEvent::KeyPress,Qt::Key_Up,Qt::NoModifier);QCoreApplication::sendEvent(&widget,&foreign);need(test.phoneLifecycleWorldInput(request("observe")).isEmpty());return 0;}
    if(mode=="expiry")QTest::qWait(10020);
    const auto released=test.phoneLifecycleWorldInput(request("release",gesture));need(!released.isEmpty());sample();
    const auto after=test.phoneLifecycleWorldInput(request("observe"));const auto source=after.value("source").toMap();
    need(source.value("pending")==false && source.value("timerActive")==false && widget.releases==1 && after.value("motion").toMap().value("upPressed").toDouble()==0);
    const auto terminal=source.value("gestures").toList().first().toMap();need(terminal.value("releaseObserved")==true
        && terminal.value("releaseReason")== (mode=="expiry" ? "hold-deadline" : "explicit"));
    need(!test.phoneLifecycleWorldInput(request("release",gesture)).isEmpty() && widget.releases==1);
    std::puts(QJsonDocument::fromVariant(after).toJson(QJsonDocument::Compact).constData());return 0;
}
