// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
(function () {
    if (window !== window.top || window.__overteEditor) { return; }
    var composing = null, editDepth = 0, revealScheduled = false, numericDrafts = new WeakMap();
    var editorOwner = null, editorIdentity = 0, appliedSequence = 0;
    function ownEditor(element) {
        if (element !== editorOwner) {
            editorOwner = element; ++editorIdentity; appliedSequence = 0; composing = null;
        }
    }
    function editable(element) {
        return element && !element.readOnly && !element.disabled
            && !(element.matches && element.matches(":disabled")) && (element instanceof HTMLTextAreaElement ||
            element instanceof HTMLInputElement && /^(text|search|email|url|tel|password|number)$/.test(element.type)
            || element.isContentEditable);
    }
    function current(element) {
        return document.activeElement === element && element.isConnected !== false && editable(element);
    }
    function value(element) {
        var text = element.value === undefined ? element.textContent : element.value;
        if (element instanceof HTMLInputElement && element.type === "number") {
            var draft = numericDrafts.get(element);
            if (draft && (draft.pending || text === draft.apiValue)) return draft.text;
            if (draft) numericDrafts.delete(element);
        }
        return text;
    }
    function keydown(element, key, command) {
        var accepted = element.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true,
            key: key, shiftKey: command.shift === true || command.extend === true,
            isComposing: !!(composing && composing.element === element) })) !== false;
        if (!current(element)) { composing = null; publish(); return false; }
        if (!accepted) publish();
        return accepted;
    }
    function beforeinput(element, inputType, data, isComposing, text, selected) {
        var accepted = element.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, cancelable: true,
            inputType: inputType, data: data, isComposing: isComposing })) !== false;
        if (!current(element)) { composing = null; publish(); return false; }
        // An application callback may replace the value or selection itself.
        // Never apply an older native edit over its newly chosen state.
        var now = selection(element);
        if (value(element) !== text || now[0] !== selected[0] || now[1] !== selected[1]) {
            composing = null; publish(); return false;
        }
        return accepted;
    }
    function enter(element, command) {
        if (!keydown(element, "Enter", command)) return;
        // The IME owns completion of its current preedit. Enter must not
        // submit it or replace it with a newline before the commit arrives.
        if (composing && composing.element === element) return;
        if (element instanceof HTMLInputElement) {
            if (command.shift || !element.form) return;
            var form = element.form, controls = document.querySelectorAll("button,input"), submitter = null;
            for (var i = 0; i < controls.length; ++i) {
                var candidate = controls[i];
                if (candidate.form === form && (candidate.type === "submit" || candidate.type === "image")) {
                    submitter = candidate; break;
                }
            }
            if (submitter && (submitter.disabled || submitter.matches(":disabled"))) return;
            if (!submitter) {
                var blockers = 0;
                for (var j = 0; j < form.elements.length; ++j) {
                    var control = form.elements[j];
                    if (control instanceof HTMLInputElement
                            && /^(text|search|url|tel|email|password|date|month|week|time|datetime-local|number)$/.test(control.type)) ++blockers;
                }
                if (blockers > 1) return;
            }
            // Implicit Enter activates the default button, including its
            // cancelable click handlers and submitter-specific overrides.
            // Without a button, requestSubmit retains validation and submit.
            if (submitter) submitter.click();
            else if (typeof form.requestSubmit === "function") form.requestSubmit();
            return;
        }
        var text = value(element), selected = selection(element);
        if (!beforeinput(element, "insertLineBreak", null, false, text, selected)) return;
        var emitted = replace(element, text, Math.min(selected[0], selected[1]), Math.max(selected[0], selected[1]), "\n");
        composing = null;
        if (!emitted) element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertLineBreak", data: null }));
        revealCaret(element);
        publish();
    }
    function selection(element) {
        if (typeof element.selectionStart === "number") {
            return element.selectionDirection === "backward" ? [element.selectionEnd, element.selectionStart] : [element.selectionStart, element.selectionEnd];
        }
        if (element instanceof HTMLInputElement && element.type === "number") { return [value(element).length, value(element).length]; }
        var selected = window.getSelection();
        if (!selected.rangeCount || !element.contains(selected.anchorNode) || !element.contains(selected.focusNode)) {
            return [0, 0];
        }
        function offset(node, index) {
            var range = document.createRange(); range.selectNodeContents(element);
            range.setEnd(node, index); return range.toString().length;
        }
        return [offset(selected.anchorNode, selected.anchorOffset), offset(selected.focusNode, selected.focusOffset)];
    }
    function editorGeometry(element, selected, point) {
        if (typeof window.getComputedStyle !== "function" || typeof document.createRange !== "function") return null;
        var bounds = element.getBoundingClientRect();
        if (!(bounds.width > 0 && bounds.height > 0)) return null;
        if (point && (!Number.isFinite(point.x) || !Number.isFinite(point.y)
                || point.x < bounds.left || point.x > bounds.right
                || point.y < bounds.top || point.y > bounds.bottom)) return null;
        var mirror = null, root = element;
        try {
            if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
                // Range cannot inspect an input's private browser text nodes.
                // A temporary, transparent text box lets the browser perform
                // its own font shaping, wrapping and point hit testing.
                if (element.type === "number") return null;
                var style = window.getComputedStyle(element);
                mirror = document.createElement("div");
                ["direction", "writing-mode", "font-style", "font-variant", "font-weight", "font-stretch",
                    "font-size", "font-family", "line-height", "letter-spacing", "word-spacing", "tab-size",
                    "text-transform", "text-align", "text-indent", "word-break", "overflow-wrap",
                    "padding-top", "padding-right", "padding-bottom", "padding-left",
                    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
                    "border-top-style", "border-right-style", "border-bottom-style", "border-left-style"].forEach(function (name) {
                    mirror.style.setProperty(name, style.getPropertyValue(name), "important");
                });
                var fixed = { position: "fixed", display: "block", margin: "0", "box-sizing": "border-box", right: "auto", bottom: "auto",
                    left: bounds.left + "px", top: bounds.top + "px", width: bounds.width + "px", height: bounds.height + "px",
                    overflow: "hidden", opacity: "0", visibility: "visible", "z-index": "2147483647",
                    "pointer-events": point ? "auto" : "none", transform: "none", transition: "none", animation: "none",
                    "white-space": element instanceof HTMLTextAreaElement ? style.whiteSpace : "pre" };
                // The mirror has no scrollbars. Reserve the actual control's
                // scrollbar space so wrapping and scroll limits still match.
                fixed.width = (element.clientWidth + parseFloat(style.borderLeftWidth) + parseFloat(style.borderRightWidth)) + "px";
                fixed.height = (element.clientHeight + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)) + "px";
                Object.keys(fixed).forEach(function (name) { mirror.style.setProperty(name, fixed[name], "important"); });
                if (element instanceof HTMLInputElement) {
                    var contentHeight = bounds.height - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth)
                        - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
                    if (contentHeight > 0) mirror.style.setProperty("line-height", contentHeight + "px", "important");
                }
                var text = value(element);
                if (text.length > 65536) return null; // Bound temporary layout work independently of page size.
                mirror.textContent = (element.type === "password" ? "\u2022".repeat(text.length) : text) + "\u200b";
                document.documentElement.appendChild(mirror);
                mirror.scrollLeft = element.scrollLeft; mirror.scrollTop = element.scrollTop;
                root = mirror;
            }
            function caret(index) {
                var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node, remaining = index;
                while ((node = walker.nextNode())) {
                    if (remaining <= node.length) {
                        var range = document.createRange(); range.setStart(node, remaining); range.collapse(true);
                        var rectangle = range.getBoundingClientRect();
                        if (!Number.isFinite(rectangle.x) || !Number.isFinite(rectangle.y) || rectangle.height <= 0) return null;
                        return { x: rectangle.x, y: rectangle.y, width: 1, height: rectangle.height };
                    }
                    remaining -= node.length;
                }
                return null;
            }
            if (!point) return { caret: caret(selected[1]), anchorCaret: caret(selected[0]) };
            var hit;
            if (typeof document.caretRangeFromPoint === "function") hit = document.caretRangeFromPoint(point.x, point.y);
            else if (typeof document.caretPositionFromPoint === "function") {
                var position = document.caretPositionFromPoint(point.x, point.y);
                if (position) { hit = document.createRange(); hit.setStart(position.offsetNode, position.offset); hit.collapse(true); }
            }
            if (!hit || !root.contains(hit.startContainer)) return null;
            var prefix = document.createRange(); prefix.selectNodeContents(root); prefix.setEnd(hit.startContainer, hit.startOffset);
            var offset = prefix.toString().length;
            return boundary(value(element), offset) ? { offset: offset } : null;
        } finally {
            if (mirror) mirror.remove();
        }
    }
    function revealCaret(element) {
        // setRangeText and setSelectionRange do not perform the browser's
        // normal caret scrolling. Only reveal our completed native edit;
        // observing a page or dragging its grips must retain manual scroll.
        if (!current(element) || !(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) return;
        var geometry = editorGeometry(element, selection(element));
        if (!geometry || !geometry.caret || element.clientWidth <= 0 || element.clientHeight <= 0) return;
        var caret = geometry.caret, bounds = element.getBoundingClientRect();
        var left = bounds.left + element.clientLeft, top = bounds.top + element.clientTop;
        var dx = caret.x < left ? caret.x - left : Math.max(0, caret.x + caret.width - left - element.clientWidth);
        var dy = caret.y < top ? caret.y - top : Math.max(0, caret.y + caret.height - top - element.clientHeight);
        if (dx) element.scrollLeft += dx;
        if (dy) element.scrollTop += dy;
    }
    function publish(requestKeyboard) {
        // Rich-text browser edits can emit input before our preedit range is
        // updated. Publish the completed transaction, never that mixed state.
        if (editDepth) return;
        var element = document.activeElement;
        if (!editable(element)) { ownEditor(null); composing = null; window.__overteEditorTransport.editor({ active: false }); return; }
        ownEditor(element);
        var sensitive = element.type === "password", text = value(element);
        var selected = selection(element), nativeSelected = selected;
        if (composing && composing.element === element && text.slice(composing.start, composing.end) !== composing.text) {
            // A page formatter owns its replacement; it is no longer our preedit.
            composing = null;
        }
        if (composing && composing.element === element) {
            // Qt's surrounding text and offsets exclude the preedit. Android
            // adds its own composing text when exposing the input connection.
            var first = composing.start, last = composing.end;
            text = text.slice(0, first) + text.slice(last);
            nativeSelected = selected.map(function (offset) { return offset <= first ? offset :
                offset >= last ? offset - (last - first) : first; });
        }
        var start = Math.max(0, nativeSelected[1] - 8192), bounds = element.getBoundingClientRect();
        if (!boundary(text, start)) --start;
        var end = Math.min(text.length, start + 16384);
        if (!boundary(text, end)) --end;
        // Password contents never cross the DOM/native boundary.
        var state = { active: true, sensitive: sensitive, requestKeyboard: requestKeyboard === true,
            editor: String(editorIdentity), sequence: appliedSequence, composing: !!(composing && composing.element === element),
            text: sensitive ? "" : text.slice(start, end), length: end - start,
            cursor: nativeSelected[1] - start, anchor: nativeSelected[0] - start, absoluteCursor: nativeSelected[1],
            x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height,
            kind: element.isContentEditable ? "contenteditable" : element.type || "text" };
        var geometry = editorGeometry(element, selected);
        if (geometry && geometry.caret && geometry.anchorCaret) {
            state.caret = geometry.caret; state.anchorCaret = geometry.anchorCaret;
        }
        window.__overteEditorTransport.editor(state);
    }
    function revealFocusedEditor() {
        revealScheduled = false;
        var element = document.activeElement;
        if (!current(element)) { return; }
        var viewport = window.visualViewport;
        var width = viewport ? viewport.width : window.innerWidth;
        var height = viewport ? viewport.height : window.innerHeight;
        if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) { return; }
        var left = viewport ? viewport.offsetLeft || 0 : 0;
        var top = viewport ? viewport.offsetTop || 0 : 0;
        var bounds = element.getBoundingClientRect();
        var outsideX = bounds.width <= width
            ? bounds.x < left || bounds.x + bounds.width > left + width
            : bounds.x >= left + width || bounds.x + bounds.width <= left;
        var outsideY = bounds.height <= height
            ? bounds.y < top || bounds.y + bounds.height > top + height
            : bounds.y >= top + height || bounds.y + bounds.height <= top;
        if (outsideX || outsideY) {
            element.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
        publish();
    }
    function scheduleReveal() {
        if (revealScheduled) { return; }
        revealScheduled = true;
        window.requestAnimationFrame(revealFocusedEditor);
    }
    function boundary(text, index) {
        return index >= 0 && index <= text.length && !(index > 0 && index < text.length
            && text.charCodeAt(index - 1) >= 0xD800 && text.charCodeAt(index - 1) <= 0xDBFF
            && text.charCodeAt(index) >= 0xDC00 && text.charCodeAt(index) <= 0xDFFF);
    }
    function point(element, offset) {
        var walk = document.createTreeWalker(element, NodeFilter.SHOW_TEXT), node;
        while ((node = walk.nextNode())) {
            if (offset <= node.length) { return [node, offset]; }
            offset -= node.length;
        }
        return [element, element.childNodes.length];
    }
    function select(element, start, end) {
        // Number controls keep their caret inside the browser and do not
        // support setSelectionRange, even though that method is present.
        if (element instanceof HTMLInputElement && element.type === "number") return;
        if (typeof element.setSelectionRange === "function") { element.setSelectionRange(Math.min(start, end), Math.max(start, end), start > end ? "backward" : "forward"); return; }
        var left = point(element, start), right = point(element, end), range = document.createRange();
        var selected = window.getSelection();
        if (selected.setBaseAndExtent) { selected.setBaseAndExtent(left[0], left[1], right[0], right[1]); return; }
        range.setStart(left[0], left[1]); range.setEnd(right[0], right[1]);
        selected.removeAllRanges(); selected.addRange(range);
    }
    function replace(element, text, start, end, insertion, forwardDelete) {
        // execCommand on rich text may emit its own native input event. Plain
        // input/textarea setRangeText does not; report each edit only once.
        var emitted = false, observe = function () { emitted = true; };
        element.addEventListener("input", observe, true);
        try {
            if (element instanceof HTMLInputElement && element.type === "number") {
                // Assigning value discards incomplete numbers such as "12.".
                // Native editing preserves that draft and the browser's caret.
                var previousDraft = numericDrafts.get(element);
                var draft = { text: text.slice(0, start) + insertion + text.slice(end), pending: true };
                numericDrafts.set(element, draft);
                if (insertion) document.execCommand("insertText", false, insertion);
                else if (start !== end) document.execCommand(forwardDelete ? "forwardDelete" : "delete", false);
                draft.pending = false; draft.apiValue = element.value;
                // Android may expose an empty API value for a visible "12.".
                // Keep its edit length so the next IME replacement is valid.
                var incomplete = /(?:[.eE]|[eE][+-]|^[+-])$/.test(draft.text);
                if (!emitted) {
                    if (previousDraft) numericDrafts.set(element, previousDraft);
                    else numericDrafts.delete(element);
                } else if (!incomplete || !(draft.apiValue === "" ||
                        draft.text.endsWith(".") && draft.apiValue === draft.text.slice(0, -1))) {
                    numericDrafts.delete(element);
                }
            }
            else if (typeof element.setRangeText === "function") element.setRangeText(insertion, start, end, "end");
            else { select(element, start, end); document.execCommand("insertText", false, insertion); }
        } finally { element.removeEventListener("input", observe, true); }
        return emitted;
    }
    function ime(element, command, text, selected) {
        var previous = composing && composing.element === element, left = previous ? composing.start : Math.min(selected[0], selected[1]);
        var commit = command.commit || "", preedit = command.preedit || "";
        if (!previous && !commit && !preedit && !command.replaceLength) {
            // Selection-only Qt updates preserve the value and are not text input.
            if (command.selection && boundary(text, command.selection.start)
                    && boundary(text, command.selection.start + command.selection.length)) {
                select(element, command.selection.start, command.selection.start + command.selection.length);
            }
            publish(); return;
        }
        var right = previous ? composing.end : Math.max(selected[0], selected[1]);
        var base = text.slice(0, left) + text.slice(right), start = left + command.replaceStart, end = start + command.replaceLength;
        if (!boundary(base, start) || !boundary(base, end) || start > end) return;
        var committed = base.slice(0, start) + commit + base.slice(end), position = start + commit.length;
        if (command.selection) {
            var requested = command.selection.start;
            if (boundary(committed, requested)) position = requested;
        }
        var result = committed.slice(0, position) + preedit + committed.slice(position);
        // Replace only the changed DOM range so surrounding rich text retains its nodes.
        var first = 0, oldEnd = text.length, newEnd = result.length;
        while (first < oldEnd && first < newEnd && text.charAt(first) === result.charAt(first)) ++first;
        while (oldEnd > first && newEnd > first && text.charAt(oldEnd - 1) === result.charAt(newEnd - 1)) { --oldEnd; --newEnd; }
        if (!boundary(text, first) || !boundary(result, first)) --first;
        if (!boundary(text, oldEnd)) ++oldEnd;
        if (!boundary(result, newEnd)) ++newEnd;
        var entering = preedit.length > 0, completed = previous && (commit.length > 0 || !entering);
        var inputType = entering ? "insertCompositionText" : "insertText";
        if (!beforeinput(element, inputType, commit + preedit, entering, text, selected)) return;
        if (completed) element.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: commit }));
        if (entering && (!previous || completed)) element.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
        if (!current(element) || value(element) !== text) { composing = null; publish(); return; }
        var emitted = replace(element, text, first, oldEnd, result.slice(first, newEnd));
        composing = entering ? { element: element, start: position, end: position + preedit.length, text: preedit } : null;
        var caret = position + Math.max(0, Math.min(preedit.length, command.cursor));
        if (boundary(result, caret)) select(element, caret, caret);
        if (!entering && command.selection && boundary(result, position + command.selection.length)) select(element, position, position + command.selection.length);
        if (entering) element.dispatchEvent(new CompositionEvent("compositionupdate", { bubbles: true, data: preedit }));
        if (!emitted) element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: inputType, data: commit + preedit, isComposing: entering }));
        revealCaret(element);
        publish();
    }
    window.__overteEditor = {
        publish: publish,
        edit: function (command) {
            var target = document.activeElement;
            ownEditor(current(target) ? target : null);
            // Native type-ahead acknowledgements belong to one exact focus owner.
            // A page may still invoke this private DOM editor directly without a native ticket.
            if (command.editor !== undefined || command.sequence !== undefined) {
                if (!editorOwner || command.editor !== String(editorIdentity) || !Number.isSafeInteger(command.sequence)
                        || command.sequence <= appliedSequence) { publish(); return; }
                appliedSequence = command.sequence;
            }
            ++editDepth;
            try {
                var element = document.activeElement;
                if (!current(element)) { composing = null; publish(); return; }
                if (command.action === "enter") { enter(element, command); return; }
                var text = value(element), selected = selection(element);
                if (command.action === "point") {
                    var handle = command.handle === undefined ? 1 : command.handle;
                    if (handle !== 1 && handle !== 2 && handle !== 3) return;
                    var lower = Math.min(selected[0], selected[1]), upper = Math.max(selected[0], selected[1]);
                    if (handle !== 1 && lower === upper) return;
                    var hit = editorGeometry(element, selected, command);
                    if (hit && current(element) && value(element) === text) {
                        function adjacent(index, previous) {
                            if (typeof Intl !== "undefined" && typeof Intl.Segmenter === "function") {
                                var segment = new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text)
                                    .containing(previous ? index - 1 : index);
                                if (segment) return previous ? segment.index : segment.index + segment.segment.length;
                            }
                            var next = Math.max(0, Math.min(text.length, index + (previous ? -1 : 1)));
                            if (!boundary(text, next)) next += previous ? -1 : 1;
                            return next;
                        }
                        if (handle === 2) select(element, hit.offset < upper ? hit.offset : adjacent(upper, true), upper);
                        else if (handle === 3) select(element, lower, hit.offset > lower ? hit.offset : adjacent(lower, false));
                        else select(element, hit.offset, hit.offset);
                        composing = null; publish();
                    }
                    return;
                }
                if (command.action === "ime") { ime(element, command, text, selected); return; }
                if (command.action !== "selection" && !command.composing) {
                    var keys = { backspace: "Backspace", delete: "Delete", left: "ArrowLeft", right: "ArrowRight", home: "Home", end: "End" };
                    var key = keys[command.action] || command.text;
                    if (key && !keydown(element, key, command)) return;
                    text = value(element); selected = selection(element);
                }
                var start = Math.min(selected[0], selected[1]), end = Math.max(selected[0], selected[1]);
                if (composing && composing.element === element) { start = composing.start; end = composing.end; }
                if (command.replaceStart || command.replaceLength) {
                    var base = composing && composing.element === element ? composing.start : selected[1];
                    start = base + command.replaceStart; end = start + command.replaceLength;
                    // Qt replacements count committed text, skipping the old preedit range.
                    if (composing && composing.element === element) {
                        if (start > composing.start) { start += composing.end - composing.start; }
                        if (end >= composing.start) { end += composing.end - composing.start; }
                    }
                }
                if (command.action === "backspace" && start === end && start > 0) {
                    --start; if (!boundary(text, start)) { --start; }
                }
                if (command.action === "delete" && start === end && end < text.length) {
                    ++end; if (!boundary(text, end)) { ++end; }
                }
                if (!boundary(text, start) || !boundary(text, end) || start > end) { return; }
                if (command.action === "left" || command.action === "right" || command.action === "home" || command.action === "end") {
                    var next = selected[1];
                    if (command.action === "home") next = text.lastIndexOf("\n", next - 1) + 1;
                    else if (command.action === "end") { next = text.indexOf("\n", next); if (next < 0) next = text.length; }
                    else { next = Math.max(0, Math.min(text.length, next + (command.action === "left" ? -1 : 1))); if (!boundary(text, next)) next += command.action === "left" ? -1 : 1; }
                    select(element, command.extend ? selected[0] : next, next); composing = null; revealCaret(element); publish(); return;
                }
                if (command.action === "selection") {
                    if (boundary(text, command.start) && boundary(text, command.start + command.length)) {
                        select(element, command.start, command.start + command.length); composing = null; revealCaret(element); publish();
                    }
                    return;
                }
                var insertion = command.text || "";
                var wasComposing = composing && composing.element === element;
                var inputType = command.composing ? "insertCompositionText" :
                    command.action === "backspace" ? "deleteContentBackward" :
                    command.action === "delete" ? "deleteContentForward" : "insertText";
                if (!beforeinput(element, inputType, insertion, command.composing === true, text, selected)) return;
                if (command.composing && !wasComposing) element.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
                if (!current(element) || value(element) !== text) { composing = null; publish(); return; }
                var emitted = replace(element, text, start, end, insertion, command.action === "delete");
                if (command.composing) element.dispatchEvent(new CompositionEvent("compositionupdate", { bubbles: true, data: insertion }));
                else if (wasComposing) element.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: insertion }));
                composing = command.composing ? { element: element, start: start, end: start + insertion.length, text: insertion } : null;
                if (!emitted) element.dispatchEvent(new InputEvent("input", { bubbles: true,
                    inputType: inputType, data: insertion,
                    isComposing: command.composing === true }));
                if (command.composing && typeof command.cursor === "number") {
                    var caret = start + Math.max(0, Math.min(insertion.length, command.cursor));
                    if (boundary(element.value === undefined ? element.textContent : element.value, caret)) select(element, caret, caret);
                }
                revealCaret(element);
                publish();
            } finally { if (--editDepth === 0) publish(); }
        },
        blur: function () { composing = null; if (document.activeElement) { document.activeElement.blur(); } publish(); }
    };
    ["focusin", "focusout", "input", "selectionchange", "compositionend"].forEach(function (name) {
        document.addEventListener(name, publish, true);
    });
    document.addEventListener("pointerup", function (event) {
        var element = document.activeElement;
        // Back hides the OS keyboard without blurring the DOM editor. A tap
        // at the same caret may emit neither focus nor selection changes.
        if (current(element) && (event.target === element || element.contains(event.target))) publish(true);
    }, true);
    document.addEventListener("reset", function () { numericDrafts = new WeakMap(); }, true);
    // Native overlay clipping alone does not move a focused DOM editor. React
    // after the browser accepts its actual IME viewport, retaining the page.
    window.addEventListener("resize", scheduleReveal);
    if (window.visualViewport) { window.visualViewport.addEventListener("resize", scheduleReveal); }
}());
