import whisper
from jiwer import wer
import librosa
from librosa.effects import split
import re

# 初始化 Whisper 模型
model = whisper.load_model("small")

# 文本标准化处理
def normalize_text(text):
    text = text.lower()  # 小写
    text = re.sub(r"[^\w\s]", "", text)  # 去掉标点，只保留单词和空格
    text = re.sub(r"\s+", " ", text)  # 多个空格合成一个空格
    text = text.strip()  # 去掉首尾空格
    return text

# 音频转文本
def transcribe_audio(audio_path):
    result = model.transcribe(audio_path, temperature=0)
    return result['text']

# 计算 WER（词错误率）
def calculate_wer(reference_text, transcribed_text):
    # 在计算准确率之前，先处理 reference 和 transcribed 文本
    norm_reference = normalize_text(reference_text)
    norm_transcribed = normalize_text(transcribed_text)
    error_rate = wer(norm_reference, norm_transcribed)
    accuracy = 1 - error_rate
    return accuracy * 100  # 转换为百分制

# 计算语速（words per second）
def calculate_speech_rate(audio_path, transcribed_text):
    y, sr = librosa.load(audio_path, sr=16000)
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"[INFO] Audio Duration: {duration:.2f} seconds")
    word_count = len(transcribed_text.split())
    speech_rate = word_count / duration if duration > 0 else 0
    return round(speech_rate, 2)

# 计算流畅度（基于非静音比例）
def calculate_fluency(audio_path):
    y, sr = librosa.load(audio_path, sr=16000)
    intervals = split(y, top_db=30)
    non_silence = sum([(end - start) for start, end in intervals])
    total = len(y)
    non_silence_ratio = non_silence / total
    fluency_score = round(min(non_silence_ratio * 120, 100), 2)  # 非静音比例映射到 100分以内
    return fluency_score

# 语速评分
def rate_speech_speed(wps):
    if wps < 1.0:
        return max(50, 100 - (1.0 - wps) * 20)
    elif 1.0 <= wps < 1.5:
        return round(80 + (wps - 1.0) * 40, 2)
    elif 1.5 <= wps <= 2.5:
        return 100
    elif 2.5 < wps <= 3.0:
        return round(100 - (wps - 2.5) * 40, 2)
    else:
        return max(50, 100 - (wps - 3.0) * 20)

# 测试函数
def evaluate_audio(audio_path, reference_text):
    transcribed_text = transcribe_audio(audio_path)
    print(f"Recognized Text: {transcribed_text}")

    accuracy = calculate_wer(reference_text, transcribed_text)
    print(f"Accuracy: {accuracy}%")

    speech_rate = calculate_speech_rate(audio_path, transcribed_text)
    print(f"Speech Rate: {speech_rate} words/sec")

    fluency_score = calculate_fluency(audio_path)
    print(f"Fluency Score: {fluency_score}/100")

    return accuracy, speech_rate, fluency_score

# 计算最终得分
def calculate_final_score(accuracy, speech_rate, fluency_score):
    speech_rate_score = rate_speech_speed(speech_rate)

    final_score = (accuracy * 0.7) + (speech_rate_score * 0.1) + (fluency_score * 0.2)
    return round(final_score, 2)

# 示例测试
audio_file = "data/user_1_lesson_13.webm"
#audio_file = "data/lesson_13.wav"
reference_text = '''
Why will the police have a difficult time?
The Greenwood Boys are a group of pop singers.
At present, they are visiting all parts of the country.
They will be arriving here tomorrow.
They will be coming by train and most of the young people in the town will be meeting them at the station.
Tomorrow evening they will be singing at the Workers' Club.
The Greenwood Boys will be staying for five days.
During this time, they will give five performances.
As usual, the police will have a difficult time.
They will be trying to keep order.
It is always the same on these occasions.
'''

accuracy, speech_rate, fluency_score = evaluate_audio(audio_file, reference_text)

final_score = calculate_final_score(accuracy, speech_rate, fluency_score)
print(f"🏁 Final Score: {final_score:.2f}/100")
