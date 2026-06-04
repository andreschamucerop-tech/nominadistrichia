"""Helpers de UI reutilizables para Streamlit."""
from __future__ import annotations
import streamlit as st

# JavaScript injected once per session. Finds every text input whose
# placeholder is "$" and adds real-time dot-separated (es-CO) formatting.
_PESO_JS = """
<script>
(function () {
    'use strict';
    function fmt(val) {
        var d = val.replace(/[^0-9]/g, '');
        if (!d) return '';
        return d.replace(/\\B(?=(\\d{3})+(?!\\d))/g, '.');
    }
    function setup(el) {
        if (el._peso) return;
        el._peso = true;
        if (el.value) el.value = fmt(el.value);
        el.addEventListener('input', function () {
            var pos = this.selectionStart;
            var oldLen = this.value.length;
            var f = fmt(this.value);
            if (this.value !== f) {
                this.value = f;
                var np = Math.max(0, pos + (f.length - oldLen));
                try { this.setSelectionRange(np, np); } catch (e) {}
            }
        });
    }
    function scan() {
        document.querySelectorAll(
            '.stTextInput input[placeholder="$"]'
        ).forEach(setup);
    }
    new MutationObserver(scan).observe(document.body, {childList: true, subtree: true});
    [0, 150, 500, 1500].forEach(function (ms) { setTimeout(scan, ms); });
})();
</script>
"""


def _ensure_peso_js() -> None:
    if not st.session_state.get("_peso_js_ok"):
        st.session_state["_peso_js_ok"] = True
        st.markdown(_PESO_JS, unsafe_allow_html=True)


def _fmt_default(value: float) -> str:
    """Format a float as a dot-separated integer string for initial display."""
    if not value:
        return ""
    s = str(int(value))
    parts: list[str] = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return ".".join(reversed(parts))


def peso_input(label: str, value: float = 0.0, **_) -> float:
    """Currency text input with real-time dot thousands-separator formatting.

    Accepts and ignores extra kwargs (min_value, format, etc.) so existing
    call sites that passed number_input kwargs don't break.
    """
    _ensure_peso_js()
    raw = st.text_input(label, value=_fmt_default(value), placeholder="$")
    digits = "".join(c for c in (raw or "") if c.isdigit())
    return float(digits) if digits else 0.0
