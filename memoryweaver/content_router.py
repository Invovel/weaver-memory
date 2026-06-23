"""Rule-based content router for ContextCapsule creation."""

from __future__ import annotations

import json
import re
from typing import Any

from memoryweaver.context_schema import ContentType, ContextCapsule, RawSpan
from memoryweaver.store import tokenize_text


class ContentRouter:
    """Create reversible ContextCapsules using deterministic rules."""

    compression_method = "rule_v1"

    def compress(self, raw_span: RawSpan) -> ContextCapsule:
        if raw_span.content_type == ContentType.TERMINAL_LOG:
            summary, tags = self._compress_terminal_log(raw_span)
        elif raw_span.content_type == ContentType.TOOL_JSON:
            summary, tags = self._compress_tool_json(raw_span)
        elif raw_span.content_type == ContentType.CONVERSATION_TURN:
            summary, tags = self._compress_conversation_turn(raw_span)
        elif raw_span.content_type == ContentType.CODE_PATCH:
            summary, tags = self._compress_code_patch(raw_span)
        elif raw_span.content_type == ContentType.TRACE_RECORD:
            summary, tags = self._compress_trace_record(raw_span)
        else:
            summary, tags = self._compress_text(raw_span)
        ratio = _compression_ratio(raw_span.content, summary)
        return ContextCapsule(
            raw_ref_id=raw_span.id,
            content_type=raw_span.content_type,
            summary=summary,
            tags=sorted(set(tags)),
            timestamp=raw_span.timestamp,
            source=raw_span.source,
            compression_method=self.compression_method,
            compression_ratio=ratio,
            reversible=True,
            metadata={
                "raw_source": raw_span.source.value,
                "raw_timestamp": raw_span.timestamp,
                "raw_content_hash": raw_span.content_hash,
            },
        )

    def _compress_terminal_log(self, raw_span: RawSpan) -> tuple[str, list[str]]:
        metadata = raw_span.metadata
        command = str(metadata.get("command", _first_command(raw_span.content)))
        exit_code = metadata.get("exit_code", _extract_exit_code(raw_span.content))
        stderr_lines = _interesting_lines(raw_span.content)
        stderr_head = " | ".join(stderr_lines[:2])
        stderr_tail = " | ".join(stderr_lines[-2:])
        summary = (
            f"[{raw_span.timestamp}] command={command} -> exit={exit_code}. "
            f"stderr_head={stderr_head}; stderr_tail={stderr_tail}"
        )
        tags = _tags_from("terminal", "terminal_log", command, stderr_head)
        if exit_code not in ("", None, 0, "0"):
            tags.append("error")
        return summary, tags

    def _compress_tool_json(self, raw_span: RawSpan) -> tuple[str, list[str]]:
        try:
            parsed = json.loads(raw_span.content)
        except json.JSONDecodeError:
            parsed = {}
        kept = _keep_json_keys(parsed)
        summary = json.dumps(kept, ensure_ascii=False, sort_keys=True)
        tags = _tags_from("tool_json", summary, str(raw_span.metadata))
        status = str(kept.get("status", ""))
        if status:
            tags.append(status.lower())
        return summary, tags

    def _compress_conversation_turn(self, raw_span: RawSpan) -> tuple[str, list[str]]:
        metadata = raw_span.metadata
        speaker = str(metadata.get("speaker", raw_span.source.value))
        intent = str(metadata.get("intent", _infer_intent(raw_span.content)))
        correction = "correction" if _contains_correction(raw_span.content) else ""
        decision = str(metadata.get("decision", ""))
        summary = (
            f"[{raw_span.timestamp}] speaker={speaker} | intent={intent} "
            f"| correction={correction} | decision={decision} | text={_shorten(raw_span.content)}"
        )
        tags = _tags_from("conversation_turn", speaker, intent, decision, raw_span.content)
        if correction:
            tags.append("correction")
        return summary, tags

    def _compress_code_patch(self, raw_span: RawSpan) -> tuple[str, list[str]]:
        metadata = raw_span.metadata
        file_path = str(metadata.get("file_path", _extract_file_path(raw_span.content)))
        changed_lines = str(metadata.get("changed_lines", _count_changed_lines(raw_span.content)))
        symbols = metadata.get("symbols", _extract_symbols(raw_span.content))
        if isinstance(symbols, str):
            symbols_text = symbols
        else:
            symbols_text = ",".join(str(symbol) for symbol in symbols)
        summary = (
            f"[{raw_span.timestamp}] file={file_path} symbols={symbols_text} "
            f"changed_lines={changed_lines}"
        )
        tags = _tags_from("code_patch", file_path, symbols_text)
        return summary, tags

    def _compress_trace_record(self, raw_span: RawSpan) -> tuple[str, list[str]]:
        try:
            parsed = json.loads(raw_span.content)
        except json.JSONDecodeError:
            parsed = {}
        marker = str(parsed.get("activated_marker", parsed.get("marker", "")))
        route = str(parsed.get("route", parsed.get("recommended_route", "")))
        required = parsed.get("required_evidence", parsed.get("required_evidence_checks", []))
        suppressed = parsed.get("suppressed_actions", parsed.get("suppressed_known_bad_paths", []))
        summary = (
            f"[{raw_span.timestamp}] marker={marker} route={route} "
            f"required={required} suppressed={suppressed}"
        )
        tags = _tags_from("trace_record", summary)
        return summary, tags

    def _compress_text(self, raw_span: RawSpan) -> tuple[str, list[str]]:
        summary = f"[{raw_span.timestamp}] text={_shorten(raw_span.content, limit=240)}"
        return summary, _tags_from("text", summary)


def _compression_ratio(original: str, compressed: str) -> float:
    if not original:
        return 1.0
    return round(len(compressed.encode("utf-8")) / len(original.encode("utf-8")), 4)


def _tags_from(*values: str) -> list[str]:
    tags: set[str] = set()
    for value in values:
        for identifier in re.findall(r"\b[A-Za-z][A-Za-z0-9]*\b", str(value)):
            for part in _split_camel_case(identifier):
                tags.add(part.lower())
        for token in tokenize_text(str(value)):
            tags.add(token)
            for part in re.split(r"[^a-z0-9]+", token.lower()):
                if part:
                    tags.add(part)
            for part in _split_camel_case(token):
                tags.add(part.lower())
    return sorted(tags)


def _split_camel_case(value: str) -> list[str]:
    if not (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value)):
        return []
    return re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", value)


def _first_command(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("$"):
            return stripped.lstrip("$").strip()
    return ""


def _extract_exit_code(text: str) -> str:
    match = re.search(r"exit(?:_code)?[=:]\s*(-?\d+)", text, re.IGNORECASE)
    return match.group(1) if match else ""


def _interesting_lines(text: str) -> list[str]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if re.search(r"error|failed|exception|traceback|stderr|warning", line, re.I)
    ]
    if not lines:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines


def _keep_json_keys(value: Any) -> dict[str, Any]:
    allowed = {"status", "error", "errors", "id", "key", "code", "message", "path", "timestamp"}
    if isinstance(value, dict):
        kept: dict[str, Any] = {}
        for key, item in value.items():
            if key in allowed:
                kept[key] = item
            elif isinstance(item, dict):
                nested = _keep_json_keys(item)
                if nested:
                    kept[key] = nested
        return kept
    return {}


def _infer_intent(text: str) -> str:
    lowered = text.lower()
    if _contains_correction(text):
        return "correction"
    if "?" in text or "should" in lowered:
        return "question"
    return "observation"


def _contains_correction(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["do not", "don't", "wrong", "correction", "不要", "不应该"])


def _shorten(text: str, limit: int = 160) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _extract_file_path(text: str) -> str:
    match = re.search(r"^[+ -]{0,3}(?:file|path)[:=]\s*(.+)$", text, re.I | re.M)
    return match.group(1).strip() if match else ""


def _count_changed_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))


def _extract_symbols(text: str) -> list[str]:
    return re.findall(r"\b(?:def|class|function|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)", text)
