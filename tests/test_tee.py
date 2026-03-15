import io
from unittest.mock import MagicMock

from main import _Tee


# ---------------------------------------------------------------------------
# write()
# ---------------------------------------------------------------------------


def test_write_sends_data_to_primary() -> None:
    primary: io.StringIO = io.StringIO()
    secondary: io.StringIO = io.StringIO()
    tee: _Tee = _Tee(primary, secondary)  # type: ignore[arg-type]
    tee.write("hello")
    assert primary.getvalue() == "hello"


def test_write_sends_data_to_secondary() -> None:
    primary: io.StringIO = io.StringIO()
    secondary: io.StringIO = io.StringIO()
    tee: _Tee = _Tee(primary, secondary)  # type: ignore[arg-type]
    tee.write("hello")
    assert secondary.getvalue() == "hello"


def test_write_returns_secondary_write_count() -> None:
    primary: io.StringIO = io.StringIO()
    secondary: io.StringIO = io.StringIO()
    tee: _Tee = _Tee(primary, secondary)  # type: ignore[arg-type]
    result: int = tee.write("hello")
    assert result == 5


def test_write_accumulates_across_calls() -> None:
    primary: io.StringIO = io.StringIO()
    secondary: io.StringIO = io.StringIO()
    tee: _Tee = _Tee(primary, secondary)  # type: ignore[arg-type]
    tee.write("foo")
    tee.write("bar")
    assert secondary.getvalue() == "foobar"
    assert primary.getvalue() == "foobar"


# ---------------------------------------------------------------------------
# flush()
# ---------------------------------------------------------------------------


def test_flush_calls_flush_on_primary() -> None:
    primary: MagicMock = MagicMock()
    secondary: io.StringIO = io.StringIO()
    tee: _Tee = _Tee(primary, secondary)
    tee.flush()
    primary.flush.assert_called_once()


def test_flush_calls_flush_on_secondary() -> None:
    primary: io.StringIO = io.StringIO()
    secondary: MagicMock = MagicMock()
    tee: _Tee = _Tee(primary, secondary)  # type: ignore[arg-type]
    tee.flush()
    secondary.flush.assert_called_once()
