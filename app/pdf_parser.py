import re
import logging
import pdfminer.high_level
import pdfminer.layout
import os

log = logging.getLogger(__name__)

# --- Constants for State Machine ---
STATE_LOOKING_FOR_LESSON = "LOOKING_FOR_LESSON"
STATE_EXPECTING_TITLE_EN = "EXPECTING_TITLE_EN"
STATE_EXPECTING_TITLE_CN = "EXPECTING_TITLE_CN"
STATE_SKIPPING_HEADER = "SKIPPING_HEADER"
STATE_CAPTURING_TEXT_EN = "CAPTURING_TEXT_EN"
STATE_CAPTURING_VOCAB = "CAPTURING_VOCAB"
STATE_CAPTURING_TEXT_CN = "CAPTURING_TEXT_CN"

# --- Markers & Patterns ---
MARKER_LESSON_START = r'^\s*Lesson\s+(\d+)'
MARKER_VOCAB_START = r"New words and expressions|生词和短语"
MARKER_TEXT_CN_START = r"参考译文"
# Combine known instruction/question patterns to skip them (Added 'Then answer')
PATTERN_HEADER_SKIP = r'^(First listen|听录音|Why did|What happens|When did|How did|Where did|Then answer)'
# Vocab extraction regex
REGEX_VOCAB = r'^([a-zA-Z]+(?:[\s\'-][a-zA-Z]+)*)\s+(?:(?:\(?([a-z]{1,4})\.?\)?\.?)\s+)?(.+)$'

# --- 添加这行定义 ---
# Markers that often indicate the end of a text/vocab section before the next lesson
MARKER_SECTION_END = r"Comprehension|Exercises|Key\s+to|Summary\s+writing|Multiple\s+choice|Sentence\s+structure|语法|词汇练习|难点"


def finalize_lesson_data(lesson_data, text_en_lines, text_cn_lines, vocab_items, lessons_list, vocabulary_list):
    """Helper function to finalize and store data for the completed lesson."""
    if not lesson_data or 'lesson_number' not in lesson_data:
        log.debug("finalize_lesson_data called with no current lesson data to finalize.")
        return

    lesson_num = lesson_data['lesson_number']
    log.debug(f"Finalizing data for Lesson {lesson_num}")

    # Join collected lines. Replace multiple newlines potentially created by blank lines
    # in the source with single newlines for cleaner paragraph separation.
    lesson_data['text_en'] = re.sub(r'\n{2,}', '\n', "\n".join(text_en_lines)).strip()
    lesson_data['text_cn'] = re.sub(r'\n{2,}', '\n', "\n".join(text_cn_lines)).strip()

    lessons_list.append(lesson_data)
    log.info(f"Stored lesson text data for Lesson {lesson_num} (EN: {len(lesson_data['text_en'])} chars, CN: {len(lesson_data['text_cn'])} chars).")
    if not lesson_data.get('title_en'): log.warning(f"Missing English title for Lesson {lesson_num}")
    if not lesson_data.get('text_en'): log.warning(f"Missing English text for Lesson {lesson_num}")
    if not lesson_data.get('text_cn'): log.warning(f"Missing Chinese text for Lesson {lesson_num}")

    # Add collected vocabulary items, ensuring lesson number is attached
    valid_vocab_count = 0
    for item in vocab_items:
        if isinstance(item, dict):
             item['lesson'] = lesson_num # Set lesson number
             vocabulary_list.append(item)
             valid_vocab_count += 1
        else:
            log.warning(f"Skipping invalid vocab item found during finalization: {item}")

    log.info(f"Stored {valid_vocab_count} vocabulary items for Lesson {lesson_num}.")


def process_nce_pdf(pdf_path):
    """
    V1.1 Attempt: Extracts vocabulary & lesson text based on observed structure.

    Uses pdfminer.six and a state machine tailored to the provided format.
    Still experimental, likely needs refinement for full NCE Book 2.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        dict: {'vocabulary': [...], 'lessons': [...]}
    """
    if not os.path.exists(pdf_path):
        log.error(f"PDF file not found at path: {pdf_path}")
        return {'vocabulary': [], 'lessons': []}

    log.info(f"Starting V1.1 NCE data extraction for PDF: {pdf_path}")
    vocabulary_list = []
    lessons_list = []

    current_lesson_number = 0
    state = STATE_LOOKING_FOR_LESSON
    current_lesson_data = {}
    current_text_en_lines = []
    current_text_cn_lines = []
    current_vocab_items = []

    try:
        for page_num, page_layout in enumerate(pdfminer.high_level.extract_pages(pdf_path)):
            log.debug(f"Processing Page Number: {page_num + 1}")

            for element in page_layout:
                if isinstance(element, pdfminer.layout.LTTextContainer):
                    raw_text = element.get_text()
                    # Replace potential multiple newlines from layout with single ones for splitting
                    lines = re.sub(r'\n{2,}', '\n', raw_text).split('\n')

                    for line_num, line in enumerate(lines):
                        original_line = line # Keep original for potential multi-line elements
                        line = line.strip()

                        log.debug(f"  P{page_num + 1}|L{line_num + 1}|State:{state}| Line: '{line}'")

                        # --- Always check for Lesson Start ---
                        lesson_match = re.match(MARKER_LESSON_START, line, re.IGNORECASE)
                        if lesson_match:
                            new_lesson = int(lesson_match.group(1))
                            log.debug(f"Detected 'Lesson {new_lesson}' marker.")
                            if current_lesson_number > 0: # Finalize previous lesson if applicable
                                finalize_lesson_data(current_lesson_data, current_text_en_lines,
                                                     current_text_cn_lines, current_vocab_items,
                                                     lessons_list, vocabulary_list)
                            # Reset for new lesson
                            current_lesson_number = new_lesson
                            state = STATE_EXPECTING_TITLE_EN
                            current_lesson_data = {'lesson_number': current_lesson_number}
                            current_text_en_lines = []
                            current_text_cn_lines = []
                            current_vocab_items = []
                            log.info(f"--- Started processing Lesson {current_lesson_number} ---")
                            continue # Move to next line

                        # --- State-Specific Processing ---

                        if state == STATE_EXPECTING_TITLE_EN:
                            if line: # Expecting first non-empty line as EN title
                                current_lesson_data['title_en'] = line
                                log.debug(f"  Captured English Title: '{line}'")
                                state = STATE_EXPECTING_TITLE_CN
                            # else: Stay in this state if line is empty

                        elif state == STATE_EXPECTING_TITLE_CN:
                             if line: # Expecting first non-empty line as CN title
                                current_lesson_data['title_cn'] = line
                                log.debug(f"  Captured Chinese Title: '{line}'")
                                state = STATE_SKIPPING_HEADER # Next, skip instructions
                            # else: Stay in this state

                        elif state == STATE_SKIPPING_HEADER:
                            # Skip blank lines and known instruction/question patterns
                            if not line or re.search(PATTERN_HEADER_SKIP, line, re.IGNORECASE):
                                log.debug(f"  Skipping header line: '{line}'")
                                continue
                            else:
                                # Assume first non-skipped line is start of English text
                                log.debug(f"  Finished skipping headers. Assuming start of English text: '{line}'")
                                current_text_en_lines.append(line) # Add this line
                                state = STATE_CAPTURING_TEXT_EN

                        elif state == STATE_CAPTURING_TEXT_EN:
                            # Check for Vocab start marker first
                            if re.search(MARKER_VOCAB_START, line, re.IGNORECASE):
                                log.info(f"Detected start of Vocabulary Section.")
                                state = STATE_CAPTURING_VOCAB
                                continue # Don't add marker line to text
                            # Otherwise, add to English text buffer
                            current_text_en_lines.append(original_line) # Append original line to preserve internal spacing/newlines better? Test this.
                            # log.debug(f"  Added to English text buffer: '{line}'")

                        elif state == STATE_CAPTURING_VOCAB:
                            # Check for Chinese Text start marker
                            if re.search(MARKER_TEXT_CN_START, line, re.IGNORECASE):
                                log.info(f"Detected start of Chinese Text Section.")
                                state = STATE_CAPTURING_TEXT_CN
                                continue # Don't add marker line
                            # Check for other potential end markers (less likely between vocab and CN text)
                            elif re.search(MARKER_SECTION_END, line, re.IGNORECASE):
                                log.warning(f"Detected unexpected end marker '{line}' while capturing Vocab.")
                                # Decide how to handle: maybe finalize and look for next lesson?
                                # For V1.1, let's assume CN text follows or next lesson starts.
                                continue # Skip this line for now

                            # Try matching vocab item
                            vocab_match = re.match(REGEX_VOCAB, line)
                            if vocab_match:
                                eng = vocab_match.group(1).strip()
                                pos = vocab_match.group(2)
                                chn = vocab_match.group(3).strip()
                                if eng and chn:
                                    vocab_item = {'english': eng, 'chinese': chn, 'part_of_speech': pos}
                                    current_vocab_items.append(vocab_item)
                                    log.debug(f"  [Vocab] Added: Eng='{eng}' | POS='{pos}' | Chn='{chn}'")
                                else: log.warning(f"  [Vocab] Partial match? Line: '{line}'")
                            elif line: # Log non-empty lines that don't match
                                log.debug(f"  [Vocab] Line did not match vocab pattern: '{line}'")

                        elif state == STATE_CAPTURING_TEXT_CN:
                             # Check for markers indicating end (like next lesson handled above)
                             # Or common section end markers
                             if re.search(MARKER_SECTION_END, line, re.IGNORECASE):
                                log.info(f"Detected potential end marker '{line}' while capturing Chinese Text.")
                                # Don't change state here, let the next 'Lesson X' finalize
                                continue # Skip this end marker line

                             # Otherwise, add to Chinese text buffer
                             current_text_cn_lines.append(original_line) # Use original line? Test this.
                             # log.debug(f"  Added to Chinese text buffer: '{line}'")


                        # STATE_LOOKING_FOR_LESSON is handled by the initial Lesson check

        # --- End of PDF Processing ---
        if current_lesson_number > 0:
            log.info(f"End of PDF reached. Finalizing last lesson: {current_lesson_number}")
            finalize_lesson_data(current_lesson_data, current_text_en_lines,
                                 current_text_cn_lines, current_vocab_items,
                                 lessons_list, vocabulary_list)

    except FileNotFoundError:
        log.error(f"PDF file does not exist at the specified path: {pdf_path}")
        return {'vocabulary': [], 'lessons': []}
    except ImportError:
         log.error("pdfminer.six library not found. Please install it using 'pip install pdfminer.six'")
         return {'vocabulary': [], 'lessons': []}
    except Exception as e:
        log.error(f"An unexpected error occurred during PDF parsing process: {e}", exc_info=True)
        return {'vocabulary': [], 'lessons': []} # Return empty on major error

    log.info(f"Finished NCE data extraction. Total vocabulary items: {len(vocabulary_list)}. Total lessons with text data: {len(lessons_list)}")
    return {'vocabulary': vocabulary_list, 'lessons': lessons_list}


# --- (Optional) Standalone Test Block ---
# (Same test block as V1.0, can be used for basic checks)
# if __name__ == '__main__':
#    # ... (configure logging, set pdf_file_path) ...
#    if os.path.exists(pdf_file_path):
#        extracted_data = process_nce_pdf(pdf_file_path)
#        # ... (print summary and samples) ...
#    else:
#        print(f"Error: Test PDF file not found at calculated path: {pdf_file_path}")