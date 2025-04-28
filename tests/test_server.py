import os
import shutil
import tempfile

import pytest

from semgrep_mcp.server import CodeFile, McpError, create_temp_files_from_code_content, safe_join


def test_safe_join_valid_paths():
    """Test safe_join with valid paths that should be allowed"""
    base_dir = tempfile.mkdtemp(prefix="semgrep_scan_")

    # Test basic path joining
    assert safe_join(base_dir, "file.txt") == os.path.realpath(os.path.join(base_dir, "file.txt"))

    # Test with subdirectories
    assert safe_join(base_dir, "subdir/file.txt") == os.path.realpath(
        os.path.join(base_dir, "subdir/file.txt")
    )

    # Test with current directory references
    assert safe_join(base_dir, "./file.txt") == os.path.realpath(os.path.join(base_dir, "file.txt"))

    # Test with multiple subdirectories
    assert safe_join(base_dir, "sub1/sub2/file.txt") == os.path.realpath(
        os.path.join(base_dir, "sub1/sub2/file.txt")
    )


def test_safe_join_path_traversal_attempts():
    """Test safe_join blocks path traversal attempts"""
    base_dir = tempfile.mkdtemp(prefix="semgrep_scan_")

    # Test simple parent directory traversal
    with pytest.raises(ValueError, match="Untrusted path escapes the base directory!"):
        safe_join(base_dir, "../file.txt")

    # Test nested parent directory traversal
    with pytest.raises(ValueError, match="Untrusted path escapes the base directory!"):
        safe_join(base_dir, "subdir/../../file.txt")

    # Test absolute path attempt
    with pytest.raises(ValueError, match="Untrusted path must be relative"):
        safe_join(base_dir, "/etc/passwd")

    # Test complex traversal with current directory references
    with pytest.raises(ValueError, match="Untrusted path escapes the base directory!"):
        safe_join(base_dir, "./subdir/../../../file.txt")


def test_safe_join_edge_cases():
    """Test safe_join with edge cases"""
    base_dir = tempfile.mkdtemp(prefix="semgrep_scan_")

    # Test empty path
    assert safe_join(base_dir, "") == os.path.realpath(base_dir)

    # Test current directory
    assert safe_join(base_dir, ".") == os.path.realpath(base_dir)

    # Test path with only slashes
    assert safe_join(base_dir, "///") == os.path.realpath(base_dir)

    # Test path with spaces and special characters
    assert safe_join(base_dir, "my file with spaces.txt") == os.path.realpath(
        os.path.join(base_dir, "my file with spaces.txt")
    )

    # Test path with unicode characters
    assert safe_join(base_dir, "üñîçødé_fïlé.txt") == os.path.realpath(
        os.path.join(base_dir, "üñîçødé_fïlé.txt")
    )


def test_safe_join_with_normalized_base():
    """Test safe_join handles base directory normalization correctly"""
    # Test with non-normalized base path
    base_dir = tempfile.mkdtemp(prefix="semgrep_scan_")

    # Should normalize the base path
    assert safe_join(base_dir, "file.txt") == os.path.realpath(os.path.join(base_dir, "file.txt"))

    # Should still prevent traversal with normalized base
    with pytest.raises(ValueError, match="Untrusted path escapes the base directory!"):
        safe_join(base_dir, "../file.txt")


def test_create_temp_files_from_code_content():
    """Test that create_temp_files_from_code_content correctly creates temp files with content"""
    # Define test code files
    code_files = [
        CodeFile(filename="test_file.py", content="print('Hello, world!')"),
        CodeFile(filename="nested/path/test_file.js", content="console.log('Hello, world!');"),
        CodeFile(filename="special chars/file with spaces.txt", content="Hello, world!"),
    ]

    # Call the function
    temp_dir = None
    try:
        temp_dir = create_temp_files_from_code_content(code_files)

        # Check if temp directory was created
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)

        # Check if files were created with correct content
        for code_file in code_files:
            file_path = os.path.join(temp_dir, code_file.filename)
            assert os.path.exists(file_path)
            with open(file_path) as f:
                content = f.read()
                assert content == code_file.content

        # Check that nested directories were created
        assert os.path.exists(os.path.join(temp_dir, "nested/path"))
        assert os.path.exists(os.path.join(temp_dir, "special chars"))

    finally:
        # Clean up
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_temp_files_from_code_content_empty_list():
    """Test that create_temp_files_from_code_content handles empty file list"""
    code_files = []

    temp_dir = None
    try:
        temp_dir = create_temp_files_from_code_content(code_files)

        # Check if temp directory was created
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)

        # Directory should be empty (except for potential system files like .DS_Store)
        # Just check that no files were created from our empty list
        entries = os.listdir(temp_dir)
        assert all(
            not os.path.isfile(os.path.join(temp_dir, entry)) or entry.startswith(".")
            for entry in entries
        )

    finally:
        # Clean up
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_temp_files_from_code_content_empty_filename():
    """Test that create_temp_files_from_code_content handles empty filenames"""
    code_files = [
        CodeFile(filename="", content="This content should be skipped"),
        CodeFile(filename="valid_file.txt", content="This is valid content"),
    ]

    temp_dir = None
    try:
        temp_dir = create_temp_files_from_code_content(code_files)

        # Check if temp directory was created
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)

        # The empty filename should be skipped - we can't directly check for a file with empty name
        # because os.path.join(temp_dir, "") just returns temp_dir
        # Instead, we'll check that only the valid file exists in the directory
        files = [
            f
            for f in os.listdir(temp_dir)
            if os.path.isfile(os.path.join(temp_dir, f)) and not f.startswith(".")
        ]
        assert len(files) == 1
        assert "valid_file.txt" in files

        # The valid file should be created
        valid_file_path = os.path.join(temp_dir, "valid_file.txt")
        assert os.path.exists(valid_file_path)
        with open(valid_file_path) as f:
            content = f.read()
            assert content == "This is valid content"

    finally:
        # Clean up
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_temp_files_from_code_content_path_traversal():
    """Test that create_temp_files_from_code_content prevents path traversal"""
    # Define test code files with path traversal attempts
    code_files = [
        CodeFile(filename="../attempt_to_write_outside.txt", content="This should fail"),
        CodeFile(filename="subdir/../../../etc/passwd", content="This should fail too"),
        CodeFile(filename="/absolute/path/file.txt", content="This should fail as well"),
    ]

    # The function should raise a ValueError for path traversal attempts
    with pytest.raises(McpError):
        create_temp_files_from_code_content(code_files)
