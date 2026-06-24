from app.agents.chapter_writer import chapter_output_looks_truncated


def test_truncation_detector_flags_mid_sentence_cutoff():
    text = "三者合在一起，构成理解睡眠的第一张底图。\n\n现在再"
    assert chapter_output_looks_truncated(text, 5500) is True


def test_truncation_detector_accepts_complete_chapter():
    body = "本段论述完整。" * 100
    text = f"{body}本章到此告一段落。"
    assert chapter_output_looks_truncated(text, 800) is False
