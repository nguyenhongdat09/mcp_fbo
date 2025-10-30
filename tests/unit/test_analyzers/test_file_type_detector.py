"""Tests for file type detector."""

import pytest
from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.core.constants import FileType


@pytest.fixture
def detector():
    """Create detector instance."""
    return FileTypeDetector()


def test_detect_dir_form(detector):
    """Test detection of DIR form XML."""
    xml = '''<?xml version="1.0"?>
    <dir table="m91$000000" type="Voucher">
        <fields></fields>
        <commands>
            <command event="Inserting"></command>
        </commands>
    </dir>'''

    context = detector.detect(xml)

    assert context.file_type == FileType.DIR
    assert context.table_name == "m91$000000"


def test_detect_grid_view(detector):
    """Test detection of Grid View XML."""
    xml = '''<?xml version="1.0"?>
    <grid table="m91$000000" type="Voucher">
        <queries>
            <query event="Loading"></query>
        </queries>
        <toolbar></toolbar>
    </grid>'''

    context = detector.detect(xml)

    assert context.file_type == FileType.GRID_VIEW


def test_detect_grid_detail(detector):
    """Test detection of Grid Detail XML."""
    xml = '''<?xml version="1.0"?>
    <grid type="Detail">
        <fields></fields>
    </grid>'''

    context = detector.detect(xml)

    assert context.file_type == FileType.GRID_DETAIL


def test_detect_filter(detector):
    """Test detection of Filter XML."""
    xml = '''<?xml version="1.0"?>
    <!DOCTYPE dir [
        <!ENTITY XMLWhenFilterLoading SYSTEM "test.xml">
    ]>
    <dir type="Report" cache="true">
        <commands>
            <command event="Processing"></command>
        </commands>
    </dir>'''

    context = detector.detect(xml)

    assert context.file_type == FileType.FILTER
