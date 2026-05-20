import pytest
from hypothesis import given, strategies as st

# Valid states the application allows for a search lifecycle
VALID_STATUSES = ['pending', 'running', 'completed', 'failed']

class MockTargetSearch:
    """Simulates your real Django TargetSearch database model constraints."""

    def __init__(self, username, status="pending"):
        # Django CharFields have a max length limitation (typically 150 or 255)
        if len(username) > 150:
            raise ValueError("Data too long for database column column (max 150)")
            
        # Hardens status fields to ensure bad telemetry states don't pollute rows
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status state: {status}")
            
        self.username = username
        self.status = status

    def __str__(self):
        return f"Target: {self.username} ({self.status})"


class MockDiscoveredProfile:
    """Simulates the child table that tracks individual site hits."""

    def __init__(self, search_record, site_name, profile_url):
        self.search = search_record  # Simulates ForeignKey relation
        self.site_name = site_name
        self.profile_url = profile_url


@given(st.text())
def test_model_string_representation_resilience(random_username):
    """Ensures string rendering remains stable for normal lengths."""

    # Restrict the length here just to test standard rendering boundaries safely
    if len(random_username) <= 150:
        mock_record = MockTargetSearch(username=random_username, status="pending")
        assert f"Target: {random_username}" in str(mock_record)


@given(st.text(min_size=151))
def test_database_enforces_maximum_length_boundaries(overflow_username):
    """
    CRITICAL CONSTRAINT CHECK
    Hypothesis will generate strings exceeding 150 characters.
    We assert that the model infrastructure strictly catches and blocks
    overflow states, preventing silent truncation inside SQLite/PostgreSQL.
    """
    with pytest.raises(ValueError, match="Data too long"):
        MockTargetSearch(username=overflow_username)


@given(st.text())
def test_database_rejects_corrupted_status_states(garbage_status):
    """
    Ensures that rogue strings sent over the wire cannot inject invalid 
    states into the operational data tracking columns.
    """
    # If Hypothesis happens to generate a valid keyword, skip it
    if garbage_status in VALID_STATUSES:
        return
        
    with pytest.raises(ValueError, match="Invalid status state"):
        MockTargetSearch(username="valid_user", status=garbage_status)