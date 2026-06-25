"""Tests for composite Investigation Record provider.

Verifies that writes go to the primary backend only and reads
fan out across all backends with proper deduplication.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from providers.investigation.composite import (
    CompositeRecordProvider,
)
from providers.investigation.file import FileRecordProvider
from providers.investigation.models import (
    AnomalyContext,
    BuildHistoryEntry,
    InvestigationRecord,
    InvestigationState,
)


def _make_record(**overrides) -> InvestigationRecord:
    """Create a test record with sensible defaults."""
    defaults = {
        "anomaly_context": AnomalyContext(
            subsystem="storage_io",
            metric="iops_4k_randread",
            direction="degrading",
            platform="NXP_S32G",
            magnitude="-31%",
        ),
        "root_cause_summary": "virtio-blk regression",
        "confidence": 0.92,
    }
    defaults.update(overrides)
    return InvestigationRecord(**defaults)


@pytest.fixture
def writer(tmp_path: Path) -> FileRecordProvider:
    """Primary (writable) backend."""
    return FileRecordProvider(
        persist_dir=tmp_path / "writer",
    )


@pytest.fixture
def reader_a(tmp_path: Path) -> FileRecordProvider:
    """Secondary read-only backend A."""
    return FileRecordProvider(
        persist_dir=tmp_path / "reader_a",
    )


@pytest.fixture
def reader_b(tmp_path: Path) -> FileRecordProvider:
    """Secondary read-only backend B."""
    return FileRecordProvider(
        persist_dir=tmp_path / "reader_b",
    )


@pytest.fixture
def composite(
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
    reader_b: FileRecordProvider,
) -> CompositeRecordProvider:
    """Composite with writer + two readers."""
    return CompositeRecordProvider(
        writer=writer,
        readers=[writer, reader_a, reader_b],
    )


# --- Writes go to writer only ---


@pytest.mark.asyncio
async def test_create_goes_to_writer(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
):
    """Create writes to the primary backend only."""
    record = _make_record(
        investigation_id="RCA-WRITE001",
    )
    await composite.create(record)

    # Writer has it
    assert await writer.get("RCA-WRITE001") is not None
    # Reader A does not
    assert await reader_a.get("RCA-WRITE001") is None


@pytest.mark.asyncio
async def test_append_goes_to_writer(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
):
    """Append build history writes to writer only."""
    record = _make_record(
        investigation_id="RCA-APPEND01",
    )
    await writer.create(record)

    await composite.append_build_history(
        "RCA-APPEND01",
        BuildHistoryEntry(
            build_id="2026.05.15",
            action="SKIP_MATCHED",
        ),
    )

    fetched = await writer.get("RCA-APPEND01")
    assert fetched is not None
    assert len(fetched.build_history) == 1


@pytest.mark.asyncio
async def test_link_jira_goes_to_writer(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
):
    """Link Jira writes to writer only."""
    record = _make_record(
        investigation_id="RCA-JIRA0001",
    )
    await writer.create(record)

    await composite.link_jira("RCA-JIRA0001", "RHIVOS-4821")

    fetched = await writer.get("RCA-JIRA0001")
    assert fetched is not None
    assert fetched.jira_ticket == "RHIVOS-4821"


@pytest.mark.asyncio
async def test_close_goes_to_writer(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
):
    """Close writes to writer only."""
    record = _make_record(
        investigation_id="RCA-CLOSE001",
    )
    await writer.create(record)

    await composite.close_record("RCA-CLOSE001")

    fetched = await writer.get("RCA-CLOSE001")
    assert fetched is not None
    assert fetched.state == InvestigationState.RESOLVED


# --- Reads fan out across all backends ---


@pytest.mark.asyncio
async def test_get_finds_in_writer(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
):
    """Get finds records in the writer."""
    record = _make_record(
        investigation_id="RCA-GETW0001",
    )
    await writer.create(record)

    result = await composite.get("RCA-GETW0001")
    assert result is not None
    assert result.investigation_id == "RCA-GETW0001"


@pytest.mark.asyncio
async def test_get_finds_in_reader(
    composite: CompositeRecordProvider,
    reader_a: FileRecordProvider,
):
    """Get finds records in a read-only backend."""
    record = _make_record(
        investigation_id="RCA-GETR0001",
    )
    # Write directly to reader_a (simulating pre-existing data)
    await reader_a.create(record)

    result = await composite.get("RCA-GETR0001")
    assert result is not None
    assert result.investigation_id == "RCA-GETR0001"


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(
    composite: CompositeRecordProvider,
):
    """Get returns None when no backend has the record."""
    result = await composite.get("RCA-MISSING1")
    assert result is None


@pytest.mark.asyncio
async def test_query_merges_across_backends(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
    reader_b: FileRecordProvider,
):
    """Query returns records from all backends."""
    await writer.create(_make_record(investigation_id="RCA-QWRITE01"))
    await reader_a.create(_make_record(investigation_id="RCA-QREADA1"))
    await reader_b.create(_make_record(investigation_id="RCA-QREADB1"))

    results = await composite.query()
    ids = {r.investigation_id for r in results}
    assert "RCA-QWRITE01" in ids
    assert "RCA-QREADA1" in ids
    assert "RCA-QREADB1" in ids
    assert len(results) == 3


@pytest.mark.asyncio
async def test_query_deduplicates_by_id(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
):
    """Same ID in multiple backends appears only once."""
    record = _make_record(
        investigation_id="RCA-DEDUP001",
    )
    await writer.create(record)
    # Same ID in reader_a (simulating migration leftovers)
    await reader_a.create(record)

    results = await composite.query()
    ids = [r.investigation_id for r in results]
    assert ids.count("RCA-DEDUP001") == 1


@pytest.mark.asyncio
async def test_query_writer_takes_precedence(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
):
    """When same ID exists in writer and reader, writer wins."""
    # Writer has the updated version
    writer_record = _make_record(
        investigation_id="RCA-PREC0001",
        root_cause_summary="Writer version",
    )
    await writer.create(writer_record)

    # Reader has an older version
    reader_record = _make_record(
        investigation_id="RCA-PREC0001",
        root_cause_summary="Reader version",
    )
    await reader_a.create(reader_record)

    results = await composite.query()
    match = [r for r in results if r.investigation_id == "RCA-PREC0001"]
    assert len(match) == 1
    # Writer is first in the readers list, so its copy wins
    assert match[0].root_cause_summary == "Writer version"


@pytest.mark.asyncio
async def test_query_filters_apply_across_backends(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
):
    """Filters work across all backends."""
    await writer.create(
        _make_record(
            investigation_id="RCA-FILTR001",
            anomaly_context=AnomalyContext(
                subsystem="storage_io",
                metric="iops",
            ),
        )
    )
    await reader_a.create(
        _make_record(
            investigation_id="RCA-FILTR002",
            anomaly_context=AnomalyContext(
                subsystem="networking",
                metric="throughput",
            ),
        )
    )

    results = await composite.query(
        subsystem="networking",
    )
    assert len(results) == 1
    assert results[0].investigation_id == "RCA-FILTR002"


@pytest.mark.asyncio
async def test_query_respects_limit(
    composite: CompositeRecordProvider,
    writer: FileRecordProvider,
    reader_a: FileRecordProvider,
):
    """Limit applies to the merged result set."""
    for i in range(5):
        await writer.create(
            _make_record(
                investigation_id=f"RCA-LIM_W{i:04d}",
            )
        )
    for i in range(5):
        await reader_a.create(
            _make_record(
                investigation_id=f"RCA-LIM_R{i:04d}",
            )
        )

    results = await composite.query(limit=3)
    assert len(results) == 3
