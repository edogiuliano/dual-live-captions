import os
from pathlib import Path
import numpy as np
import pytest
from faster_whisper.audio import decode_audio
from dual_live_captions.asr import FasterWhisperEngine
from dual_live_captions.settings import Settings
from dual_live_captions.models import cached_model
from dual_live_captions.pipeline import CaptionPipeline
from dual_live_captions.audio import AudioFrame
from dual_live_captions.language import LanguageRouter

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("DLC_INTEGRATION") != "1", reason="Set DLC_INTEGRATION=1 for real local inference")]


@pytest.fixture(scope="module")
def engine():
    model = cached_model("small")
    if not model:
        pytest.skip("small not downloaded")
    return FasterWhisperEngine(model, Settings())


@pytest.mark.parametrize("name,language", [("english", "en"), ("spanish", "es"), ("short_en", "en"), ("short_es", "es")])
def test_actual_audio_language(engine, name, language):
    path = Path(__file__).parents[1] / "audio_samples" / (name + ".wav")
    result = engine.transcribe(decode_audio(str(path), sampling_rate=16000))
    assert result.words
    groups = LanguageRouter().route(result.words, result.language, result.confidence)
    assert groups and all(lang == language for lang, _ in groups)


def test_silence_pipeline_does_not_call_asr(engine):
    events, metrics = [], []
    pipeline = CaptionPipeline(engine, Settings(), events.append, metrics.append)
    for i in range(200):
        pipeline.feed(AudioFrame("test", np.zeros(512, np.float32), i * .032, 0))
    assert not [c for c in events if c.text]
    assert not metrics
