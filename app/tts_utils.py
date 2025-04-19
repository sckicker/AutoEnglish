# app/tts_utils.py
from TTS.api import TTS as APITTS
import torch
import os
import logging
import time
from flask import current_app

log = logging.getLogger(__name__)
tts_engine_instance: APITTS | None = None

# --- 从配置读取默认值 ---
# 注意: 默认值在这里设置意义不大，因为主要依赖 Flask Config
DEFAULT_TTS_MODEL = "tts_models/en/ljspeech/tacotron2-DDC"

def initialize_tts_model() -> APITTS | None:
    """(懒加载) 初始化并返回 TTS API 类的实例 (Tacotron2 + Vocoder)。"""
    global tts_engine_instance
    if tts_engine_instance is not None:
        log.debug("Returning cached TTS engine instance.")
        return tts_engine_instance

    log.info("Initializing TTS engine (using TTS.api.TTS for Tacotron2 + Vocoder)...")
    try:
        model_name = current_app.config.get('TTS_MODEL', DEFAULT_TTS_MODEL)
        use_cuda = current_app.config.get('TTS_USE_CUDA', False)
        device = "cuda" if use_cuda and torch.cuda.is_available() else "cpu"
        # ... (日志和设备检查) ...
        log.info(f"Selected TTS Model: {model_name}")
        log.info(f"Target device: {device}")

        # --- 使用 TTS API 类初始化 (包含声码器) ---
        tts_engine = APITTS(
            model_name=model_name,
            progress_bar=True
        )
        tts_engine.to(device)
        # ------------------------------------------

        log.info(f"TTS engine ({model_name}) initialized successfully on {device}.")
        tts_engine_instance = tts_engine
        return tts_engine_instance
    except Exception as e:
        log.error(f"Failed to initialize TTS engine for model '{model_name}': {e}", exc_info=True)
        tts_engine_instance = None
        return None

def get_audio_filename(lesson_number: int) -> str | None:
    """生成并确保音频缓存目录存在，返回标准音频文件路径。(保持不变)"""
    cache_dir_base = current_app.config.get('TTS_AUDIO_CACHE_DIR')
    if not cache_dir_base:
        log.error("TTS_AUDIO_CACHE_DIR is not set in Flask config.")
        return None
    try:
        if not os.path.isabs(cache_dir_base):
             cache_dir = os.path.join(current_app.instance_path, cache_dir_base)
        else:
             cache_dir = cache_dir_base
        os.makedirs(cache_dir, exist_ok=True)
        log.debug(f"Ensured TTS audio cache directory exists: {cache_dir}")
    except OSError as e:
        log.error(f"Could not create or access TTS audio cache directory '{cache_dir}': {e}")
        return None
    filename = f"lesson_{lesson_number}.wav"
    full_path = os.path.join(cache_dir, filename)
    return full_path


def generate_and_save_audio_if_not_exists(lesson_number: int, text: str, language: str = None, force: bool = False) -> str | None:
    """
    Generates TTS audio for the given text and saves it if it doesn't exist or if forced.

    This version uses the configured TTS engine (initialized lazily if needed),
    handles file existence checks, force regeneration, error handling,
    and conditional parameter passing for single vs. multi-lingual models.

    Args:
        lesson_number (int): The lesson number, used for naming the output file.
        text (str): The text content to synthesize.
        language (str, optional): The language code (e.g., 'en', 'zh-cn').
                                   Required for multi-lingual models like XTTS.
                                   Should be None or omitted for single-language models.
        force (bool, optional): If True, delete the existing audio file before generating.
                                Defaults to False.

    Returns:
        str | None: The absolute path to the saved audio file on success, otherwise None.
    """
    output_filepath = get_audio_filename(lesson_number)
    if not output_filepath:
        log.error(f"Lesson {lesson_number}: Could not determine output filepath. Check TTS_AUDIO_CACHE_DIR config.")
        return None # Cannot proceed without a valid path

    # --- Handle Force Regeneration ---
    if force and os.path.exists(output_filepath):
        log.info(f"Lesson {lesson_number}: Force flag is set. Attempting to remove existing file: {output_filepath}")
        try:
            os.remove(output_filepath)
            log.info(f"Lesson {lesson_number}: Successfully removed existing file.")
        except OSError as e:
            log.error(f"Lesson {lesson_number}: Could not remove existing file {output_filepath} despite force flag: {e}")
            # Depending on desired behavior, you might stop here or continue
            # return None # Option: Stop if force removal fails
    # --------------------------------

    # --- Check if File Exists (after potential force removal) ---
    if os.path.exists(output_filepath):
        log.info(f"Lesson {lesson_number}: Audio file found in cache, skipping generation: {output_filepath}")
        return output_filepath
    # ---------------------------------------------------------

    log.info(f"Lesson {lesson_number}: Audio file not found or forced regeneration. Starting synthesis...")

    # --- Get or Initialize TTS Engine ---
    tts_engine = initialize_tts_model() # Lazy initialization
    if tts_engine is None:
        log.error(f"Lesson {lesson_number}: Cannot generate audio, TTS engine failed to initialize.")
        return None
    # ---------------------------------

    # --- Validate Input Text ---
    if not text or not text.strip():
        log.warning(f"Lesson {lesson_number}: No text provided or text is empty. Cannot generate audio.")
        return None # Cannot synthesize empty text
    # -------------------------

    # --- Determine Model Type for Parameter Handling ---
    # Check based on model name in config or loaded engine property
    model_name_from_config = current_app.config.get('TTS_MODEL', '')
    is_multilingual = 'multilingual' in model_name_from_config.lower() or \
                      'xtts' in model_name_from_config.lower() or \
                      (hasattr(tts_engine, 'is_multi_lingual') and tts_engine.is_multi_lingual)

    log.info(f"Lesson {lesson_number}: Synthesizing (model type: {'Multi-lingual' if is_multilingual else 'Single-language'}, length: {len(text)} chars)")
    start_time = time.time()

    # --- Prepare arguments for tts_to_file ---
    tts_kwargs = {
        "text": text,
        "file_path": output_filepath,
        # Add parameters common to most models if needed, e.g., speaker control if model supports it
    }

    if is_multilingual:
        if language:
            tts_kwargs["language"] = language
            tts_kwargs["split_sentences"] = True # Generally good for XTTS
            log.debug(f"Lesson {lesson_number}: Passing 'language={language}' and 'split_sentences=True' to multi-lingual model.")
        else:
            log.error(f"Lesson {lesson_number}: Multi-lingual model requires 'language' parameter, but none provided.")
            return None # Stop if language is missing for multi-lingual model
    else:
        # For single-language models (like Tacotron2, VITS LJSpeech), DO NOT pass 'language'
        # 'split_sentences' might also not be supported or beneficial
        log.debug(f"Lesson {lesson_number}: Not passing 'language' or 'split_sentences' to single-language model.")
    # ------------------------------------------

    # --- Perform TTS Synthesis ---
    try:
        log.debug(f"Lesson {lesson_number}: Calling tts_to_file with args: {tts_kwargs}")
        tts_engine.tts_to_file(**tts_kwargs)

        # --- Verify Output File ---
        if not os.path.exists(output_filepath) or os.path.getsize(output_filepath) == 0:
             log.error(f"Lesson {lesson_number}: TTS call succeeded but output file is missing or empty: {output_filepath}")
             # Attempt cleanup just in case an empty file was created
             if os.path.exists(output_filepath):
                 try: os.remove(output_filepath)
                 except OSError: pass
             return None # Generation failed if file isn't valid
        # ------------------------

        total_time = time.time() - start_time
        log.info(f"Lesson {lesson_number}: Successfully generated and saved audio in {total_time:.2f}s to {output_filepath}.")
        return output_filepath # Return the path on success

    # --- Specific Error Handling ---
    except RuntimeError as e:
        log.error(f"Lesson {lesson_number}: RUNTIME ERROR during TTS synthesis: {e}", exc_info=False)
        if "stack expects each tensor to be equal size" in str(e):
             log.error(f"Lesson {lesson_number}: Model ({model_name_from_config}) likely struggled with sequence processing. Consider using XTTS v2 if issues persist.")
    except ValueError as e:
         log.error(f"Lesson {lesson_number}: VALUE ERROR during TTS synthesis: {e}", exc_info=False)
         log.error(f"Lesson {lesson_number}: Check if parameters passed ({tts_kwargs}) are correct for model '{model_name_from_config}'.")
    except Exception as e:
        log.error(f"Lesson {lesson_number}: Unexpected error during TTS synthesis: {e}", exc_info=True) # Log full traceback for unexpected errors

    # --- Cleanup and Return None on Error ---
    log.error(f"Lesson {lesson_number}: Synthesis failed.")
    if os.path.exists(output_filepath): # Attempt to clean up potentially corrupted/empty file
        try:
            os.remove(output_filepath)
            log.debug(f"Lesson {lesson_number}: Removed potentially corrupted file after error: {output_filepath}")
        except OSError as remove_err:
             log.error(f"Lesson {lesson_number}: Could not remove file {output_filepath} after error: {remove_err}")
    return None # Return None to indicate failure
# --- End of function ---