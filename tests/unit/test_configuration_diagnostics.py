"""T6-B configuration diagnostics must be useful without exposing secrets."""

from pathlib import Path

from researchmind.maintenance import diagnose_configuration


def test_diagnostics_report_ready_local_configuration_without_secret(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()

    report = diagnose_configuration(
        env={
            "LLM_BASE_URL": "https://example.test/v1",
            "LLM_API_KEY": "diagnostic-secret-value",
            "LLM_MODEL": "test-model",
            "OBSIDIAN_VAULT_PATH": str(vault),
            "OBSIDIAN_SUBDIRECTORY": "ResearchMind",
        }
    )

    statuses = {check.code: check.status for check in report.checks}
    assert statuses["python_runtime"] == "ok"
    assert statuses["configuration"] == "ok"
    assert statuses["llm_endpoint"] == "ok"
    assert statuses["llm_credentials"] == "ok"
    assert statuses["library"] == "warning"
    assert statuses["zotero_local_api"] == "warning"
    assert statuses["vault"] == "ok"
    assert report.has_errors is False
    assert "diagnostic-secret-value" not in repr(report)
    assert not (vault / "ResearchMind").exists()


def test_diagnostics_treat_unconfigured_optional_capabilities_as_warnings() -> None:
    report = diagnose_configuration(env={})

    statuses = {check.code: check.status for check in report.checks}
    assert statuses["llm_credentials"] == "warning"
    assert statuses["library"] == "warning"
    assert statuses["zotero_local_api"] == "warning"
    assert statuses["vault"] == "warning"
    assert report.has_errors is False


def test_diagnostics_validate_library_without_creating_it(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "new-library"

    report = diagnose_configuration(
        env={"RESEARCHMIND_DATA_DIR": str(data_dir)}
    )

    statuses = {check.code: check.status for check in report.checks}
    assert statuses["library"] == "ok"
    assert data_dir.exists() is False
    assert str(tmp_path) not in repr(report)


def test_diagnostics_reports_enabled_zotero_without_network_probe() -> None:
    report = diagnose_configuration(
        env={"ZOTERO_LOCAL_API_ENABLED": "true"}
    )

    check = next(
        item for item in report.checks if item.code == "zotero_local_api"
    )
    assert check.status == "ok"
    assert "诊断不会联网" in check.message


def test_diagnostics_convert_invalid_configuration_to_safe_error() -> None:
    report = diagnose_configuration(
        env={
            "CONTEXT_TOKEN_BUDGET": "invalid",
            "LLM_API_KEY": "must-not-leak",
        }
    )

    assert report.has_errors is True
    assert len(report.checks) == 1
    assert report.checks[0].code == "configuration"
    assert report.checks[0].status == "error"
    assert "CONTEXT_TOKEN_BUDGET" in report.checks[0].message
    assert "must-not-leak" not in repr(report)


def test_diagnostics_reject_invalid_endpoint_and_vault(
    tmp_path: Path,
) -> None:
    report = diagnose_configuration(
        env={
            "LLM_BASE_URL": "file:///private/config",
            "LLM_API_KEY": "secret",
            "LLM_MODEL": "model",
            "OBSIDIAN_VAULT_PATH": str(tmp_path / "missing"),
        }
    )

    statuses = {check.code: check.status for check in report.checks}
    assert statuses["llm_endpoint"] == "error"
    assert statuses["vault"] == "error"
    assert report.has_errors is True
    assert str(tmp_path) not in repr(report)
