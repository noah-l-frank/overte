// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PicoRemoteAvatarStream.h"
#include "PicoEmoteSourcePublisher.h"
#include "PicoEmoteSourceWidgets.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QSet>

namespace overte::e2e {
// NEW, uncompiled and not called. Requires the proposed readonly Stream gate
// and fixed CaptureFile leaf before integration. TSI owns this arena before
// calling advance; the arena holds every delegated resource before open.
class PicoEmoteSourceArena {
public:
    using Request=PicoEmoteSourceTransactionRequest;
    using Builder=PicoEmoteSourceTransaction::Builder;
    PicoEmoteSourceArena(std::shared_ptr<PicoRemoteAvatarStream> stream,QString root,
            std::shared_ptr<PicoEmoteSourceWidgets> widgets,Builder builders,std::function<bool()> alive):
        _stream(std::move(stream)),_root(std::move(root)),_widgets(std::move(widgets)),_builders(std::move(builders)),_alive(std::move(alive)) {}
    QVariantMap advance(std::shared_ptr<const Request> original) {
        if (_failed || _stopped || !context() || !_alive || !_alive() || !original || !original->fresh()
                || !PicoEmoteSourceTransaction::command(original->command) || !_builders || !_widgets
                || !_widgets->available() || !_stream || !_stream->sourceTransactionPermit(original->command)) {return fail();}
        const auto nonce=original->command.value("commandId").toString();
        if (_current && nonce==_command.value("commandId").toString()) {
            // Reusing this nonce with changed bindings is an actual failure.
            // Its owner keeps the FIRST pre-queue clock, not original->age.
            return original->command==_command ? _current->advance(_command) : fail();
        }
        if (_nonces.contains(nonce) || _nonces.size()>=512 || (_current && !_current->complete())) {return fail();}
        _nonces.insert(nonce);_command=original->command;
        if (!_publisher) {
            _publisher=std::make_shared<PicoEmoteSourcePublisher>(); // Strong before original file open.
            if (!_publisher->open(_root,[this] {return permit();})) {return fail();}
        }
        // A successful prior current-file duplicate is not a second immutable
        // Native history. The Host must retain the prior SDK literal BEFORE
        // publishing its next request under the SAME SourceLock. Only this
        // explicit new-request admission may release that resource-free byte
        // assembler. Failed/partial assemblers never reach this branch.
        _current=std::make_shared<PicoEmoteSourceTransaction>(original,
            [this](const QString& label,const QString& id) {
                if (!permit()) {return QVariantMap{};}
                return label=="widgets" ? _widgets->observe() : _builders(label,id);
            },[this] {return permit();},[this](const QString& id,QByteArray& bytes) {
                return permit() && _publisher && _publisher->publish(id,bytes);
            });
        return _current->advance(_command);
    }
    void stop() {_stopped=true;if (_publisher) {_publisher->stop();}}
    bool drain() {
        if (_closed) {return true;}
        if (_failed || !_stopped || (_current && !_current->complete())
                || (_publisher && !_publisher->drain())) {fail();return false;}
        _closed=true;return true;
    }
    bool unfinished() const {return _failed || (_current && !_current->complete());}
    bool selected() const {return bool(_publisher);}
private:
    bool context() const {return ::getpid()==_pid && QCoreApplication::instance()==_application
        && _application && QThread::currentThread()==_thread && _application->thread()==_thread;}
    bool permit() const {return !_failed && !_stopped && !_closed && context() && _alive && _alive() && _stream
        && _widgets && _widgets->available() && _stream->sourceTransactionPermit(_command);}
    QVariantMap fail() {_failed=true;if (_stream) {_stream->refuseMixed();}return {};}
    const pid_t _pid{::getpid()};QCoreApplication* const _application{QCoreApplication::instance()};
    QThread* const _thread{QThread::currentThread()};
    const std::shared_ptr<PicoRemoteAvatarStream> _stream;const QString _root;
    const std::shared_ptr<PicoEmoteSourceWidgets> _widgets;const Builder _builders;const std::function<bool()> _alive;
    std::shared_ptr<PicoEmoteSourcePublisher> _publisher;
    std::shared_ptr<PicoEmoteSourceTransaction> _current;QVariantMap _command;QSet<QString> _nonces;
    bool _failed{false},_stopped{false},_closed{false};
};
}
#endif
