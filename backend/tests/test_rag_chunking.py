import pytest

from app.services.rag_service import _split_text


def test_split_text_respects_chunk_size_and_overlap():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = _split_text(text, size=100, overlap=20)

    assert chunks
    assert all(len(chunk) <= 100 for chunk in chunks)
    chunk_words = [chunk.split() for chunk in chunks]
    assert any(
        set(chunk_words[index - 1][-2:]).intersection(chunk_words[index][:2])
        for index in range(1, len(chunk_words))
    )


def test_split_text_splits_long_tokens():
    chunks = _split_text("x" * 205, size=50, overlap=5)

    assert chunks == ["x" * 50, "x" * 50, "x" * 50, "x" * 50, "x" * 5]


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (10, 10), (10, 11), (10, -1)],
)
def test_split_text_rejects_invalid_parameters(size, overlap):
    with pytest.raises(ValueError):
        _split_text("hello", size=size, overlap=overlap)


def test_split_text_empty_input_returns_empty_chunks():
    assert _split_text("", size=100, overlap=10) == []
