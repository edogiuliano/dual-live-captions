import json
import pytest
from dual_live_captions.comparison import LiveComparison, SnapshotTracker, tokenize
from dual_live_captions.comparison_ui import new_report
from dual_live_captions.comparison_windows import caption_plain
from dual_live_captions.comparison_windows import WindowCaptionReader, CaptionReadError
from types import SimpleNamespace
import time


def seeded():
    comparison = LiveComparison()
    comparison.observe("", {"en": "", "es": ""}, 0, 0)
    return comparison


@pytest.mark.parametrize("delta", [-.6, .4, 1.1])
def test_first_appearance_delta_has_correct_sign(delta):
    comparison = seeded()
    text = "we are ready to start the new comparison today"
    comparison.observe(text, {"en": text}, 2, 2 + delta)
    report = comparison.summarize(6)
    assert report["matched_words"] == len(tokenize(text))
    assert report["dual_minus_windows_median_ms"] == pytest.approx(delta * 1000)
    assert report["word_agreement_percent"] == 100


def test_preexisting_captions_are_not_timestamped_as_new_speech():
    comparison = LiveComparison()
    comparison.observe("previous sensitive conversation", {"en": "previous sensitive conversation"}, 0, 0)
    assert comparison.summarize(5)["matched_words"] == 0
    comparison.observe("previous sensitive conversation we will start the test now", {"en": "previous sensitive conversation we will start the test now"}, 6, 6.5)
    result = comparison.summarize(9)
    assert result["matched_words"] == 6
    assert result["dual_minus_windows_median_ms"] == 500


def test_rolling_prefix_is_not_a_correction_or_duplicate():
    tracker = SnapshotTracker()
    tracker.update("", 0)
    tracker.update("one two three four five", 1)
    tracker.update("three four five six seven", 2)
    assert tracker.revisions == 0
    assert [w.word for w in tracker.stable(5)] == "one two three four five six seven".split()


def test_correction_preserves_sequence_and_changes_appearance_time():
    tracker = SnapshotTracker()
    tracker.update("", 0)
    tracker.update("we go tuesday after lunch", 1)
    tracker.update("we go wednesday after lunch", 2)
    words = tracker.stable(5)
    assert [w.word for w in words] == "we go wednesday after lunch".split()
    assert next(w.first for w in words if w.word == "wednesday") == 2
    assert tracker.revisions == 1


def test_disagreement_is_between_common_anchors_not_unequal_tails():
    comparison = seeded()
    windows = "we are going to the big store this afternoon then we come back"
    dual = "we are going to the small store this afternoon then we come back extra unfinished tail"
    comparison.observe(windows, {"en": dual}, 1, 1.3)
    result = comparison.summarize(5)
    assert result["edit_operations_vs_windows"] == 1
    assert 90 < result["word_agreement_percent"] < 100
    assert result["compared_words"] == len(tokenize(windows))


def test_far_apart_repeated_text_cannot_establish_latency():
    comparison = seeded()
    text = "thank you for your help today"
    comparison.observe(text, {"en": text}, 1, 25)
    result = comparison.summarize(30)
    assert result["matched_words"] == 0
    assert result["dual_minus_windows_median_ms"] is None


def test_repeated_phrases_keep_their_separate_chronology():
    comparison = seeded()
    phrase = "thank you very much"
    comparison.observe(phrase, {"en": phrase}, 1, 1.5)
    comparison.observe(phrase + " " + phrase, {"en": phrase + " " + phrase}, 10, 10.5)
    result = comparison.summarize(15)
    assert result["matched_words"] == 8
    assert result["dual_minus_windows_median_ms"] == 500


def test_other_language_is_counted_but_not_mislabeled_as_disagreement():
    comparison = seeded()
    comparison.observe("we are ready to start this test now", {"en": "we are ready to start this test now", "es": "hola necesito un turno"}, 1, 1.2)
    result = comparison.summarize(5)
    assert result["word_agreement_percent"] == 100
    assert result["dual_es_observed_words"] == 4


def test_stale_silence_reports_no_new_activity_not_zero_latency():
    comparison = seeded()
    result = comparison.summarize(50)
    assert result["seconds_since_text_change"] is None
    assert result["dual_minus_windows_median_ms"] is None
    assert result["word_agreement_percent"] is None


def test_text_and_numeric_reports_remain_bounded_and_private():
    tracker = SnapshotTracker(capacity=20)
    tracker.update("", 0)
    for i in range(1000):
        tracker.update(f"word{i} suffix", i / 10)
    assert len(tracker.ledger) == 20
    assert len(tracker.current) == 2
    comparison = seeded()
    secret = "private patient information should never be stored in a report"
    comparison.observe(secret, {"en": secret}, 1, 1.4)
    report = new_report("en", 30)
    report["latest"] = comparison.summarize(5)
    encoded = json.dumps(report)
    assert "patient" not in encoded
    assert "private" not in encoded
    assert report["privacy"]["transcripts_saved"] is False


def test_html_and_waiting_placeholders_are_not_counted_as_captions():
    assert caption_plain('<span style="color:red">Good &amp; ready</span>') == "Good & ready"
    assert caption_plain("Waiting for English speech…") == ""
    assert caption_plain("Esperando voz en español…") == ""


def test_reading_old_captions_cannot_produce_false_live_timestamps():
    reader = WindowCaptionReader.__new__(WindowCaptionReader)
    reader.last_probe = time.perf_counter()
    reader.binding = (1, 2)
    reader.follow_nodes = [SimpleNamespace(CurrentName="Releyendo")]
    reader.windows_node = None
    with pytest.raises(CaptionReadError, match="relectura"):
        reader.read()
