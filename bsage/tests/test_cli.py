"""Tests for bsage.cli — Click CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bsage.cli import main


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestRunCommand:
    """Test `bsage run` command."""

    @patch("bsage.cli.uvicorn")
    @patch("bsage.cli.get_settings")
    def test_run_starts_server(self, mock_settings, mock_uvicorn, runner) -> None:
        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        settings.log_level = "info"
        mock_settings.return_value = settings

        result = runner.invoke(main, ["run"])
        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(
            "bsage.gateway.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=8000,
            log_level="info",
        )


class TestInitCommand:
    """Test `bsage init` command."""

    def test_init_creates_vault_dirs(self, runner, tmp_path) -> None:
        with patch("bsage.cli.get_settings") as mock_settings:
            settings = MagicMock()
            settings.vault_path = tmp_path / "vault"
            mock_settings.return_value = settings
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "Vault initialized" in result.output
            assert (tmp_path / "vault" / "seeds").is_dir()
            assert (tmp_path / "vault" / "garden").is_dir()
            assert (tmp_path / "vault" / "actions").is_dir()


class TestSkillsCommand:
    """Test `bsage skills` command."""

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_skills_lists_all(self, mock_settings, mock_httpx, runner) -> None:
        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "name": "garden-writer",
                "category": "process",
                "is_dangerous": False,
                "description": "Write notes",
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = runner.invoke(main, ["skills"])
        assert result.exit_code == 0
        assert "garden-writer" in result.output

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_skills_empty(self, mock_settings, mock_httpx, runner) -> None:
        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = runner.invoke(main, ["skills"])
        assert result.exit_code == 0
        assert "No skills loaded" in result.output

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_skills_connection_error(self, mock_settings, mock_httpx, runner) -> None:
        import httpx

        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_httpx.get.side_effect = httpx.ConnectError("refused")
        mock_httpx.ConnectError = httpx.ConnectError

        result = runner.invoke(main, ["skills"])
        assert result.exit_code == 1
        assert "Cannot connect" in result.output


class TestRunSkillCommand:
    """Test `bsage run-skill` command."""

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_run_skill_success(self, mock_settings, mock_httpx, runner) -> None:
        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_response = MagicMock()
        mock_response.json.return_value = {"skill": "garden-writer", "results": [{}]}
        mock_response.raise_for_status = MagicMock()
        mock_httpx.post.return_value = mock_response
        mock_httpx.ConnectError = Exception
        mock_httpx.HTTPStatusError = Exception

        result = runner.invoke(main, ["run-skill", "garden-writer"])
        assert result.exit_code == 0
        assert "executed successfully" in result.output

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_run_skill_connection_error(self, mock_settings, mock_httpx, runner) -> None:
        import httpx

        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_httpx.post.side_effect = httpx.ConnectError("refused")
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError

        result = runner.invoke(main, ["run-skill", "test-skill"])
        assert result.exit_code == 1
        assert "Cannot connect" in result.output

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_run_skill_http_error(self, mock_settings, mock_httpx, runner) -> None:
        import httpx

        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        error_response = MagicMock()
        error_response.json.return_value = {"detail": "Skill not found"}
        error_response.status_code = 404

        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.post.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=error_response,
        )

        result = runner.invoke(main, ["run-skill", "missing-skill"])
        assert result.exit_code == 1
        assert "Skill not found" in result.output

    def test_run_skill_invalid_name(self, runner) -> None:
        result = runner.invoke(main, ["run-skill", "INVALID_NAME!"])
        assert result.exit_code != 0
        assert "Invalid skill name" in result.output


class TestHealthCommand:
    """Test `bsage health` command."""

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_health_ok(self, mock_settings, mock_httpx, runner) -> None:
        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "ok" in result.output

    @patch("bsage.cli.httpx")
    @patch("bsage.cli.get_settings")
    def test_health_connection_error(self, mock_settings, mock_httpx, runner) -> None:
        import httpx

        settings = MagicMock()
        settings.gateway_host = "127.0.0.1"
        settings.gateway_port = 8000
        mock_settings.return_value = settings

        mock_httpx.get.side_effect = httpx.ConnectError("refused")
        mock_httpx.ConnectError = httpx.ConnectError

        result = runner.invoke(main, ["health"])
        assert result.exit_code == 1
        assert "Cannot connect" in result.output
