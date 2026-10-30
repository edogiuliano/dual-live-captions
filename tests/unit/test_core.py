import json
import numpy as np
import pytest
from dual_live_captions.audio import AudioFrame, BoundedAudioQueue, Converter, RingBuffer
from dual_live_captions.settings import Settings, PROFILES
from dual_live_captions.subtitles import Agreement, Caption, History, Word, srt_time
from dual_live_captions.language import LanguageRouter
from dual_live_captions.hotkeys import parse_hotkey


def test_ring_rolls_without_growth():
    ring = RingBuffer(100)
    for i in range(1000):
        ring.append(np.arange(i * 16, (i + 1) * 16, dtype=np.float32))
    np.testing.assert_array_equal(ring.read(), np.arange(15900, 16000, dtype=np.float32))
    assert len(ring.data) == ring.capacity == 100


def test_ring_large_append_then_wrap():
    ring = RingBuffer(5)
    ring.append(np.arange(8))
    ring.append(np.arange(8, 11))
    np.testing.assert_array_equal(ring.read(), np.arange(6, 11))


def test_queue_drops_oldest_and_marks_discontinuity():
    q = BoundedAudioQueue(3)
    for i in range(10):
        q.put(AudioFrame("system", np.zeros(512, np.float32), i, 0))
    assert q.queue.qsize() == 3
    assert q.dropped == 7
    assert q.queue.get().discontinuity
    q.clear()
    assert q.queue.empty()


@pytest.mark.parametrize("rate", [32000, 44100, 48000])
def test_stereo_conversion_preserves_frequency_and_duration(rate):
    x = .2 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate)
    stereo = np.column_stack((x, x)).astype(np.float32)
    conv = Converter(rate, 2)
    frames = []
    for pos in range(0, rate, 2048):
        frames.extend(conv.convert(stereo[pos:pos + 2048].tobytes()))
    mono = np.concatenate(frames)
    assert 15000 <= len(mono) <= 16000
    frequencies = np.fft.rfftfreq(len(mono), 1 / 16000)
    peak = frequencies[np.argmax(abs(np.fft.rfft(mono)))]
    assert abs(peak - 440) < 2
    assert all(len(f) == 512 for f in frames)


def test_conversion_sanitizes_nan():
    frames = Converter(16000, 1).convert(np.full(1024, np.nan, np.float32).tobytes())
    assert all(np.all(np.isfinite(f)) for f in frames)


def test_agreement_partial_corrects_then_commits_once():
    a = Agreement()
    hello = Word(" Hello", 0, .5)
    wrong = Word(" world", .5, .9)
    fixed = Word(" there", .5, .9)
    committed, partial = a.update([hello, wrong], audio_end=1.2)
    assert not committed and partial == [hello, wrong]
    committed, partial = a.update([hello, fixed], audio_end=1.3)
    assert committed == [hello] and partial == [fixed]
    committed, partial = a.update([hello, fixed], final=True)
    assert committed == [fixed] and not partial
    assert a.update([hello, fixed], final=True) == ([], [])


def test_agreement_allows_actual_later_repetition():
    a = Agreement()
    assert a.update([Word("yes", 0, .4)], final=True)[0]
    assert a.update([Word("yes", 2, 2.4)], final=True)[0]


@pytest.fixture(scope="module")
def router():
    return LanguageRouter()


@pytest.mark.parametrize("text,expected", [("Good morning, how can I help you?", "en"), ("Hola, necesito un turno médico para mañana.", "es"), ("Let me check our availability.", "en"), ("Perfecto, muchas gracias por su ayuda.", "es")])
def test_language_classification(router, text, expected):
    assert router.classify(text) == expected


def test_ambiguous_word_without_evidence_is_withheld(router):
    assert router.classify("No", None, 0) is None


def test_name_uses_acoustic_context_instead_of_switching_panel(router):
    assert router.classify("YouTube", "es", .95) == "es"


def test_sentence_switch_not_published_twice(router):
    words = [Word(" Good morning.", 0, 1), Word(" Hola, necesito un turno médico.", 1, 3)]
    routed = router.route(words, "en", .8)
    assert [language for language, _ in routed] == ["en", "es"]
    assert sum(len(w) for _, w in routed) == len(words)


def test_history_disabled_stores_nothing(tmp_path):
    h = History()
    h.add(Caption("1", "system", "en", "Sensitive", 0, 1, True))
    assert not h.items
    assert not list(tmp_path.iterdir())


def test_history_retention_and_exports(tmp_path):
    h = History(True, retention_minutes=1)
    h.add(Caption("1", "system", "en", "Hello", 0, 1, True))
    h.add(Caption("2", "microphone", "es", "Hola", 90, 91, True))
    h.add(Caption("3", "system", "en", "Welcome", 80, 82, True))
    assert len(h.items) == 2
    assert [c.id for c in h.ordered()] == ["3", "2"]
    for extension in ("txt", "srt", "json"):
        path = tmp_path / ("captions." + extension)
        h.export(path)
        assert path.stat().st_size > 0
    assert "00:01:20,000 --> 00:01:22,000" in (tmp_path / "captions.srt").read_text(encoding="utf-8-sig")
    assert json.loads((tmp_path / "captions.json").read_text(encoding="utf-8"))["schema"] == 1


def test_history_never_keeps_partials():
    h = History(True, max_items=3)
    for i in range(10):
        h.add(Caption(str(i), "system", "en", "hello", i, i + .5, i % 2 == 0))
    assert len(h.items) == 3
    assert all(c.final for c in h.items)


@pytest.mark.parametrize("seconds,expected", [(0, "00:00:00,000"), (3661.123, "01:01:01,123"), (-2, "00:00:00,000"), (.9996, "00:00:01,000")])
def test_srt_time(seconds, expected):
    assert srt_time(seconds) == expected


def test_settings_round_trip_and_corruption(tmp_path):
    path = tmp_path / "settings.json"
    value = Settings(history_enabled=False, opacity=.78)
    value.save(path)
    assert Settings.load(path).opacity == .78
    path.write_text("invalid")
    assert Settings.load(path).history_enabled is False


def test_profiles_change_real_engine_parameters():
    value = Settings()
    signatures = []
    for profile in PROFILES:
        value.apply_profile(profile)
        signatures.append((value.model, value.interval, value.beam_size))
    assert len(set(signatures)) == 3


@pytest.mark.parametrize("value", ["O", "Ctrl+Alt", "Ctrl+Alt+INVALID"])
def test_invalid_hotkeys(value):
    with pytest.raises(ValueError):
        parse_hotkey(value)
