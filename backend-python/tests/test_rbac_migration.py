from models.user import UserAuth, AgentKeyMetadata

def test_legacy_str_key_migrates_to_full_access():
    auth = UserAuth.model_validate({
        "password_hash": "hash",
        "agent_keys": [
            "some-bcrypt-hash-string"
        ]
    })
    assert len(auth.agent_keys) == 1
    key = auth.agent_keys[0]
    assert isinstance(key, AgentKeyMetadata)
    assert key.hash == "some-bcrypt-hash-string"
    assert key.name == "Legacy Key 1"
    assert key.scopes == ["read", "write"]

def test_v1_dict_key_without_scopes_migrates_to_full_access():
    auth = UserAuth.model_validate({
        "password_hash": "hash",
        "agent_keys": [
            {
                "hash": "hash-str",
                "name": "Custom Key",
                "created_at": "2026-06-01"
            }
        ]
    })
    assert len(auth.agent_keys) == 1
    key = auth.agent_keys[0]
    assert isinstance(key, AgentKeyMetadata)
    assert key.hash == "hash-str"
    assert key.name == "Custom Key"
    assert key.scopes == ["read", "write"]

def test_new_key_preserves_explicit_scopes():
    auth = UserAuth.model_validate({
        "password_hash": "hash",
        "agent_keys": [
            {
                "hash": "hash-str",
                "name": "Custom Key",
                "created_at": "2026-06-01",
                "scopes": ["read"]
            }
        ]
    })
    assert len(auth.agent_keys) == 1
    key = auth.agent_keys[0]
    assert isinstance(key, AgentKeyMetadata)
    assert key.scopes == ["read"]
