"""Test suite for TOML/JSON converter."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.toml_get import (
    ConversionConfig,
    FileType,
    JSONConverter,
    TOMLConverter,
    convert_file,
    serialize_json,
)


class TestFileType:
    """Tests for FileType enum."""

    def test_file_type_values(self) -> None:
        """Test FileType enum values."""
        assert FileType.TOML.name == "TOML"
        assert FileType.JSON.name == "JSON"


class TestTOMLConverter:
    """Tests for TOMLConverter class."""

    def test_parse_valid_toml(self, tmp_path: Path) -> None:
        """Test parsing valid TOML file."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[app]\nname = "TestApp"\nversion = "1.0.0"')

        converter = TOMLConverter()
        result = converter.parse(toml_file)

        assert result["app"]["name"] == "TestApp"
        assert result["app"]["version"] == "1.0.0"

    def test_parse_invalid_toml_exits(self, tmp_path: Path) -> None:
        """Test parsing invalid TOML exits with code 2."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text("not valid toml {{[}")

        converter = TOMLConverter()
        with pytest.raises(SystemExit) as exc_info:
            converter.parse(toml_file)
        assert exc_info.value.code == 2

    def test_parse_missing_file_exits(self, tmp_path: Path) -> None:
        """Test parsing missing file exits with code 1."""
        missing_file = tmp_path / "nonexistent.toml"

        converter = TOMLConverter()
        with pytest.raises(SystemExit) as exc_info:
            converter.parse(missing_file)
        assert exc_info.value.code == 1


class TestJSONConverter:
    """Tests for JSONConverter class."""

    def test_parse_valid_json(self, tmp_path: Path) -> None:
        """Test parsing valid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "TestApp", "version": "1.0.0"}')

        converter = JSONConverter()
        result = converter.parse(json_file)

        assert result["name"] == "TestApp"
        assert result["version"] == "1.0.0"

    def test_parse_invalid_json_exits(self, tmp_path: Path) -> None:
        """Test parsing invalid JSON exits with code 2."""
        json_file = tmp_path / "test.json"
        json_file.write_text("not valid json")

        converter = JSONConverter()
        with pytest.raises(SystemExit) as exc_info:
            converter.parse(json_file)
        assert exc_info.value.code == 2


class TestConversionConfig:
    """Tests for ConversionConfig dataclass."""

    def test_from_args_toml(self, tmp_path: Path) -> None:
        """Test creating config from TOML file args."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[app]\nname = "Test"')

        class Args:
            file = toml_file
            pretty = False

        config = ConversionConfig.from_args(Args())
        assert config.file_path == toml_file
        assert config.pretty is False
        assert config.file_type == FileType.TOML

    def test_from_args_json(self, tmp_path: Path) -> None:
        """Test creating config from JSON file args."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "Test"}')

        class Args:
            file = json_file
            pretty = True

        config = ConversionConfig.from_args(Args())
        assert config.file_path == json_file
        assert config.pretty is True
        assert config.file_type == FileType.JSON

    def test_from_args_missing_file_exits(self, tmp_path: Path) -> None:
        """Test creating config with missing file exits."""
        missing_file = tmp_path / "nonexistent.toml"

        class Args:
            file = missing_file
            pretty = False

        with pytest.raises(SystemExit) as exc_info:
            ConversionConfig.from_args(Args())
        assert exc_info.value.code == 1

    def test_from_args_directory_exits(self, tmp_path: Path) -> None:
        """Test creating config with directory path exits."""

        class Args:
            file = tmp_path
            pretty = False

        with pytest.raises(SystemExit) as exc_info:
            ConversionConfig.from_args(Args())
        assert exc_info.value.code == 1

    def test_from_args_unsupported_extension_exits(self, tmp_path: Path) -> None:
        """Test creating config with unsupported extension exits."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("name: Test")

        class Args:
            file = yaml_file
            pretty = False

        with pytest.raises(SystemExit) as exc_info:
            ConversionConfig.from_args(Args())
        assert exc_info.value.code == 1


class TestSerializeJson:
    """Tests for serialize_json function."""

    def test_compact_json(self) -> None:
        """Test compact JSON serialization."""
        data = {"name": "Test", "version": "1.0.0"}
        result = serialize_json(data, pretty=False)
        # Should not contain newlines in compact mode
        assert "\n" not in result
        assert '"name":"Test"' in result or '"name": "Test"' in result

    def test_pretty_json(self) -> None:
        """Test pretty JSON serialization."""
        data = {"name": "Test"}
        result = serialize_json(data, pretty=True)
        # Should contain newlines in pretty mode
        assert "\n" in result
        assert '"name": "Test"' in result

    def test_unicode_handling(self) -> None:
        """Test Unicode handling in JSON."""
        data = {"name": "テスト", "emoji": "🎉"}
        result = serialize_json(data, pretty=False)
        assert "テスト" in result
        assert "🎉" in result


class TestConvertFile:
    """Tests for convert_file function."""

    def test_convert_toml(self, tmp_path: Path) -> None:
        """Test converting TOML file."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[app]\nname = "TestApp"')

        config = ConversionConfig(
            file_path=toml_file,
            pretty=False,
            file_type=FileType.TOML,
        )
        result = convert_file(config)

        assert '"app"' in result
        assert '"name"' in result
        assert '"TestApp"' in result

    def test_convert_json(self, tmp_path: Path) -> None:
        """Test converting (reformatting) JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name":"TestApp"}')

        config = ConversionConfig(
            file_path=json_file,
            pretty=True,
            file_type=FileType.JSON,
        )
        result = convert_file(config)

        assert '"name": "TestApp"' in result


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("config.toml", FileType.TOML),
        ("config.json", FileType.JSON),
        ("data.TOML", FileType.TOML),  # Case insensitive
        ("data.JSON", FileType.JSON),
    ],
)
def test_file_type_detection(tmp_path: Path, filename: str, expected_type: FileType) -> None:
    """Test file type detection from extension."""
    file_path = tmp_path / filename
    file_path.write_text('{"test": true}' if expected_type == FileType.JSON else "[test]")

    class Args:
        file = file_path
        pretty = False

    config = ConversionConfig.from_args(Args())
    assert config.file_type == expected_type
