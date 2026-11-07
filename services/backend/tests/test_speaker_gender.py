from app.speaker_gender import gender_reply_voice, parse_gender
from app.voices import class_voice


def test_parse_gender_accepts_common_labels() -> None:
    assert parse_gender("boy") == "boy"
    assert parse_gender("niño") == "boy"
    assert parse_gender("girl") == "girl"
    assert parse_gender("niña") == "girl"
    assert parse_gender("") is None


def test_gender_reply_voices_match_mateo_and_valeria_providers() -> None:
    boy = gender_reply_voice("boy")
    girl = gender_reply_voice("girl")
    assert boy.provider_voice == class_voice("mateo").provider_voice == "verse"
    assert girl.provider_voice == class_voice("valeria").provider_voice == "marin"
    assert "young man" in boy.instructions
    assert "young woman" in girl.instructions
    assert "child" not in boy.instructions.lower()
    assert "child" not in girl.instructions.lower()
    assert "American English" in boy.instructions
    assert "American English" in girl.instructions
