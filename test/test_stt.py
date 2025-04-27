import whisper
import librosa
import soundfile as sf
import re
from librosa.effects import split
from jiwer import wer

# 加载 Whisper 小模型
model = whisper.load_model("small")


# 音频检测函数
def check_audio(audio_path):
    with sf.SoundFile(audio_path) as f:
        sr = f.samplerate
        channels = f.channels
    if sr != 16000 or channels != 1:
        print("[WARN] Audio is not 16kHz Mono. Recommend converting before recognition.")


# 文本标准化处理（增强版）
def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s'-]", "", text)  # 保留撇号和连字符
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


# 音频转文本
def transcribe_audio(audio_path):
    result = model.transcribe(audio_path, temperature=0.0)
    return result['text']


# 计算准确率
def calculate_wer(reference_text, transcribed_text):
    norm_reference = normalize_text(reference_text)
    norm_transcribed = normalize_text(transcribed_text)
    error_rate = wer(norm_reference, norm_transcribed)
    accuracy = 1 - error_rate
    return accuracy * 100  # 百分制


# 计算语速
def calculate_speech_rate(audio_path, transcribed_text):
    y, sr = librosa.load(audio_path, sr=16000)
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"[INFO] Audio Duration: {duration:.2f} seconds")
    word_count = len(transcribed_text.split())
    speech_rate = word_count / duration if duration > 0 else 0
    return round(speech_rate, 2)


# 语速打分（基于区间映射）
def rate_speech_speed_revised(wps: float) -> float:
    """
    根据每秒词数 (WPS) 评估语速，给出一个 0-100 的分数。
    这个修订版本调整了理想语速范围，并修复了边界不连续问题。
    - 理想范围 (100分): 1.8 到 2.8 WPS (108-168 WPM)
    - 分数从理想范围向两侧平滑下降。
    - 考虑将最低分设为 0 或一个较低的值（这里仍保留 50 作为示例）。
    """

    ideal_min = 1.8
    ideal_max = 2.8

    # 低于理想范围
    if wps < ideal_min:
        # 从 ideal_min (100分) 向下递减
        # 设定一个下限点，例如在 0.8 WPS 时达到 50 分
        lower_bound_wps = 0.8
        if wps <= lower_bound_wps:
            return 50.0
        else:
            # 线性下降: 从 (lower_bound_wps, 50) 到 (ideal_min, 100)
            score = 50 + (wps - lower_bound_wps) * (100 - 50) / (ideal_min - lower_bound_wps)
            return round(max(50.0, score), 2)  # 确保不低于50

    # 在理想范围内
    elif ideal_min <= wps <= ideal_max:
        return 100.0

    # 高于理想范围
    else:  # wps > ideal_max
        # 从 ideal_max (100分) 向下递减
        # 设定一个上限点，例如在 3.8 WPS 时达到 50 分
        upper_bound_wps = 3.8
        if wps >= upper_bound_wps:
            return 50.0
        else:
            # 线性下降: 从 (ideal_max, 100) 到 (upper_bound_wps, 50)
            score = 100 - (wps - ideal_max) * (100 - 50) / (upper_bound_wps - ideal_max)
            return round(max(50.0, score), 2)  # 确保不低于50


# 计算流畅度（基于停顿分析）
def calculate_simple_fluency(audio_path: str,
                             sr: int = 16000,
                             top_db: int = 30,
                             long_pause_threshold: float = 1.5,
                             penalty_per_long_pause: int = 15) -> float:
    """
    计算一个更简洁的音频流畅度分数 (0-100)。

    主要基于说话密度和长停顿次数进行评估。

    Args:
        audio_path (str): 音频文件路径。
        sr (int): 加载音频时使用的采样率。默认为 16000 Hz。
        top_db (int): 用于区分语音和静音的能量阈值 (dB)。
                      低于最大能量 top_db dB 的部分被视为静音。
                      数值越小，检测静音越严格。可能需要根据音频调整。
                      默认值为 30。
        long_pause_threshold (float): 定义为“长停顿”的最小秒数。
                                     超过此时间的停顿会被计入惩罚。
                                     默认值为 1.5 秒。
        penalty_per_long_pause (int): 每次检测到长停顿时扣除的分数。
                                      默认值为 15 分。

    Returns:
        float: 计算得到的流畅度分数 (0-100)，保留两位小数。
               如果无法处理音频（如文件不存在或为空），返回 0.0。
    """
    try:
        # 1. 加载音频
        y, current_sr = librosa.load(audio_path, sr=sr)

        # 检查音频是否有效
        if len(y) == 0:
            print(f"Warning: Audio file {audio_path} is empty or could not be loaded correctly.")
            return 0.0

        total_duration = librosa.get_duration(y=y, sr=current_sr)
        if total_duration == 0:
            print(f"Warning: Audio file {audio_path} has zero duration.")
            return 0.0

        # 2. 查找非静音（语音）片段
        #    intervals 是一个包含 [start, end] 时间戳（样本点索引）的列表
        intervals = librosa.effects.split(y, top_db=top_db)

        # 3. 计算说话总时长和说话密度
        if intervals.size == 0:  # 如果没有检测到任何语音
            speaking_duration = 0.0
        else:
            speaking_duration = sum((end - start) for start, end in intervals) / current_sr

        speaking_ratio = speaking_duration / total_duration

        # 基于说话密度的基础分 (0-100)
        # 这里使用一个简单的映射，例如让 70% 的密度对应大约 85-90 分
        # 你可以调整这个映射关系，比如使用非线性映射
        base_score = min(100, speaking_ratio * 125)  # 乘以 125 使得 ratio 0.8 -> 100分

        # 4. 计算长停顿次数
        long_pause_count = 0
        if len(intervals) > 1:
            for i in range(len(intervals) - 1):
                # 计算两个语音片段之间的停顿时间（秒）
                pause_duration = (intervals[i + 1][0] - intervals[i][1]) / current_sr
                if pause_duration > long_pause_threshold:
                    long_pause_count += 1

        # 5. 计算最终得分
        # 从基础分中扣除长停顿的惩罚
        final_score = base_score - (long_pause_count * penalty_per_long_pause)

        # 确保分数在 0 到 100 之间
        final_score = max(0.0, min(100.0, final_score))

        return round(final_score, 2)

    except Exception as e:
        print(f"Error processing audio file {audio_path}: {e}")
        # 发生错误时返回 0 分或可以抛出异常
        return 0.0


# --- 示例用法 ---
# 假设你有一个名为 "test_audio.wav" 的文件
# audio_file = "test_audio.wav"
# fluency = calculate_simple_fluency(audio_file)
# print(f"The calculated fluency score is: {fluency}")

# 你也可以调整参数
# fluency_strict = calculate_simple_fluency(audio_file, top_db=25, long_pause_threshold=1.0, penalty_per_long_pause=20)
# print(f"Stricter fluency score: {fluency_strict}")

# 分数 clip 保证在 0-100
def safe_clip(score):
    return max(0, min(score, 100))


# 计算最终总分
def calculate_final_score(accuracy, speech_rate, fluency_score):
    speech_rate_score = rate_speech_speed_revised(speech_rate)
    print(f'speech_rate_score:{speech_rate_score}')
    final_score = (accuracy * 0.7) + (fluency_score * 0.2) + (speech_rate_score * 0.1)
    return safe_clip(round(final_score, 2))


# 主流程封装
def evaluate_audio(audio_path, reference_text):
    # 1. 音频预检查
    #check_audio(audio_path)

    # 2. Whisper转文本
    transcribed_text = transcribe_audio(audio_path)
    print(f"Recognized Text: {transcribed_text}")

    # 3. 指标计算
    accuracy = calculate_wer(reference_text, transcribed_text)
    print(f"Accuracy: {accuracy:.2f}%")

    speech_rate = calculate_speech_rate(audio_path, transcribed_text)
    print(f"Speech Rate: {speech_rate} words/sec")

    fluency_score = calculate_simple_fluency(audio_path)
    print(f"Fluency Score: {fluency_score}/100")

    # 4. 综合得分
    final_score = calculate_final_score(accuracy, speech_rate, fluency_score)
    print(f"🏁 Final Score: {final_score}/100")

    return {
        "recognized_text": transcribed_text,
        "accuracy": round(accuracy, 2),
        "speech_rate": speech_rate,
        "fluency_score": fluency_score,
        "final_score": final_score
    }

audio_file = "data/user_1_lesson_13.webm"

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

result = evaluate_audio(audio_file, reference_text)
print(result)