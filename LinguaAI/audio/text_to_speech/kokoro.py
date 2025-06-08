from kokoro import KPipeline
import numpy as np
import io
import soundfile as sf

class Kokoro():
    def __init__(self):
        super().__init__()
        self.voice_id = 'af_heart'
        en_pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
        def en_callable(text):
            return next(en_pipeline(text, voice=self.voice_id)).phonemes
        self.zh_pipeline = KPipeline(lang_code='z', repo_id='hexgrad/Kokoro-82M', en_callable=en_callable)
        self.en_pipeline = en_pipeline
        
    async def generate_audio(self, text: str, is_english: bool):
        if is_english:
            generator = self.en_pipeline(text, voice=self.voice_id, speed=1.0)
        else:
            generator = self.zh_pipeline(text, voice=self.voice_id, speed=1.0)
        
        # 拼接所有段落的音频
        audio_list = []
        for result in generator:
            audio = result.audio.cpu().numpy()
            audio_list.append(audio)
        if not audio_list:
            raise ValueError("No audio generated")
        wav = np.concatenate(audio_list)
        
        wav_bytes = io.BytesIO()
        sf.write(wav_bytes, wav, 24000, format='WAV')  # 让soundfile自动处理类型
        wav_bytes.seek(0)
        return wav_bytes 