"""
Copied from Lazy-Bing-Server/CalyxLib-Python
Licensed under LGPL v3 only
RComplexText — per-character rich text for Minecraft (MCDReforged v2.15.7).

Unlike RText which applies styles to the entire text object, RComplexText
stores style metadata for each individual character, enabling:

- Range-based styling via the :meth:`RComplexText.range` context manager
- Clean ``split`` / ``rsplit`` that preserves per-character metadata
- ``§`` format code conversion to JSON properties
- Minecraft raw JSON export

Design
------
Each character position carries its own **slot** dict containing
``color``, ``styles``, ``hover_event``, ``click_event``, ``extra_keys``.

The internal ``_text`` is a ``List[str]`` where each element is either a
single character (for normal text) or an empty string ``""`` (for
translatable/score/keybind/selector/nbt components whose content lives
in the slot's ``extra_keys``).  ``"".join(_text)`` naturally produces
the human-readable plain text, and ``str.split`` on the joined text
never cuts through translatable placeholders.

Range-based styling uses a context manager::

    ct = RComplexText('Hello World')
    with ct.range(0, 5):
        ct.set_color(RColor.red)
        ct.set_styles(RStyle.bold)
    with ct.range(6, 11):
        ct.set_color(RColor.blue)
"""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union

from colorama import Style
from typing_extensions import Self, Unpack, override

from mcdreforged.api.rtext import (
    RClickEvent, RColor, RColorRGB, RHoverEvent, RHoverText,
    RStyle, RTextBase, RTextJsonFormat, RTextList,
)

__all__ = ["RComplexText"]


# ═══════════════════════════════════════════════════════════════════════
# § format code constants
# ═══════════════════════════════════════════════════════════════════════

_SECTION_SIGN = "\u00a7"  # §

_COLOR_CODES: Dict[str, str] = {
    "0": "black",     "1": "dark_blue",    "2": "dark_green",
    "3": "dark_aqua", "4": "dark_red",     "5": "dark_purple",
    "6": "gold",      "7": "gray",         "8": "dark_gray",
    "9": "blue",      "a": "green",        "b": "aqua",
    "c": "red",       "d": "light_purple", "e": "yellow",
    "f": "white",
}

_STYLE_CODES: Dict[str, str] = {
    "k": "obfuscated",  "l": "bold",           "m": "strikethrough",
    "n": "underlined",  "o": "italic",
}

_RESET_CODE = "r"
_HEX_DIGIT_CODE = "x"

_STYLE_PROPS: Dict[str, str] = {
    "obfuscated":    "obfuscated",
    "bold":          "bold",
    "strikethrough": "strikethrough",
    "underlined":    "underlined",
    "italic":        "italic",
}


# ═══════════════════════════════════════════════════════════════════════
# Per-character slot helpers
# ═══════════════════════════════════════════════════════════════════════

def _new_slot() -> dict:
    """Create an empty per-character metadata slot."""
    return {
        "color": None,
        "styles": set(),
        "hover_event": None,
        "click_event": None,
        "extra_keys": None,
    }


def _copy_slot(slot: dict) -> dict:
    """Copy a slot (shallow for event objects, deep for styles set)."""
    return {
        "color": slot["color"],
        "styles": set(slot["styles"]),
        "hover_event": slot["hover_event"],
        "click_event": slot["click_event"],
        "extra_keys": slot["extra_keys"],
    }


def _slot_fingerprint(slot: dict, json_format: RTextJsonFormat) -> tuple:
    """Hashable fingerprint for run-merging in :meth:`to_json_object`."""
    hover_json = slot["hover_event"].to_json_object(json_format) if slot["hover_event"] else None
    click_json = slot["click_event"].to_json_object(json_format) if slot["click_event"] else None
    return (
        slot["color"],
        frozenset(slot["styles"]),
        repr(hover_json),
        repr(click_json),
        repr(slot["extra_keys"]),
    )


def _is_plain_slot(slot: dict) -> bool:
    """Return *True* when a slot has no styling at all."""
    return (
        slot["color"] is None
        and len(slot["styles"]) == 0
        and slot["hover_event"] is None
        and slot["click_event"] is None
        and slot["extra_keys"] is None
    )


def _slot_to_json(slot: dict, json_format: RTextJsonFormat) -> dict:
    """Convert a non-empty slot to Minecraft JSON text-component properties."""
    result: dict = {}
    if slot["extra_keys"] is not None:
        result.update(slot["extra_keys"])
    if slot["color"] is not None:
        result["color"] = slot["color"].name
    for style in slot["styles"]:
        result[style.name] = True
    if slot["click_event"] is not None:
        result[json_format.value.click_event_key] = slot["click_event"].to_json_object(json_format)
    if slot["hover_event"] is not None:
        he = slot["hover_event"]
        if isinstance(he, RHoverText) and isinstance(he.text, RComplexText):
            # Serialize RComplexText hover text via its to_json_object
            he_json: dict = {"action": he.action.name}
            he_json["value"] = he.text.to_json_object(json_format=json_format)
            result[json_format.value.hover_event_key] = he_json
        else:
            result[json_format.value.hover_event_key] = he.to_json_object(json_format)
    return result


# ═══════════════════════════════════════════════════════════════════════
# JSON → flat (text, slots)
# ═══════════════════════════════════════════════════════════════════════

def _flatten_json(
    obj: Any,
    text_parts: list,
    slot_parts: list,
    parent_slot: dict,
    json_format: Optional[RTextJsonFormat] = None,
) -> None:
    """Recursively flatten a Minecraft JSON object into *(text_parts, slot_parts)*."""
    if json_format is None:
        json_format = RTextJsonFormat.default()

    if isinstance(obj, str):
        for ch in obj:
            text_parts.append(ch)
            slot_parts.append(_copy_slot(parent_slot))
        return

    if isinstance(obj, dict):
        current = _copy_slot(parent_slot)

        if "color" in obj:
            try:
                current["color"] = RColor.from_mc_value(obj["color"])
            except (ValueError, KeyError):
                pass

        for style in RStyle:
            if obj.get(style.name, False):
                current["styles"].add(style)

        if json_format is None:
            json_format = RTextJsonFormat.guess(obj)
        click_key = json_format.value.click_event_key
        hover_key = json_format.value.hover_event_key
        if click_key in obj and isinstance(obj[click_key], dict):
            current["click_event"] = RClickEvent.from_json_object(obj[click_key], json_format)
        if hover_key in obj and isinstance(obj[hover_key], dict):
            current["hover_event"] = RHoverEvent.from_json_object(obj[hover_key], json_format)

        # Translatable / score / keybind / selector / nbt components
        _CONTENT_KEYS = {"translate", "score", "keybind", "selector", "nbt"}
        if "text" not in obj and (_CONTENT_KEYS & obj.keys()):
            _STYLE_KEYS = {"color", "bold", "italic", "underlined",
                           "strikethrough", "obfuscated"}
            current["extra_keys"] = {
                k: v for k, v in obj.items()
                if k not in _STYLE_KEYS and k != click_key and k != hover_key
            }
            text_parts.append("")   # empty string placeholder for non-text component
            slot_parts.append(_copy_slot(current))
            return

        for ch in obj.get("text", ""):
            text_parts.append(ch)
            slot_parts.append(_copy_slot(current))

        for child in obj.get("extra", []):
            _flatten_json(child, text_parts, slot_parts, current, json_format)
        return

    if isinstance(obj, list):
        for item in obj:
            _flatten_json(item, text_parts, slot_parts, parent_slot, json_format)
        return


# ═══════════════════════════════════════════════════════════════════════
# § format-code parsing
# ═══════════════════════════════════════════════════════════════════════

def _parse_format_codes(
    text: List[str],
    base_slots: Optional[List[dict]] = None,
) -> Tuple[List[str], List[dict]]:
    """Parse ``§`` formatting codes from *text*, apply them to per-character
    slots, and return ``(clean_text, clean_slots)`` with all ``§X`` sequences
    removed.  Empty-string entries (translatable placeholders) are preserved."""
    cur_color: Optional[RColor] = None
    cur_styles: Set[RStyle] = set()
    reset_pending = False       # True after §r; next char clears inherited styles

    out_text: List[str] = []
    out_slots: List[dict] = []
    i = 0
    raw_len = len(text)

    while i < raw_len:
        ch = text[i]

        # Empty-string placeholder (translatable) — pass through, apply current styles
        if ch == "":
            slot = _copy_slot(base_slots[i]) if base_slots and i < len(base_slots) else _new_slot()
            if reset_pending:
                slot["color"] = None
                slot["styles"] = set()
                reset_pending = False
            if cur_color is not None:
                slot["color"] = cur_color
            slot["styles"] |= cur_styles
            out_text.append("")
            out_slots.append(slot)
            i += 1
            continue

        # ── handle § ────────────────────────────────────────────────
        if ch == _SECTION_SIGN and i + 1 < raw_len:
            code = text[i + 1].lower()

            # Hex colour: §x§d§1§g§2§3  (14 chars total)
            if code == _HEX_DIGIT_CODE and i + 13 < raw_len:
                hex_chars: List[str] = []
                valid = True
                for j in range(6):
                    pos = i + 2 + j * 2
                    if pos < raw_len and text[pos] == _SECTION_SIGN:
                        hex_chars.append(text[pos + 1].lower())
                    else:
                        valid = False
                        break
                if valid and all(c in "0123456789abcdef" for c in hex_chars):
                    cur_color = RColorRGB.from_code("#" + "".join(hex_chars))
                    cur_styles.clear()
                    i += 14
                    continue

            if code in _COLOR_CODES:
                cur_color = RColor.from_mc_value(_COLOR_CODES[code])
                i += 2
                continue

            if code in _STYLE_CODES:
                style_name = _STYLE_CODES[code]
                for s in RStyle:
                    if s.name == style_name:
                        cur_styles.add(s)
                        break
                i += 2
                continue

            if code == _RESET_CODE:
                cur_color = None
                cur_styles.clear()
                reset_pending = True
                i += 2
                continue

        # ── regular character ────────────────────────────────────────
        slot = _copy_slot(base_slots[i]) if base_slots and i < len(base_slots) else _new_slot()
        if reset_pending:
            slot["color"] = None
            slot["styles"] = set()
            reset_pending = False
        if cur_color is not None:
            slot["color"] = cur_color
        slot["styles"] |= cur_styles
        out_text.append(ch)
        out_slots.append(slot)
        i += 1

    return out_text, out_slots


# ═══════════════════════════════════════════════════════════════════════
# RComplexText
# ═══════════════════════════════════════════════════════════════════════

class RComplexText(RTextBase):
    """
    Per-character rich text component for Minecraft.

    Each character stores its own ``color``, ``styles``, ``hover_event``,
    ``click_event``, ``extra_keys``.  Non-text components (translatable,
    score, keybind, selector, nbt) occupy a single position with an empty
    string in ``_text`` and their content in ``extra_keys``.

    Styling methods (``set_color``, ``set_styles``, etc.) apply to the
    full text by default.  Use the :meth:`range` context manager to target
    a specific character range::

        ct = RComplexText('Hello World')
        with ct.range(0, 5):
            ct.set_color(RColor.red)       # "Hello" only
        with ct.range(6, 11):
            ct.set_color(RColor.blue)      # "World" only
    """

    _text: List[str]
    _slots: List[dict]

    def __init__(self, text: str = "", *, parse_format_codes: bool = False) -> None:
        self._slot_range_cv: ContextVar[Optional[Tuple[int, int]]] = ContextVar(
            f'_slot_range_{id(self):x}', default=None
        )
        if parse_format_codes:
            self._text, self._slots = _parse_format_codes(list(text))
        else:
            self._text = list(text)
            self._slots = [_new_slot() for _ in text]

    # ── internal helpers ────────────────────────────────────────────

    def _plain_str(self) -> str:
        """Joined text with empty-string (translatable) positions skipped."""
        return "".join(self._text)

    def _norm_index(self, idx: int) -> int:
        if idx < 0:
            idx += len(self._text)
        return max(0, min(idx, len(self._text)))

    def _iter_slots(self):
        rng = self._slot_range_cv.get()
        if rng is not None:
            s, e = rng
        else:
            s, e = 0, len(self._text)
        yield from self._slots[s:e]

    # ── range context manager ───────────────────────────────────────

    @contextmanager
    def range(self, start: int = 0, end: Optional[int] = None) -> Iterator[Self]:
        """Context manager that scopes subsequent styling calls to
        ``[start, end)`` character indices.

        Negative *start*/*end* count from the end of the text.
        *end* defaults to the text length (i.e. "to the end").

        Can be nested; the innermost range wins.

        Stored in a :class:`~contextvars.ContextVar` so ranges never
        leak across threads or async tasks.
        """
        s = self._norm_index(start)
        e = self._norm_index(end if end is not None else len(self._text))

        token = self._slot_range_cv.set((s, e))
        try:
            yield self
        finally:
            self._slot_range_cv.reset(token)

    # ── RTextBase abstract methods ──────────────────────────────────

    @override
    def to_json_object(self, **kwargs: Unpack[RTextBase.ToJsonKwargs]) -> Union[dict, list]:
        json_format = kwargs.get("json_format", RTextJsonFormat.default())

        if not self._text:
            return {"text": ""}

        runs: List[Tuple[str, dict]] = []
        for ch, slot in zip(self._text, self._slots):
            fp = _slot_fingerprint(slot, json_format)
            if runs and _slot_fingerprint(runs[-1][1], json_format) == fp:
                prev_text, prev_slot = runs[-1]
                runs[-1] = (prev_text + ch, prev_slot)
            else:
                runs.append((ch, slot))

        components: list = []
        for text, slot in runs:
            if text == "" and slot["extra_keys"] is not None:
                components.append(_slot_to_json(slot, json_format))
            elif _is_plain_slot(slot):
                components.append({"text": text})
            else:
                obj = _slot_to_json(slot, json_format)
                obj["text"] = text
                components.append(obj)

        if len(components) == 1:
            return components[0]
        return [''] + components

    @override
    def to_plain_text(self) -> str:
        parts: List[str] = []
        for i, ch in enumerate(self._text):
            if ch == "":
                ek = self._slots[i]["extra_keys"]
                if ek is not None:
                    parts.append(ek.get("translate", ek.get("score", {}).get("name", "?")
                                        if isinstance(ek.get("score"), dict) else "?"))
                # else: empty string, skip
            else:
                parts.append(ch)
        return "".join(parts)

    @override
    def to_colored_text(self) -> str:
        parts: List[str] = []
        cur_color: Optional[RColor] = None
        cur_styles: Set[RStyle] = set()

        i = 0
        while i < len(self._text):
            slot = self._slots[i]
            if slot["color"] != cur_color or slot["styles"] != cur_styles:
                if cur_color is not None or cur_styles:
                    parts.append(Style.RESET_ALL)  # ty:ignore[invalid-argument-type]
                codes: List[str] = []
                color = slot["color"]
                if color is not None:
                    if hasattr(color, "console_code"):
                        codes.append(color.console_code)
                    elif hasattr(color, "to_classic"):
                        classic = color.to_classic()
                        if hasattr(classic, "console_code"):
                            codes.append(classic.console_code)
                for style in slot["styles"]:
                    if hasattr(style, "console_code") and style.console_code:
                        codes.append(style.console_code)
                parts.append("".join(codes))
                cur_color = slot["color"]
                cur_styles = set(slot["styles"])

            run_start = i
            while i < len(self._text) and self._slots[i]["color"] == cur_color and self._slots[i]["styles"] == cur_styles:
                i += 1
            parts.append("".join(self._text[run_start:i]))

        if cur_color is not None or cur_styles:
            parts.append(Style.RESET_ALL)  # ty:ignore[invalid-argument-type]
        return "".join(parts)

    @override
    def to_legacy_text(self) -> str:
        parts: List[str] = []
        cur_color: Optional[RColor] = None
        cur_styles: Set[RStyle] = set()

        i = 0
        while i < len(self._text):
            slot = self._slots[i]
            if slot["color"] != cur_color or slot["styles"] != cur_styles:
                if (cur_color is not None or cur_styles) and slot["color"] is None and not slot["styles"]:
                    parts.append(RColor.reset.mc_code)
                color = slot["color"]
                if color is not None:
                    if hasattr(color, "mc_code"):
                        parts.append(color.mc_code)
                    elif hasattr(color, "to_classic"):
                        classic = color.to_classic()
                        if hasattr(classic, "mc_code"):
                            parts.append(classic.mc_code)
                for style in slot["styles"]:
                    if hasattr(style, "mc_code"):
                        parts.append(style.mc_code)
                cur_color = slot["color"]
                cur_styles = set(slot["styles"])

            run_start = i
            while i < len(self._text) and self._slots[i]["color"] == cur_color and self._slots[i]["styles"] == cur_styles:
                i += 1
            parts.append("".join(self._text[run_start:i]))

        if cur_color is not None or cur_styles:
            parts.append(RColor.reset.mc_code)
        return "".join(parts)

    @override
    def copy(self) -> Self:
        result = RComplexText.__new__(RComplexText)
        result._text = list(self._text)
        result._slots = [_copy_slot(s) for s in self._slots]
        return result

    @override
    def set_color(self, color: RColor) -> Self:
        for slot in self._iter_slots():
            slot["color"] = color
        return self

    @override
    def set_styles(self, styles: Union[RStyle, Iterable[RStyle]]) -> Self:
        if isinstance(styles, RStyle):
            resolved = {styles}
        elif isinstance(styles, Iterable):
            resolved = set(styles)
        else:
            raise TypeError(f"Unsupported style type {type(styles)}")
        for slot in self._iter_slots():
            slot["styles"] = set(resolved)
        return self

    @override
    def set_hover_event(self, hover_event: RHoverEvent) -> Self:
        for slot in self._iter_slots():
            slot["hover_event"] = hover_event
        return self

    @override
    def _set_click_event_direct(self, click_event: RClickEvent) -> Self:
        for slot in self._iter_slots():
            slot["click_event"] = click_event
        return self

    # ── dunders ─────────────────────────────────────────────────────

    def __str__(self) -> str:
        return self._plain_str()

    def __repr__(self) -> str:
        return f"RComplexText({self._plain_str()!r})"

    def __len__(self) -> int:
        return len(self._text)

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RComplexText):
            return self._text == other._text and self._slots == other._slots
        return NotImplemented

    def __hash__(self) -> int:
        return id(self)

    def __contains__(self, item: str) -> bool:
        return item in self._plain_str()

    def __add__(self, other) -> Union["RComplexText", RTextList]:
        if isinstance(other, RComplexText):
            result = self.copy()
            result._text.extend(other._text)
            result._slots.extend(_copy_slot(s) for s in other._slots)
            return result
        if isinstance(other, str):
            result = self.copy()
            result._text.extend(other)
            result._slots.extend(_new_slot() for _ in other)
            return result
        if isinstance(other, RTextBase):
            return RTextList(self, other)
        return NotImplemented

    def __radd__(self, other) -> Union["RComplexText", RTextList]:
        if isinstance(other, str):
            result = RComplexText(other)
            result._text.extend(self._text)
            result._slots.extend(_copy_slot(s) for s in self._slots)
            return result
        if isinstance(other, RTextBase):
            return RTextList(other, self)
        return NotImplemented

    def replace(self, old: str, new: str, *, cross_format: bool = False) -> Self:
        """Replace occurrences of *old* with *new* in the text, preserving per-character metadata.

        Translatable placeholders (empty-string slots) do not participate in matching.

        :param old: The substring to search for (plain `str` only).
        :param new: The replacement substring (plain `str` only).
        :param cross_format: If `False` (default), only replace when **all** characters
            in the matched range share identical metadata; replacement characters inherit
            that metadata.  If `True`, replace even when metadata is inconsistent;
            replacement characters inherit the **first** matched character's metadata.
            Ignored when `len(old) == 1`.
        :return: *self* (modifies in-place).
        """
        if not isinstance(old, str) or not isinstance(new, str):
            raise TypeError("replace() only accepts str arguments")

        if old == "":
            self._replace_empty(new)
            return self

        plain = self._plain_str()
        if old not in plain:
            return self

        i = 0
        result_text: List[str] = []
        result_slots: List[dict] = []
        plain_pos = 0

        while i < len(self._text):
            if self._text[i] == "":
                result_text.append(self._text[i])
                result_slots.append(_copy_slot(self._slots[i]))
                i += 1
                continue

            # Check for match starting at plain position plain_pos
            if plain.startswith(old, plain_pos):
                # Map plain match range back to _text indices
                match_start_idx = i
                match_end_idx = i
                p = plain_pos
                while p < plain_pos + len(old):
                    if match_end_idx >= len(self._text):
                        break
                    if self._text[match_end_idx] == "":
                        match_end_idx += 1  # skip translatables
                        continue
                    p += 1
                    match_end_idx += 1

                match_slots = self._slots[match_start_idx:match_end_idx]
                same_meta = all(
                    _slot_fingerprint(s, RTextJsonFormat.default())
                    == _slot_fingerprint(match_slots[0], RTextJsonFormat.default())
                    for s in match_slots[1:]
                ) if len(match_slots) > 1 else True

                if same_meta or len(old) == 1 or cross_format:
                    # Replace
                    template = _copy_slot(self._slots[match_start_idx])
                    for ch in new:
                        result_text.append(ch)
                        result_slots.append(_copy_slot(template))
                    i = match_end_idx
                    plain_pos += len(old)
                    continue

            # Keep current character
            result_text.append(self._text[i])
            result_slots.append(_copy_slot(self._slots[i]))
            i += 1
            plain_pos += 1

        self._text = result_text
        self._slots = result_slots
        return self

    def _replace_empty(self, new: str) -> None:
        """Insert *new* at every character boundary (empty-string match)."""
        new_items = list(new)
        out_text: List[str] = []
        out_slots: List[dict] = []

        for i, ch in enumerate(self._text):
            # Insert before each real character
            template = _copy_slot(self._slots[i])
            out_text.extend(new_items)
            out_slots.extend(_copy_slot(template) for _ in new_items)
            # The character itself
            out_text.append(ch)
            out_slots.append(_copy_slot(self._slots[i]))

        # Insert after the last character
        if self._text:
            template = _copy_slot(self._slots[-1])
            out_text.extend(new_items)
            out_slots.extend(_copy_slot(template) for _ in new_items)

        self._text = out_text
        self._slots = out_slots
    # ── split / rsplit ──────────────────────────────────────────────

    def split(self, sep: Optional[str] = None, maxsplit: int = -1) -> List["RComplexText"]:
        """Split the text literal and distribute per-character metadata."""
        joined = self._plain_str()
        parts_str = joined.split(sep, maxsplit)
        return self._split_parts(parts_str, sep, joined)

    def rsplit(self, sep: Optional[str] = None, maxsplit: int = -1) -> List["RComplexText"]:
        """Split from the right and distribute per-character metadata."""
        joined = self._plain_str()
        parts_str = joined.rsplit(sep, maxsplit)
        return self._split_parts(parts_str, sep, joined)

    def _split_parts(
        self, parts: List[str], sep: Optional[str], joined: str,
    ) -> List["RComplexText"]:
        """Map *parts* (from ``str.split`` / ``rsplit``) back to RComplexText chunks."""
        result: List["RComplexText"] = []
        search_pos = 0
        sep_len = len(sep) if sep is not None else 0
        for part in parts:
            idx = joined.find(part, search_pos)
            if idx == -1:
                chunk = RComplexText(part)
            else:
                start = idx
                end = idx + len(part)
                i_start, i_end = self._plain_range_to_indices(start, end)

                chunk = RComplexText.__new__(RComplexText)
                chunk._text = list(self._text[i_start:i_end])
                chunk._slots = [_copy_slot(self._slots[i]) for i in range(i_start, i_end)]
                search_pos = end + sep_len
            result.append(chunk)
        return result

    def _plain_range_to_indices(self, start: int, end: int) -> Tuple[int, int]:
        """Map a range in the plain-text (joined) space back to ``_text`` indices."""
        i_start: Optional[int] = None
        plain_pos = 0
        for i, ch in enumerate(self._text):
            if plain_pos == start:
                i_start = i
            if plain_pos == end:
                return (i_start if i_start is not None else i, i)
            plain_pos += len(ch)
        return (i_start if i_start is not None else len(self._text), len(self._text))

    # ── § format code conversion ────────────────────────────────────

    def strip_format_codes(self) -> Self:
        """Convert ``§`` formatting codes to JSON properties and remove them.

        Modifies this instance in-place and returns *self*.
        """
        self._text, self._slots = _parse_format_codes(self._text, self._slots)
        # Recursively strip § codes in hover event texts
        for slot in self._slots:
            he = slot.get("hover_event")
            if isinstance(he, RHoverText):
                if isinstance(he.text, RComplexText):
                    he.text.strip_format_codes()
                else:
                    # Hover text is a raw RText with possible § codes — convert and strip
                    inner = RComplexText.from_json_object(he.text.to_json_object())
                    inner.strip_format_codes()
                    slot["hover_event"] = RHoverText(text=inner)
        return self

    # ── factory class methods ───────────────────────────────────────
    @classmethod
    def from_json_object(cls, data, **kwargs) -> "RComplexText":
        """Create an :class:`RComplexText` from a Minecraft raw JSON object."""
        json_format = kwargs.get("json_format")
        result = cls.__new__(cls)
        text_parts: list = []
        slot_parts: list = []
        _flatten_json(data, text_parts, slot_parts, _new_slot(), json_format)
        result._text = text_parts
        result._slots = slot_parts
        return result

    @classmethod
    def from_rtext(cls, rtext: RTextBase, **kwargs) -> "RComplexText":
        """Create an :class:`RComplexText` from an existing RText / RTextList."""
        return cls.from_json_object(rtext.to_json_object(**kwargs), **kwargs)
