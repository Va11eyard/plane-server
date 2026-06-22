# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import re
import subprocess
import time

from plane.utils.site_audit.types import (
    ProbeResult,
    STATUS_CRITICAL,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARN,
)

logger = logging.getLogger("plane.site_audit")

SSH_TIMEOUT = 20


def _run_ssh_command(host: str, command: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "StrictHostKeyChecking=accept-new",
            host,
            command,
        ],
        capture_output=True,
        text=True,
        timeout=SSH_TIMEOUT + 5,
    )
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


def probe_ssh_systemd(host: str, unit: str) -> ProbeResult:
    start = time.monotonic()
    if not host:
        return ProbeResult(
            check_type="ssh_systemd",
            check_key=unit,
            status=STATUS_SKIPPED,
            message="SSH host не задан",
        )
    try:
        code, out, err = _run_ssh_command(host, f"systemctl is-active {unit}")
        duration_ms = int((time.monotonic() - start) * 1000)
        state = (out or err).strip().lower()
        if code == 0 and state == "active":
            return ProbeResult(
                check_type="ssh_systemd",
                check_key=unit,
                status=STATUS_OK,
                message=f"{unit}: active",
                details={"unit": unit, "state": state},
                duration_ms=duration_ms,
            )
        if state in ("inactive", "failed", "dead"):
            return ProbeResult(
                check_type="ssh_systemd",
                check_key=unit,
                status=STATUS_CRITICAL,
                message=f"{unit}: {state or 'не active'}",
                details={"unit": unit, "state": state},
                duration_ms=duration_ms,
            )
        return ProbeResult(
            check_type="ssh_systemd",
            check_key=unit,
            status=STATUS_WARN,
            message=f"{unit}: {state or err or 'unknown'}",
            details={"unit": unit, "state": state, "stderr": err},
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning("SSH systemd probe %s@%s: %s", unit, host, e)
        return ProbeResult(
            check_type="ssh_systemd",
            check_key=unit,
            status=STATUS_ERROR,
            message=f"{unit}: SSH ошибка — {e}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )


def probe_ssh_docker(host: str, project_path: str) -> ProbeResult:
    start = time.monotonic()
    if not host or not project_path:
        return ProbeResult(
            check_type="ssh_docker",
            check_key=project_path,
            status=STATUS_SKIPPED,
            message="SSH host или путь не задан",
        )
    try:
        cmd = f"cd {project_path} && docker compose ps --format '{{{{.Name}}}}\\t{{{{.State}}}}\\t{{{{.Status}}}}'"
        code, out, err = _run_ssh_command(host, cmd)
        duration_ms = int((time.monotonic() - start) * 1000)
        if code != 0:
            return ProbeResult(
                check_type="ssh_docker",
                check_key=project_path,
                status=STATUS_ERROR,
                message=f"docker compose ps: {err or out or f'exit {code}'}",
                duration_ms=duration_ms,
            )

        lines = [ln for ln in out.splitlines() if ln.strip()]
        if not lines:
            return ProbeResult(
                check_type="ssh_docker",
                check_key=project_path,
                status=STATUS_WARN,
                message="Нет запущенных контейнеров",
                duration_ms=duration_ms,
            )

        bad: list[str] = []
        containers: list[dict[str, str]] = []
        for line in lines:
            parts = line.split("\t")
            name = parts[0] if parts else line
            state = parts[1].lower() if len(parts) > 1 else ""
            status_text = parts[2] if len(parts) > 2 else ""
            containers.append({"name": name, "state": state, "status": status_text})
            if state not in ("running", "") and "running" not in status_text.lower():
                bad.append(name)
            if re.search(r"unhealthy|exited|dead|restarting", status_text, re.I):
                bad.append(name)

        if bad:
            return ProbeResult(
                check_type="ssh_docker",
                check_key=project_path,
                status=STATUS_CRITICAL,
                message=f"Проблемные контейнеры: {', '.join(sorted(set(bad))[:5])}",
                details={"containers": containers, "bad": bad},
                duration_ms=duration_ms,
            )
        return ProbeResult(
            check_type="ssh_docker",
            check_key=project_path,
            status=STATUS_OK,
            message=f"{len(containers)} контейнер(ов) running",
            details={"containers": containers},
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning("SSH docker probe %s@%s: %s", project_path, host, e)
        return ProbeResult(
            check_type="ssh_docker",
            check_key=project_path,
            status=STATUS_ERROR,
            message=f"Docker SSH: {e}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
