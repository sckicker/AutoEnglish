# app/scoring_utils.py
import os
import whisper
import librosa
import soundfile as sf
import re
import numpy as np # librosa.effects.split 返回 numpy 数组
from jiwer import wer
import logging # 使用 Flask 的 logger

# --- 全局模型变量 ---
whisper_model = None

# --- 日志记录器 ---
# 获取 Flask 应用的 logger (在函数中通过 current_app 获取)
# logger = logging.getLogger(__name__) # 如果想用独立 logger
from flask import current_app # 导入 current_app

# --- 模型加载函数 (可以在 app/__init__.py 中调用) ---
def load_whisper_model(model_name):
    """加载 Whisper 模型"""
    global whisper_model
    if whisper_model is None:
        try:
            # 自动检测设备 (GPU 或 CPU)
            whisper_model = whisper.load_model(model_name)
            current_app.logger.info(f"Whisper model '{model_name}' loaded successfully.")
        except Exception as e:
            current_app.logger.error(f"Failed to load Whisper model '{model_name}': {e}", exc_info=True)
            whisper_model = None # 标记加载失败
    return whisper_model

# --- 文本标准化 ---
def normalize_text(text):
    """对文本进行标准化处理，用于评分比较。"""
    if not isinstance(text, str): return "" # 处理 None 或其他类型
    text = text.lower()
    text = re.sub(r"[^\w\s'-]", "", text)  # 保留字母、数字、空格、撇号、连字符
    text = re.sub(r"\s+", " ", text)       # 合并多个空格为一个
    text = text.strip()
    return text

# --- 音频转文本 ---
def transcribe_audio(audio_path):
    """使用加载的 Whisper 模型将音频转为文本。"""
    global whisper_model
    if whisper_model is None:
        current_app.logger.error("Whisper model is not loaded. Cannot transcribe.")
        raise ValueError("Whisper model not loaded") # 抛出异常让调用者处理

    try:
        # 检查音频文件是否存在且可读
        if not os.path.exists(audio_path):
             raise FileNotFoundError(f"Audio file not found at {audio_path}")

        # 可以选择性地添加音频检查（16kHz, Mono），但 Whisper 内部通常能处理
        # check_audio(audio_path) # 如果需要

        current_app.logger.info(f"Transcribing audio file: {audio_path}")
        # temperature=0.0 使输出更具确定性
        result = whisper_model.transcribe(audio_path, language='en', temperature=0.0, fp16=False) # fp16=False for CPU stability
        recognized_text = result.get('text', '') # 获取文本，如果 key 不存在则返回空字符串
        current_app.logger.info(f"Transcription result: {recognized_text}")
        return recognized_text
    except Exception as e:
        current_app.logger.error(f"Whisper transcription failed for {audio_path}: {e}", exc_info=True)
        raise # 重新抛出异常，让调用者知道出错了

# --- 计算准确率 (基于 1 - WER) ---
def calculate_accuracy_score(reference_text, transcribed_text):
    """计算基于 WER 的准确率分数 (0-100)。"""
    norm_reference = normalize_text(reference_text)
    norm_transcribed = normalize_text(transcribed_text)

    if not norm_reference: # 如果标准文本为空，无法计算 WER
        current_app.logger.warning("Reference text is empty after normalization. Cannot calculate WER.")
        return 0.0 # 或者返回一个特殊值

    # 如果识别文本为空，错误率视为 100% (或根据策略调整)
    if not norm_transcribed:
        current_app.logger.warning("Transcribed text is empty after normalization. Assuming 100% WER.")
        return 0.0 # 准确率为 0

    try:
        error_rate = wer(norm_reference, norm_transcribed)
        current_app.logger.info(f"WER calculation: {error_rate:.4f}")
        # 准确率 = 1 - 错误率。WER 可能 > 1，所以用 max(0, ...) 限制最低为 0
        accuracy = max(0.0, 1.0 - error_rate)
        return round(accuracy * 100, 2) # 转为百分制，保留两位小数
    except Exception as e:
        current_app.logger.error(f"Error calculating WER: {e}", exc_info=True)
        return 0.0 # 计算出错时返回 0

# --- 计算语速 (WPS) ---
def calculate_speech_rate_wps(audio_path, transcribed_text):
    """计算语速 (Words Per Second)。"""
    try:
        y, sr = librosa.load(audio_path, sr=16000)
        duration = librosa.get_duration(y=y, sr=sr)
        current_app.logger.info(f"[INFO] Audio Duration: {duration:.2f} seconds")
        word_count = len(transcribed_text.split())
        speech_rate = word_count / duration if duration > 0 else 0
        return round(speech_rate, 2)
    except Exception as e:
        current_app.logger.error(f"Error calculating speech rate for {audio_path}: {e}", exc_info=True)
        return 0.0

# --- 语速打分 ---
def rate_speech_speed_score(wps: float) -> float:
    """根据 WPS 评估语速，给出一个 0-100 的分数。"""
    ideal_min = 1.8
    ideal_max = 2.8
    lower_bound_wps = 0.8 # 低于此值给最低分
    upper_bound_wps = 3.8 # 高于此值给最低分
    min_score = 50.0      # 最低分

    if wps < ideal_min:
        if wps <= lower_bound_wps: return min_score
        else: score = min_score + (wps - lower_bound_wps) * (100 - min_score) / (ideal_min - lower_bound_wps); return round(max(min_score, score), 2)
    elif ideal_min <= wps <= ideal_max: return 100.0
    else: # wps > ideal_max
        if wps >= upper_bound_wps: return min_score
        else: score = 100 - (wps - ideal_max) * (100 - min_score) / (upper_bound_wps - ideal_max); return round(max(min_score, score), 2)

# --- 计算流畅度分数 ---
def calculate_fluency_score(audio_path: str, sr: int = 16000, top_db: int = 30, long_pause_threshold: float = 1.5, penalty_per_long_pause: int = 15) -> float:
    """计算流畅度分数 (0-100)，基于说话密度和长停顿惩罚。"""
    try:
        y, current_sr = librosa.load(audio_path, sr=sr)
        if len(y) == 0: current_app.logger.warning(f"Fluency: Audio empty: {audio_path}"); return 0.0
        total_duration = librosa.get_duration(y=y, sr=current_sr)
        if total_duration == 0: current_app.logger.warning(f"Fluency: Zero duration: {audio_path}"); return 0.0

        intervals = librosa.effects.split(y, top_db=top_db) # 查找非静音片段

        if intervals.size == 0: speaking_duration = 0.0
        else: speaking_duration = sum((end - start) for start, end in intervals) / current_sr
        speaking_ratio = speaking_duration / total_duration

        base_score = min(100, speaking_ratio * 125) # 基础分，80% 说话密度是 100 分

        long_pause_count = 0
        if len(intervals) > 1:
            for i in range(len(intervals) - 1):
                pause_duration = (intervals[i + 1][0] - intervals[i][1]) / current_sr
                if pause_duration > long_pause_threshold: long_pause_count += 1

        final_score = base_score - (long_pause_count * penalty_per_long_pause)
        final_score = max(0.0, min(100.0, final_score)) # Clip score to 0-100

        current_app.logger.info(f"Fluency score for {audio_path}: {final_score:.2f} (Ratio: {speaking_ratio:.2f}, Long Pauses: {long_pause_count})")
        return round(final_score, 2)

    except Exception as e:
        current_app.logger.error(f"Error calculating fluency for {audio_path}: {e}", exc_info=True)
        return 0.0

# --- 计算最终总分 ---
def calculate_final_score(accuracy, speech_rate_wps, fluency_score, weights=None):
    """根据各分项和权重计算最终总分。"""
    if weights is None:
        weights = {'accuracy': 0.7, 'fluency': 0.2, 'speed': 0.1} # 默认权重

    speech_rate_score = rate_speech_speed_score(speech_rate_wps)
    current_app.logger.info(f"Intermediate Scores -> Accuracy: {accuracy:.2f}, Fluency: {fluency_score:.2f}, Speed Score: {speech_rate_score:.2f}")

    final_score = (accuracy * weights['accuracy'] +
                   fluency_score * weights['fluency'] +
                   speech_rate_score * weights['speed'])

    # 确保最终分数在 0-100
    final_score = max(0.0, min(100.0, final_score))
    current_app.logger.info(f"Calculated final score: {final_score:.2f}")
    return round(final_score, 2)

# --- 主评估函数 ---
def evaluate_audio_recording(audio_path, reference_text):
    """封装音频评估流程，返回包含所有指标和分数的字典。"""
    if not os.path.exists(audio_path):
         raise FileNotFoundError(f"Audio file not found for evaluation: {audio_path}")
    if not reference_text:
         raise ValueError("Reference text cannot be empty for evaluation.")

    # 1. 转文本
    transcribed_text = transcribe_audio(audio_path) # 内部会检查模型是否加载

    # 2. 计算各项指标
    accuracy = calculate_accuracy_score(reference_text, transcribed_text)
    speech_rate = calculate_speech_rate_wps(audio_path, transcribed_text)
    fluency_score = calculate_fluency_score(audio_path)

    # 3. 计算总分
    final_score = calculate_final_score(accuracy, speech_rate, fluency_score)

    # 4. 准备返回结果
    return {
        "recognized_text": transcribed_text,
        "accuracy": accuracy,
        "speech_rate_wps": speech_rate,
        "fluency_score": fluency_score,
        "final_score": final_score,
        "reference_text_normalized": normalize_text(reference_text), # 可选返回
        "recognized_text_normalized": normalize_text(transcribed_text) # 可选返回
    }