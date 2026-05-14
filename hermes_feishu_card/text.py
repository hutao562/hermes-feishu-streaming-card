from __future__ import annotations

import re

THINK_CONTENT_RE = re.compile(
    r"<think\b[^>]*>.*?</think>|<thinking\b[^>]*>.*?</thinking>",
    re.IGNORECASE | re.DOTALL,
)
THINK_TAG_RE = re.compile(r"</?think\b[^>]*>|</?thinking\b[^>]*>", re.IGNORECASE)
SENTENCE_END_RE = re.compile(r"[。！？!?\.]$")
THINK_START_RE = re.compile(r"<think\b[^>]*>|<thinking\b[^>]*>", re.IGNORECASE)
THINK_END_RE = re.compile(r"</think>|</thinking>", re.IGNORECASE)
THINK_START_PREFIXES = ("<think", "<thinking")
THINK_END_PREFIXES = ("</think", "</thinking")


def normalize_stream_text(text: str) -> str:
    """移除模型 thinking 标签及其内部内容，保留用户可读内容。"""
    text = text or ""
    text = THINK_CONTENT_RE.sub("", text)
    text = THINK_TAG_RE.sub("", text)
    return text


class StreamingTextNormalizer:
    """Filter thinking tags and their content that may be split across streaming chunks."""

    def __init__(self) -> None:
        self._pending = ""
        self._in_think = False

    def feed(self, delta: str) -> str:
        text = self._pending + (delta or "")
        self._pending = ""
        result = []

        while text:
            if self._in_think:
                match = THINK_END_RE.search(text)
                if not match:
                    _safe, self._pending = self._split_safe_text(
                        text, THINK_END_PREFIXES
                    )
                    break

                text = text[match.end() :]
                self._in_think = False
            else:
                match = THINK_START_RE.search(text)
                if not match:
                    safe_text, self._pending = self._split_safe_text(
                        text, THINK_START_PREFIXES
                    )
                    result.append(safe_text)
                    break

                result.append(text[: match.start()])
                text = text[match.end() :]
                self._in_think = True

        return "".join(result)

    @staticmethod
    def _split_safe_text(text: str, tags: tuple[str, ...]) -> tuple[str, str]:
        lower_text = text.lower()
        pending_len = 0

        for tag in tags:
            for prefix_len in range(1, len(tag)):
                if lower_text.endswith(tag[:prefix_len]):
                    pending_len = max(pending_len, prefix_len)

        if not pending_len:
            return text, ""
        return text[:-pending_len], text[-pending_len:]


def should_flush_text(
    buffer: str,
    *,
    elapsed_ms: int,
    max_wait_ms: int,
    max_chars: int,
    force: bool = False,
) -> bool:
    if force:
        return True
    if not buffer:
        return False
    if len(buffer) >= max_chars:
        return True
    if elapsed_ms >= max_wait_ms:
        return True
    if buffer.endswith(("\n", "\r\n")):
        return True
    return bool(SENTENCE_END_RE.search(buffer.rstrip()))


def count_markdown_tables(text: str) -> int:
    """统计 Markdown 文本中的表格数量（以 | --- | 分隔行为标志）。"""
    return len(re.findall(r'^\|[-: ]+\|', text, re.MULTILINE))


MAX_CARD_TABLES = 5
