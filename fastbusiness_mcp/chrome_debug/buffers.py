"""Ring buffer quản lý log console và network errors per tab."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Any, Deque, Dict, List


@dataclass
class ConsoleMessage:
    type: str
    text: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "text": self.text,
            "ts": round(self.ts, 2),
        }


@dataclass
class NetworkError:
    url: str
    method: str
    status: int
    request_payload: str = ""
    response_body: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "status": self.status,
            "request_payload": self.request_payload,
            "response_body": self.response_body,
            "ts": round(self.ts, 2),
        }


class TabBuffers:
    """Buffer lưu trữ nhật ký console và lỗi network cho 1 page."""

    def __init__(self, max_console_lines: int = 200, max_network_items: int = 50):
        self.console_buffer: Deque[ConsoleMessage] = deque(maxlen=max_console_lines)
        self.network_buffer: Deque[NetworkError] = deque(maxlen=max_network_items)

    def add_console(self, msg_type: str, text: str) -> None:
        self.console_buffer.append(ConsoleMessage(type=msg_type, text=text))

    def add_network_error(
        self,
        url: str,
        method: str,
        status: int,
        request_payload: str = "",
        response_body: str = "",
    ) -> None:
        self.network_buffer.append(
            NetworkError(
                url=url,
                method=method,
                status=status,
                request_payload=request_payload,
                response_body=response_body,
            )
        )

    def get_console_errors(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.console_buffer]

    def get_network_errors(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.network_buffer]

    def clear(self) -> None:
        self.console_buffer.clear()
        self.network_buffer.clear()
