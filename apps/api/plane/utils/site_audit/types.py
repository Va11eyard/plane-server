# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from dataclasses import dataclass, field
from typing import Any

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_CRITICAL = "critical"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

SSL_WARN_DAYS = 30
SSL_CRITICAL_DAYS = 7
RENEWAL_WARN_DAYS = 14

HTTP_TIMEOUT = 15


@dataclass
class ProbeResult:
    check_type: str
    check_key: str = ""
    status: str = STATUS_OK
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


def worst_status(*statuses: str) -> str:
    order = {STATUS_OK: 0, STATUS_SKIPPED: 1, STATUS_WARN: 2, STATUS_ERROR: 3, STATUS_CRITICAL: 4}
    return max(statuses, key=lambda s: order.get(s, 0)) if statuses else STATUS_OK
