def test_textparser_is_registered_under_txt() -> None:
def test_textparser_is_a_baseparser_subclass() -> None:
def test_registry_get_txt_constructs_textparser_instance() -> None:


    assert [c.content for c in chunks] == ["one", "two", "three"]
    assert [c.index for c in chunks] == [0, 1, 2]
    assert [c.id for c in chunks] == ["x.txt__0", "x.txt__1", "x.txt__2"]


@pytest.mark.asyncio
async def test_per_paragraph_whitespace_is_stripped() -> None:
    parser = TextParser()

    chunks = await parser.parse(b"  leading\n\ntrailing  \n\n  both  ", source="s.txt")

    assert [c.content for c in chunks] == ["leading", "trailing", "both"]


@pytest.mark.asyncio
async def test_empty_bytes_returns_empty_list() -> None:
    parser = TextParser()

    chunks = await parser.parse(b"", source="empty.txt")

    assert chunks == []


@pytest.mark.asyncio
async def test_whitespace_only_content_returns_empty_list() -> None:
    parser = TextParser()

    chunks = await parser.parse(b"   \n\n  \t \n", source="ws.txt")

    assert chunks == []


@pytest.mark.asyncio
async def test_non_utf8_bytes_raises_unicode_decode_error() -> None:
    parser = TextParser()

    # 0x80 is invalid as the first byte of a UTF-8 sequence.
    with pytest.raises(UnicodeDecodeError):
        await parser.parse(b"\x80abc", source="bad.txt")


@pytest.mark.asyncio
async def test_source_propagates_into_every_chunk() -> None:
    parser = TextParser()

    chunks = await parser.parse(b"a\n\nb\n\nc", source="my/doc.txt")

    assert {c.source for c in chunks} == {"my/doc.txt"}


@pytest.mark.asyncio
async def test_returned_chunks_are_frozen() -> None:
    parser = TextParser()

    chunks = await parser.parse(b"single", source="f.txt")
    assert len(chunks) == 1

    # `Chunk` is declared frozen + extra="forbid" in backend.core.types.
    with pytest.raises(Exception):  # pydantic ValidationError on frozen model
        chunks[0].content = "mutated"  # type: ignore[misc]
