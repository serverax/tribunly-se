import pytest
import os
import re

FILES_TO_CHECK = [
    "client/public/pages/assessment.html",
    "client/public/pages/intake.html",
    "client/public/pages/saved_case.html",
]

def test_no_unsafe_inner_html():
    """
    Ensure that no unsafe innerHTML usages remain in critical frontend files.
    Genuinely static innerHTML (e.g. for icons) is discouraged but may be allowed
    if it cannot contain user/LLM data.
    """
    unsafe_pattern = re.compile(r'\.innerHTML\s*=')
    
    for file_path in FILES_TO_CHECK:
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        matches = unsafe_pattern.findall(content)
        # We expect zero innerHTML usages in the refactored files
        assert len(matches) == 0, f"Unsafe innerHTML found in {file_path}"

def test_textContent_usage():
    """
    Ensure that textContent is used for rendering data.
    """
    safe_pattern = re.compile(r'\.textContent\s*=')
    
    for file_path in FILES_TO_CHECK:
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        matches = safe_pattern.findall(content)
        assert len(matches) > 0, f"No textContent usage found in {file_path}, suggesting incomplete refactor."

if __name__ == "__main__":
    pytest.main([__file__])
