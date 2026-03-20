"""Tests for UntrustedContent type safety."""

import pytest

from scutl.types import UntrustedContent


class TestUntrustedContent:
    def test_strips_tags(self) -> None:
        uc = UntrustedContent("<untrusted>hello world</untrusted>")
        assert uc.to_string_unsafe() == "hello world"

    def test_prompt_safe_wraps_tags(self) -> None:
        uc = UntrustedContent("<untrusted>hello</untrusted>")
        assert uc.to_prompt_safe() == "<untrusted>hello</untrusted>"

    def test_raw_body_alias(self) -> None:
        uc = UntrustedContent("<untrusted>test</untrusted>")
        assert uc.raw_body == "<untrusted>test</untrusted>"

    def test_content_self_reference(self) -> None:
        uc = UntrustedContent("<untrusted>x</untrusted>")
        assert uc.content is uc

    def test_handles_unwrapped_input(self) -> None:
        uc = UntrustedContent("plain text")
        assert uc.to_string_unsafe() == "plain text"
        assert uc.to_prompt_safe() == "<untrusted>plain text</untrusted>"

    def test_str_raises(self) -> None:
        uc = UntrustedContent("<untrusted>trap</untrusted>")
        with pytest.raises(TypeError, match="cannot be converted to str"):
            str(uc)

    def test_format_raises(self) -> None:
        uc = UntrustedContent("<untrusted>trap</untrusted>")
        with pytest.raises(TypeError, match="cannot be used in f-strings"):
            f"{uc}"

    def test_concat_raises(self) -> None:
        uc = UntrustedContent("<untrusted>trap</untrusted>")
        with pytest.raises(TypeError, match="cannot be concatenated"):
            uc + " extra"  # type: ignore[operator]
        with pytest.raises(TypeError, match="cannot be concatenated"):
            "prefix " + uc  # type: ignore[operator]

    def test_repr(self) -> None:
        uc = UntrustedContent("<untrusted>hi</untrusted>")
        assert repr(uc) == "UntrustedContent('hi')"

    def test_equality(self) -> None:
        a = UntrustedContent("<untrusted>same</untrusted>")
        b = UntrustedContent("<untrusted>same</untrusted>")
        c = UntrustedContent("<untrusted>diff</untrusted>")
        assert a == b
        assert a != c

    def test_hash(self) -> None:
        a = UntrustedContent("<untrusted>same</untrusted>")
        b = UntrustedContent("<untrusted>same</untrusted>")
        assert hash(a) == hash(b)

    def test_len(self) -> None:
        uc = UntrustedContent("<untrusted>hello</untrusted>")
        assert len(uc) == 5

    def test_bool(self) -> None:
        assert bool(UntrustedContent("<untrusted>x</untrusted>"))
        assert not bool(UntrustedContent("<untrusted></untrusted>"))
