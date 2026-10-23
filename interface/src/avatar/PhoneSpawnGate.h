// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <mutex>

// A timeout reports a failed entry; it must never authorize falling into an
// unloaded world. A new destination starts a new wait and clears that failure.
class PhoneSpawnGate {
public:
    void begin(double now) { std::lock_guard<std::mutex> lock(_mutex); _held = true; _reported = false; _started = now; }
    bool held() const { std::lock_guard<std::mutex> lock(_mutex); return _held; }
    bool update(double now, bool physicsReady, bool supportReady, bool mayReport = true) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!_held) { return false; }
        if (physicsReady && supportReady) { _held = false; return false; }
        // Credential entry is not world loading. Keep the safety hold active,
        // but give admission/support its normal deadline after the dialog closes.
        if (!mayReport) {
            _started = now;
            _reported = false;
            return false;
        }
        if (!_reported && now - _started >= 30.0) {
            _reported = true;
            return true;
        }
        return false;
    }
private:
    mutable std::mutex _mutex;
    bool _held { false };
    bool _reported { false };
    double _started { 0.0 };
};
