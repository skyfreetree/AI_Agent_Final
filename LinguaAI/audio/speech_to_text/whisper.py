import io
import os
import subprocess
import types

import speech_recognition as sr
from faster_whisper import WhisperModel
from pydub import AudioSegment
from LinguaAI.my_logging import logger

from audio.utils import Singleton, timed
from LinguaAI.database.scene_db import ChatDatabase


db = ChatDatabase()
db_settings = db.get_settings()
# 设置环境变量
os.environ["OPENAI_API_KEY"] = (
    db_settings["api_key"] if db_settings["api_key"] != "" else "empty"
)
os.environ["OPENAI_BASE_URL"] = db_settings["host"]
config = types.SimpleNamespace(
    **{
        "model": os.getenv("LOCAL_WHISPER_MODEL", "medium"),
        "language": "en",
    }
)

# Whisper use a shorter version for language code. Provide a mapping to convert
# from the standard language code to the whisper language code.


class Whisper(Singleton):
    def __init__(self, use="local"):
        super().__init__()
        if use == "local":
            try:
                subprocess.check_output(["nvidia-smi"])
                device = "cuda"
            except Exception:
                device = "cpu"
            logger.info(f"Loading [Local Whisper] model: [{config.model}]({device}) ...")
            self.model = WhisperModel(
                model_size_or_path=config.model,
                device="auto",
                download_root=None,
            )
        self.recognizer = sr.Recognizer()
        self.use = use

    @timed
    def transcribe(self, audio_bytes, platform, prompt="", language=None, suppress_tokens=[-1]):
        logger.info("Transcribing audio...")
        if platform == "web":
            audio = self._convert_webm_to_wav(audio_bytes, self.use == "local")
        elif platform == "twilio":
            audio = self._ulaw_to_wav(audio_bytes, self.use == "local")
        else:
            audio = self._convert_bytes_to_wav(audio_bytes, self.use == "local")
        if self.use == "local":
            return self._transcribe(audio, prompt, suppress_tokens=suppress_tokens)
        elif self.use == "api":
            return self._transcribe_api(audio, prompt)

    def _transcribe(self, audio, prompt="输入大概率是中英文混合的", language=None, suppress_tokens=[-1]):
        segs, _ = self.model.transcribe(
            audio,
            language=language,
            vad_filter=True,
            initial_prompt=prompt,
            suppress_tokens=suppress_tokens,
        )
        text = " ".join([seg.text for seg in segs])
        return text

    def _transcribe_api(self, audio, prompt=""):
        text = self.recognizer.recognize_openai(
            audio,
            prompt="输入很可能是中英文混合的"
        )
        return text

    def _convert_webm_to_wav(self, webm_data, local=True):
        webm_audio = AudioSegment.from_file(io.BytesIO(webm_data))
        wav_data = io.BytesIO()
        webm_audio.export(wav_data, format="wav")
        if local:
            return wav_data
        with sr.AudioFile(wav_data) as source:
            audio = self.recognizer.record(source)
        return audio

    def _convert_bytes_to_wav(self, audio_bytes, local=True):
        if local:
            audio = io.BytesIO(sr.AudioData(audio_bytes, 44100, 2).get_wav_data())
            return audio
        return sr.AudioData(audio_bytes, 44100, 2)

    def _ulaw_to_wav(self, audio_bytes, local=True):
        sound = AudioSegment(data=audio_bytes, sample_width=1, frame_rate=8000, channels=1)

        audio = io.BytesIO()
        sound.export(audio, format="wav")
        if local:
            return audio

        return sr.AudioData(audio_bytes, 8000, 1)
