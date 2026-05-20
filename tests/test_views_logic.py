# This test file targets the Django report pathing and data rendering.

import pytest
from hypothesis import given, strategies as st

def clean_path_logic(username_input):
    """The exact normalization snippet inside your views.py."""
    
    target_username = username_input.lower().strip()
    return f"report_{target_username}_simple.json"


def mock_view_data_extractor(raw_json):
    """
    Simulates a highly hardened extraction layer inside scanner/views.py.
    It guarantees that no matter what garbage data is found inside the JSON,
    the front-end template ALWAYS receives clean, predictable strings.
    """
    extracted_profiles = []
    
    if not isinstance(raw_json, dict):
        return extracted_profiles

    for site_name, target_data in raw_json.items():
        if isinstance(target_data, dict):
            # Safely parse the status dictionary block
            status_block = target_data.get("status", {})
            if not isinstance(status_block, dict):
                status_block = {}
                
            # Extract and strictly validate data elements
            profile_url = status_block.get("link")
            avatar_url = status_block.get("avatar")
            
            # ROBUST ENFORCEMENT: If fields aren't strings, force safe defaults
            if not isinstance(profile_url, str):
                profile_url = "#"
            if not isinstance(avatar_url, str):
                avatar_url = "/static/default-avatar.png"
                
            extracted_profiles.append({
                "site": site_name,
                "link": profile_url,
                "avatar": avatar_url
            })
            
    return extracted_profiles


@given(st.text(min_size=1))
def test_filename_normalization_is_always_lowercase(raw_username):
    """Ensures the filename compilation logic handles all variations."""

    filename = clean_path_logic(raw_username)
    assert filename.startswith("report_")
    assert filename.endswith("_simple.json")
    assert filename == filename.lower()


@given(st.recursive(
    st.none() | st.booleans() | st.text() | st.integers(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children)
))
def test_view_extraction_guarantees_string_outputs(corrupted_json_packet):
    """
    CRITICAL STABILITY CHECK
    Hypothesis will flood this test with completely broken data payloads.
    Assert that the extraction logic ALWAYS protects the front-end template
    by formatting everything into clean strings, completely preventing type crashes.
    """
    processed_data = mock_view_data_extractor(corrupted_json_packet)
    
    assert isinstance(processed_data, list)
    
    # Verify that every item passed down to the HTML template is safe
    for profile in processed_data:
        assert isinstance(profile, dict)
        assert isinstance(profile.get("site"), str)
        assert isinstance(profile.get("link"), str)
        assert isinstance(profile.get("avatar"), str)