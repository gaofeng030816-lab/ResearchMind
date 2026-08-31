"""Local T6-B diagnostics and safe Markdown maintenance commands."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from researchmind import __version__
from researchmind.config import ConfigError, Settings, load_settings
from researchmind.integration.obsidian import (
    ObsidianError,
    VaultConfigurationError,
    create_markdown_backup,
    restore_markdown_backup,
    validate_vault_destination,
)
from researchmind.models import ConfigurationCheck, ConfigurationReport


def diagnose_configuration(
    env_file: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    secrets: Mapping[str, object] | None = None,
) -> ConfigurationReport:
    """Load and inspect local settings without network calls or secret output."""

    try:
        settings = load_settings(
            env_file,
            env=env,
            secrets=secrets,
        )
    except ConfigError as exc:
        return ConfigurationReport(
            checks=(
                ConfigurationCheck(
                    code="configuration",
                    label="配置格式",
                    status="error",
                    message=str(exc),
                ),
            )
        )
    return inspect_settings(settings)


def inspect_settings(settings: Settings) -> ConfigurationReport:
    """Inspect already loaded settings without mutating local data."""

    checks = [
        _python_runtime_check(),
        ConfigurationCheck(
            code="configuration",
            label="配置格式",
            status="ok",
            message="配置值已成功解析，敏感值不会显示。",
        ),
        _llm_endpoint_check(settings),
        _llm_credentials_check(settings),
        _vault_check(settings),
        ConfigurationCheck(
            code="resource_limits",
            label="资源限制",
            status="ok",
            message=(
                "上下文、历史和 PDF 大小限制均为有效正整数。"
            ),
        ),
    ]
    return ConfigurationReport(checks=tuple(checks))


def main(argv: Sequence[str] | None = None) -> int:
    """Run one explicit local maintenance command."""

    _configure_utf8_stream(sys.stdout)
    _configure_utf8_stream(sys.stderr)
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "diagnose":
            report = diagnose_configuration(args.env_file)
            _print_report(report, as_json=args.json)
            return 1 if report.has_errors else 0
        if args.command == "backup":
            settings = load_settings(args.env_file)
            if settings.obsidian_vault_path is None:
                raise VaultConfigurationError(
                    "OBSIDIAN_VAULT_PATH is not configured."
                )
            result = create_markdown_backup(
                vault_path=settings.obsidian_vault_path,
                subdirectory=settings.obsidian_subdirectory,
                archive_path=args.output,
            )
            print(
                f"Created backup with {result.note_count} Markdown note(s): "
                f"{result.archive_path}"
            )
            return 0
        if args.command == "restore":
            result = restore_markdown_backup(
                archive_path=args.archive,
                vault_path=args.vault,
                subdirectory=args.subdirectory,
            )
            print(
                f"Restored {result.note_count} Markdown note(s) into: "
                f"{result.output_directory}"
            )
            return 0
    except (ConfigError, ObsidianError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    parser.error("A maintenance command is required.")
    return 2


def _python_runtime_check() -> ConfigurationCheck:
    supported = sys.version_info >= (3, 12)
    return ConfigurationCheck(
        code="python_runtime",
        label="Python",
        status="ok" if supported else "error",
        message=(
            f"Python {sys.version_info.major}.{sys.version_info.minor} "
            + ("满足 3.12+ 要求。" if supported else "低于要求的 3.12。")
        ),
    )


def _llm_endpoint_check(settings: Settings) -> ConfigurationCheck:
    parsed = urlsplit(settings.llm_base_url)
    valid = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    return ConfigurationCheck(
        code="llm_endpoint",
        label="LLM 端点",
        status="ok" if valid else "error",
        message=(
            "端点格式有效；本检查不会联网。"
            if valid
            else "LLM_BASE_URL 必须是有效的 http 或 https 地址。"
        ),
    )


def _llm_credentials_check(settings: Settings) -> ConfigurationCheck:
    configured = bool(settings.llm_api_key and settings.llm_model)
    return ConfigurationCheck(
        code="llm_credentials",
        label="LLM 凭据",
        status="ok" if configured else "warning",
        message=(
            "API Key 和模型均已配置；凭据值不会显示。"
            if configured
            else "未完整配置 API Key 和模型；本地阅读仍可使用，联网 AI 不可用。"
        ),
    )


def _vault_check(settings: Settings) -> ConfigurationCheck:
    if settings.obsidian_vault_path is None:
        return ConfigurationCheck(
            code="vault",
            label="Obsidian Vault",
            status="warning",
            message="Vault 未配置；阅读可用，但不能保存或备份知识笔记。",
        )
    try:
        validate_vault_destination(
            settings.obsidian_vault_path,
            settings.obsidian_subdirectory,
        )
    except VaultConfigurationError as exc:
        return ConfigurationCheck(
            code="vault",
            label="Obsidian Vault",
            status="error",
            message=str(exc),
        )
    return ConfigurationCheck(
        code="vault",
        label="Obsidian Vault",
        status="ok",
        message="Vault 根目录和 ResearchMind 子目录配置有效。",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m researchmind.maintenance",
        description="ResearchMind local diagnostics and Markdown backup tools.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ResearchMind {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    diagnose = subparsers.add_parser(
        "diagnose",
        help="Inspect local configuration without network calls.",
    )
    diagnose.add_argument("--env-file", type=Path)
    diagnose.add_argument("--json", action="store_true")
    backup = subparsers.add_parser(
        "backup",
        help="Create a verified ZIP of ResearchMind Markdown notes.",
    )
    backup.add_argument("--env-file", type=Path)
    backup.add_argument("--output", type=Path, required=True)
    restore = subparsers.add_parser(
        "restore",
        help="Restore a verified ZIP into a new Vault subdirectory.",
    )
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--vault", type=Path, required=True)
    restore.add_argument("--subdirectory", required=True)
    return parser


def _print_report(
    report: ConfigurationReport,
    *,
    as_json: bool,
) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "has_errors": report.has_errors,
                    "checks": [asdict(check) for check in report.checks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    for check in report.checks:
        print(
            f"[{check.status.upper()}] {check.label}: {check.message}"
        )


def _configure_utf8_stream(stream: object) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
