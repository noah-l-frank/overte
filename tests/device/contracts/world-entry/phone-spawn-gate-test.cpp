// SPDX-License-Identifier: Apache-2.0
#include "interface/src/avatar/PhoneSpawnGate.h"
#include <cassert>

int main() {
    PhoneSpawnGate gate;
    assert(!gate.held());
    gate.begin(300);
    assert(!gate.update(330, false, false, false)); // credentials own input
    assert(!gate.update(400, true, false, false)); // failed login stays usable
    assert(gate.held()); // deferral never permits falling
    assert(!gate.update(401, true, false, true)); // fresh loading time after login
    assert(!gate.update(429.9, true, false, true));
    assert(gate.update(430, true, false, true)); // normal timeout remains enforced
    assert(!gate.update(431, true, false, true));
    assert(gate.held());
    assert(!gate.update(432, true, true, false)); // loading may still recover
    assert(!gate.held());
    gate.begin(500);
    assert(!gate.update(540, true, false, false));
    assert(!gate.update(541, true, false, true)); // authentication closes first
    assert(gate.held());
    assert(!gate.update(542, true, true, true)); // support arrives after login
    assert(!gate.held());
    assert(!gate.update(543, true, true, true)); // no stale warning after success
    gate.begin(100);
    assert(gate.held());
    assert(!gate.update(101, false, true)); // stale collider, new world not ready
    assert(gate.held());
    assert(!gate.update(129.9, true, false)); // rendering/loading alone cannot release
    assert(gate.held());
    assert(gate.update(130, true, false)); // one actionable timeout
    assert(gate.held()); // a timeout never authorizes a fall
    assert(!gate.update(131, true, false));
    assert(!gate.update(132, true, true)); // late support safely recovers
    assert(!gate.held());
    gate.begin(200); // new destination re-arms after a successful entry
    assert(gate.held());
    gate.begin(220); // navigation while waiting replaces the previous timeout
    assert(!gate.update(231, false, false));
    assert(gate.held());
    assert(gate.update(250, false, false));
    gate.begin(251); // retry after failed entry
    assert(!gate.update(252, true, true));
    assert(!gate.held());
}
