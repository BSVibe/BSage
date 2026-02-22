"""Tests for bsage.core.skill_context — SkillContext."""

from unittest.mock import MagicMock

from bsage.core.skill_context import SkillContext


class TestSkillContext:
    """Test SkillContext dataclass."""

    def test_context_creation(self) -> None:
        context = SkillContext(
            credentials=MagicMock(),
            garden=MagicMock(),
            llm=MagicMock(),
            config={"key": "value"},
            logger=MagicMock(),
        )
        assert context.config == {"key": "value"}
        assert context.input_data is None

    def test_context_with_input_data(self) -> None:
        context = SkillContext(
            credentials=MagicMock(),
            garden=MagicMock(),
            llm=MagicMock(),
            config={},
            logger=MagicMock(),
            input_data={"events": [1, 2, 3]},
        )
        assert context.input_data == {"events": [1, 2, 3]}
