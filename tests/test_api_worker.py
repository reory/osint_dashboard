import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError
from api.main import ScanRequest 

@given(st.text())
def test_scan_request_username_resilience(username):
    """
    Ensures that usernames containing purely whitespaces, control characters,
    or empty strings are strictly caught and rejected by our validation rules.
    """
    try:
        # Drop 'request_data =' to fix the 'assigned but never used' warning
        ScanRequest(username=username, search_id=42)
        
        # If Pydantic allowed it through, assert that it shouldn't be an empty 
        # or whitespace-only string, otherwise the backend CLI execution will fail.
        assert username.strip() != "", "Allowed an empty or whitespace-only username!"
        
    except ValidationError:
        # If Pydantic correctly blocked an empty/unsafe string, the test passes!
        pass


@given(st.integers(max_value=-1))
def test_scan_request_rejects_negative_ids(neg_id):
    """
    Ensures the system explicitly blocks invalid, negative database IDs.
    """
    with pytest.raises(ValidationError):
        # Directly instantiate the object here as well—no unused variable warnings!
        ScanRequest(username="valid_user", search_id=neg_id)