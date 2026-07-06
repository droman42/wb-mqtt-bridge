"""GitHub report sink (problem_reports_bridge.md B-7/B-8): files one report as an
issue + a bundle commit in the private ``wb-user-reports`` repo, per the shared §5
envelope. Owns the offline spool — a failed delivery lands in ``data/reports/``
and is retried at startup + hourly; the port contract is "never lose a report"."""

import json
import logging
import os
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Optional

import aiohttp

from wb_mqtt_bridge.domain.ports import ReportSinkPort
from wb_mqtt_bridge.domain.reports.models import ReportFiling, ReportFilingResult

logger = logging.getLogger(__name__)

_API = "https://api.github.com"


class GitHubReportSink(ReportSinkPort):
    def __init__(self, repo: str, token_env: str, spool_dir: Path):
        self._repo = repo
        self._token_env = token_env
        self._spool_dir = spool_dir

    # --- delivery ---------------------------------------------------------------

    def _headers(self) -> dict:
        token = os.environ.get(self._token_env, "")
        if not token:
            raise RuntimeError(f"reports token env var {self._token_env} is not set")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _deliver(self, filing: ReportFiling) -> str:
        headers = self._headers()
        bundle_path = f"reports/{filing.report_id}/{filing.bundle_name}"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.put(
                f"{_API}/repos/{self._repo}/contents/{bundle_path}",
                json={
                    "message": f"bundle for {filing.report_id}",
                    "content": b64encode(filing.bundle_bytes).decode("ascii"),
                },
            ) as resp:
                if resp.status not in (200, 201):
                    raise RuntimeError(f"bundle commit failed: HTTP {resp.status} {await resp.text()}")
            async with session.post(
                f"{_API}/repos/{self._repo}/issues",
                json={
                    "title": filing.title,
                    "body": filing.body + f"\n\n[bundle](../blob/main/{bundle_path})",
                    "labels": filing.labels,
                },
            ) as resp:
                if resp.status != 201:
                    raise RuntimeError(f"issue creation failed: HTTP {resp.status} {await resp.text()}")
                data = await resp.json()
                return str(data.get("html_url", ""))

    # --- port -------------------------------------------------------------------

    async def file_report(self, filing: ReportFiling) -> ReportFilingResult:
        try:
            url = await self._deliver(filing)
            return ReportFilingResult(report_id=filing.report_id, filed=True, spooled=False, url=url)
        except Exception as e:  # noqa: BLE001 - delivery failure is the spool's job, never the caller's
            logger.warning("report %s delivery failed (%s) — spooling", filing.report_id, e)
            self._spool(filing)
            return ReportFilingResult(report_id=filing.report_id, filed=False, spooled=True)

    async def retry_spooled(self) -> int:
        delivered = 0
        if not self._spool_dir.exists():
            return 0
        for path in sorted(self._spool_dir.glob("*.json")):
            filing = self._load_spooled(path)
            if filing is None:
                continue
            try:
                await self._deliver(filing)
            except Exception as e:  # noqa: BLE001
                logger.info("spooled report %s still undeliverable: %s", filing.report_id, e)
                continue
            path.unlink(missing_ok=True)
            delivered += 1
            logger.info("spooled report %s delivered", filing.report_id)
        return delivered

    # --- spool (B-7) --------------------------------------------------------------

    def _spool(self, filing: ReportFiling) -> None:
        try:
            self._spool_dir.mkdir(parents=True, exist_ok=True)
            (self._spool_dir / f"{filing.report_id}.json").write_text(json.dumps({
                "report_id": filing.report_id,
                "title": filing.title,
                "body": filing.body,
                "labels": filing.labels,
                "bundle_name": filing.bundle_name,
                "bundle_b64": b64encode(filing.bundle_bytes).decode("ascii"),
            }), encoding="utf-8")
        except Exception:  # noqa: BLE001 - the spool is best-effort; log loudly and move on
            logger.exception("failed to spool report %s", filing.report_id)

    @staticmethod
    def _load_spooled(path: Path) -> Optional[ReportFiling]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReportFiling(
                report_id=data["report_id"],
                title=data["title"],
                body=data["body"],
                labels=list(data["labels"]),
                bundle_name=data["bundle_name"],
                bundle_bytes=b64decode(data["bundle_b64"]),
            )
        except Exception:  # noqa: BLE001
            logger.exception("unreadable spooled report %s (leaving in place)", path.name)
            return None
