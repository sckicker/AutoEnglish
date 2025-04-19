# pdf_parser.py V1.2 - Added Text Cleaning Logic

import re
import logging
import pdfminer.high_level
import pdfminer.layout
import os

# --- Setup Logging ---
# It's better to configure logging where the application is initialized (e.g., app/__init__.py)
# but adding a basic logger here for standalone testing or clarity.
log = logging.getLogger(__name__)
# Example basic config if run standalone:
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Constants for State Machine ---
STATE_LOOKING_FOR_LESSON = "LOOKING_FOR_LESSON"
STATE_EXPECTING_TITLE_EN = "EXPECTING_TITLE_EN"
STATE_EXPECTING_TITLE_CN = "EXPECTING_TITLE_CN"
STATE_SKIPPING_HEADER = "SKIPPING_HEADER"      # State to skip instruction lines after titles
STATE_CAPTURING_TEXT_EN = "CAPTURING_TEXT_EN"    # Capturing English main text
STATE_CAPTURING_VOCAB = "CAPTURING_VOCAB"        # Capturing Vocabulary section
STATE_CAPTURING_TEXT_CN = "CAPTURING_TEXT_CN"    # Capturing Chinese translation text

# --- Markers & Patterns ---
MARKER_LESSON_START = r'^\s*Lesson\s+(\d+)'              # Matches "Lesson XX" at the start
MARKER_VOCAB_START = r"New words and expressions|生词和短语" # Start of vocabulary section
MARKER_TEXT_CN_START = r"参考译文"                         # Start of Chinese translation section
# Patterns indicating header/instruction lines to potentially skip after titles
# Added common question words and instruction phrases
PATTERN_HEADER_SKIP = r'^(First listen|听录音|Why did|What happens|When did|How did|Where did|Who is|What is|What are|What does|What did|Then answer|Answer these questions)'
# Regular expression to capture vocabulary items: (English) (POS - optional) (Chinese)
REGEX_VOCAB = r'^([a-zA-Z]+(?:[\s\'-][a-zA-Z]+)*)\s+(?:(?:\(?([a-z]{1,4})\.?\)?\.?)\s+)?(.+)$'
# Markers that often indicate the end of a useful text section (like EN text or CN text)
# before the next lesson or major section (like exercises)
MARKER_SECTION_END = r"Comprehension|Exercises|Key\s+to|Summary\s+writing|Multiple\s+choice|Sentence\s+structure|语法|词汇练习|难点|Text|Translation" # Added Text/Translation to handle potential misfires


def clean_and_reformat_text(lines):
    """
    Cleans and reformats text lines extracted from PDF.
    Joins lines, removes extra whitespace, and attempts to restore paragraph breaks
    based on sentence-ending punctuation followed by an uppercase letter.
    """
    if not lines:
        return ""

    # 1. Join non-empty, stripped lines with a single space
    full_text = " ".join(line.strip() for line in lines if line.strip())

    # 2. Normalize whitespace: replace multiple spaces/tabs/newlines with a single space
    cleaned_text = re.sub(r'\s+', ' ', full_text).strip()

    # 3. Re-insert paragraph breaks heuristically.
    #    Looks for sentence-ending punctuation [.?!] followed by whitespace,
    #    then an uppercase letter [A-Z] (indicating a new sentence likely starts).
    #    Replaces the intervening whitespace with two newlines for a paragraph break.
    #    This helps join lines broken mid-sentence in the PDF but separate actual sentences.
    #    Note: Might not be perfect for all cases (e.g., abbreviations, quotes).
    reformatted_text = re.sub(r'(?<=[.?!])\s+(?=[A-Z])', '\n\n', cleaned_text)

    # Optional: If the above is too aggressive, a simpler version just adds one newline:
    # reformatted_text = re.sub(r'([.?!])\s+', r'\1\n', cleaned_text)

    return reformatted_text


def finalize_lesson_data(lesson_data, text_en_lines, text_cn_lines, vocab_items, lessons_list, vocabulary_list):
    """
    Helper function called when a lesson section ends (or PDF ends).
    Cleans collected text, finalizes the lesson data dictionary,
    and appends the lesson and its vocabulary to the respective lists.
    """
    if not lesson_data or 'lesson_number' not in lesson_data:
        log.debug("finalize_lesson_data called with no valid lesson data to process.")
        return

    lesson_num = lesson_data['lesson_number']
    log.debug(f"Finalizing data for Lesson {lesson_num}")

    # --- Clean and store English Text ---
    lesson_data['text_en'] = clean_and_reformat_text(text_en_lines)
    # log.debug(f"  Cleaned EN Text (Lesson {lesson_num}): {lesson_data['text_en'][:150]}...") # Log snippet

    # --- Clean and store Chinese Text ---
    # Applying the same logic, but monitor results. May need simpler join for Chinese.
    lesson_data['text_cn'] = clean_and_reformat_text(text_cn_lines)
    # log.debug(f"  Cleaned CN Text (Lesson {lesson_num}): {lesson_data['text_cn'][:150]}...") # Log snippet

    # Ensure required fields have some content (even if empty string after cleaning)
    lesson_data.setdefault('title_en', '')
    lesson_data.setdefault('title_cn', '')
    lesson_data.setdefault('text_en', '')
    lesson_data.setdefault('text_cn', '')

    # --- Store Lesson Data ---
    lessons_list.append(lesson_data)
    log.info(f"Stored lesson text data for Lesson {lesson_num} (EN Title: {len(lesson_data['title_en'])}, CN Title: {len(lesson_data['title_cn'])}, EN Text: {len(lesson_data['text_en'])}, CN Text: {len(lesson_data['text_cn'])} chars).")
    # Add warnings for completely missing sections
    if not lesson_data.get('title_en'): log.warning(f"Missing English title for Lesson {lesson_num}")
    if not lesson_data.get('text_en'): log.warning(f"Missing English text for Lesson {lesson_num}")
    if not lesson_data.get('text_cn'): log.warning(f"Missing Chinese text for Lesson {lesson_num}")

    # --- Store Vocabulary ---
    valid_vocab_count = 0
    for item in vocab_items:
        if isinstance(item, dict) and 'english' in item and 'chinese' in item:
             item['lesson'] = lesson_num # Ensure lesson number is set
             vocabulary_list.append(item)
             valid_vocab_count += 1
        else:
            log.warning(f"Skipping invalid vocab item found during finalization for Lesson {lesson_num}: {item}")

    log.info(f"Stored {valid_vocab_count} vocabulary items for Lesson {lesson_num}.")


def process_nce_pdf(pdf_path):
    """
    Extracts Lesson Titles, English Text, Chinese Text, and Vocabulary
    from a New Concept English Book 2 PDF using pdfminer.six and a state machine.

    Args:
        pdf_path (str): The full path to the NCE Book 2 PDF file.

    Returns:
        dict: A dictionary containing two lists:
              'vocabulary': List of vocabulary dictionaries [{'lesson': N, 'english': 'word', ...}, ...]
              'lessons': List of lesson dictionaries [{'lesson_number': N, 'title_en': '...', ...}, ...]
              Returns {'vocabulary': [], 'lessons': []} on error or if file not found.
    """
    if not os.path.exists(pdf_path):
        log.error(f"PDF file not found at path: {pdf_path}")
        return {'vocabulary': [], 'lessons': []}

    log.info(f"--- Starting NCE PDF Extraction (V1.2 with text cleaning) ---")
    log.info(f"Processing PDF: {pdf_path}")
    vocabulary_list = [] # List to hold all vocab dicts
    lessons_list = []    # List to hold all lesson dicts

    # --- State Machine Variables ---
    current_lesson_number = 0           # Track the lesson number being processed
    state = STATE_LOOKING_FOR_LESSON    # Initial state
    current_lesson_data = {}            # Temp dict for current lesson's info
    current_text_en_lines = []          # Buffer for English text lines
    current_text_cn_lines = []          # Buffer for Chinese text lines
    current_vocab_items = []            # Buffer for vocabulary items dicts
    # -----------------------------

    try:
        # Extract pages using pdfminer
        for page_num, page_layout in enumerate(pdfminer.high_level.extract_pages(pdf_path)):
            log.debug(f"--- Processing Page Number: {page_num + 1} ---")

            # Iterate through elements on the page
            for element in page_layout:
                # We are interested in text containers
                if isinstance(element, pdfminer.layout.LTTextContainer):
                    raw_text = element.get_text()
                    # Normalize line endings and split into lines
                    lines = re.sub(r'\r\n|\r', '\n', raw_text).split('\n') # Handle different line endings

                    # Process each line based on the current state
                    for line_num, line in enumerate(lines):
                        original_line = line # Keep original for potential multi-line elements if needed later
                        line = line.strip() # Work with the stripped version for matching

                        # --- State Machine Logic ---
                        # Log current state and line being processed (for debugging)
                        # log.debug(f"  P{page_num + 1}|L{line_num + 1}|State:{state}| Line: '{line}'")

                        # --- Check for Lesson Start Marker (Always) ---
                        lesson_match = re.match(MARKER_LESSON_START, line, re.IGNORECASE)
                        if lesson_match:
                            new_lesson = int(lesson_match.group(1))
                            log.debug(f"Detected 'Lesson {new_lesson}' marker.")
                            # Finalize data for the *previous* lesson before starting new one
                            if current_lesson_number > 0:
                                finalize_lesson_data(current_lesson_data, current_text_en_lines,
                                                     current_text_cn_lines, current_vocab_items,
                                                     lessons_list, vocabulary_list)
                            # Reset state and buffers for the new lesson
                            current_lesson_number = new_lesson
                            state = STATE_EXPECTING_TITLE_EN # Expect English title next
                            current_lesson_data = {'lesson_number': current_lesson_number}
                            current_text_en_lines = []
                            current_text_cn_lines = []
                            current_vocab_items = []
                            log.info(f"--- Started processing Lesson {current_lesson_number} ---")
                            continue # Process next line

                        # --- State-Specific Processing ---
                        if not current_lesson_number > 0 and state == STATE_LOOKING_FOR_LESSON:
                             # If we haven't found the first lesson yet, skip lines
                             continue

                        # --- Capturing Titles and Skipping Headers ---
                        if state == STATE_EXPECTING_TITLE_EN:
                            if line: # First non-empty line is assumed English title
                                current_lesson_data['title_en'] = line
                                log.debug(f"  Captured English Title: '{line}'")
                                state = STATE_EXPECTING_TITLE_CN
                        elif state == STATE_EXPECTING_TITLE_CN:
                             if line: # First non-empty line after EN title is assumed CN title
                                current_lesson_data['title_cn'] = line
                                log.debug(f"  Captured Chinese Title: '{line}'")
                                state = STATE_SKIPPING_HEADER # Now expect header/instruction lines
                        elif state == STATE_SKIPPING_HEADER:
                            # Skip blank lines and specific header patterns
                            if not line or re.search(PATTERN_HEADER_SKIP, line, re.IGNORECASE):
                                # log.debug(f"  Skipping header line: '{line}'")
                                continue
                            else:
                                # The first line *not* skipped is the start of English text
                                log.debug(f"  Finished skipping headers. Assuming start of English text.")
                                current_text_en_lines.append(line) # Add this first line
                                state = STATE_CAPTURING_TEXT_EN

                        # --- Capturing English Text ---
                        elif state == STATE_CAPTURING_TEXT_EN:
                            # Check if vocabulary section starts
                            if re.search(MARKER_VOCAB_START, line, re.IGNORECASE):
                                log.info(f"Detected start of Vocabulary Section.")
                                state = STATE_CAPTURING_VOCAB
                            # Check if Chinese text section starts unexpectedly (might happen)
                            elif re.search(MARKER_TEXT_CN_START, line, re.IGNORECASE):
                                log.warning(f"Detected Chinese Text marker while expecting English Text/Vocab for Lesson {current_lesson_number}.")
                                state = STATE_CAPTURING_TEXT_CN
                            # Check for other section end markers
                            elif re.search(MARKER_SECTION_END, line, re.IGNORECASE):
                                log.info(f"Detected potential section end marker '{line}' while capturing English Text.")
                                # Assume end of English text, move to look for vocab or CN text
                                state = STATE_CAPTURING_VOCAB # Tentatively assume vocab follows
                            elif line: # Add non-empty lines to the buffer
                                current_text_en_lines.append(line)
                                # log.debug(f"  EN Line: '{line}'")

                        # --- Capturing Vocabulary ---
                        elif state == STATE_CAPTURING_VOCAB:
                            # Check if Chinese text section starts
                            if re.search(MARKER_TEXT_CN_START, line, re.IGNORECASE):
                                log.info(f"Detected start of Chinese Text Section.")
                                state = STATE_CAPTURING_TEXT_CN
                            # Check for other section end markers
                            elif re.search(MARKER_SECTION_END, line, re.IGNORECASE):
                                log.info(f"Detected potential section end marker '{line}' while capturing Vocab.")
                                # Assume vocab ends here, look for Chinese text next
                                state = STATE_CAPTURING_TEXT_CN
                            else:
                                # Attempt to parse as a vocabulary item
                                vocab_match = re.match(REGEX_VOCAB, line)
                                if vocab_match:
                                    eng = vocab_match.group(1).strip()
                                    pos = vocab_match.group(2) # Can be None
                                    chn = vocab_match.group(3).strip()
                                    if eng and chn: # Basic validation
                                        vocab_item = {'english': eng, 'chinese': chn, 'part_of_speech': pos or ''} # Use empty string if no POS
                                        current_vocab_items.append(vocab_item)
                                        # log.debug(f"  [Vocab] Added: Eng='{eng}' | POS='{pos}' | Chn='{chn}'")
                                    else:
                                        log.warning(f"  [Vocab] Partial match (missing Eng or Chn) on line: '{original_line}'")
                                elif line: # Log non-empty lines in vocab section that didn't match
                                    log.debug(f"  [Vocab] Line did not match pattern: '{line}'")

                        # --- Capturing Chinese Text ---
                        elif state == STATE_CAPTURING_TEXT_CN:
                             # Check for section end markers (next Lesson start is handled globally)
                             if re.search(MARKER_SECTION_END, line, re.IGNORECASE):
                                log.info(f"Detected potential section end marker '{line}' while capturing Chinese Text.")
                                # Often marks the end before exercises etc. Continue capturing until next Lesson marker.
                                continue # Skip the marker line itself
                             elif line: # Add non-empty lines
                                 current_text_cn_lines.append(line)
                                 # log.debug(f"  CN Line: '{line}'")

        # --- End of PDF Loop ---
        # After processing all pages, finalize the last captured lesson
        if current_lesson_number > 0:
            log.info(f"End of PDF reached. Finalizing data for the last lesson: {current_lesson_number}")
            finalize_lesson_data(current_lesson_data, current_text_en_lines,
                                 current_text_cn_lines, current_vocab_items,
                                 lessons_list, vocabulary_list)

    # --- Error Handling ---
    except FileNotFoundError:
        log.error(f"PDF file does not exist at the specified path: {pdf_path}")
        return {'vocabulary': [], 'lessons': []}
    except ImportError:
         log.error("Required library pdfminer.six not found. Please install it using 'pip install pdfminer.six'")
         return {'vocabulary': [], 'lessons': []}
    except Exception as e:
        log.error(f"An unexpected error occurred during PDF parsing for {pdf_path}: {e}", exc_info=True)
        # Still try to return whatever was collected before the error
        log.warning("Returning potentially incomplete data due to error during processing.")
        # Ensure last lesson before error is finalized if possible
        if current_lesson_number > 0 and current_lesson_data not in lessons_list:
             finalize_lesson_data(current_lesson_data, current_text_en_lines,
                                 current_text_cn_lines, current_vocab_items,
                                 lessons_list, vocabulary_list)
        return {'vocabulary': vocabulary_list, 'lessons': lessons_list}

    # --- Success ---
    log.info(f"--- Finished NCE PDF Extraction Successfully ---")
    log.info(f"Total vocabulary items extracted: {len(vocabulary_list)}")
    log.info(f"Total lessons with text data extracted: {len(lessons_list)}")
    return {'vocabulary': vocabulary_list, 'lessons': lessons_list}


# --- Standalone Test Block ---
if __name__ == '__main__':
    # Configure basic logging for standalone testing
    logging.basicConfig(level=logging.INFO, # Change to DEBUG for more detail
                        format='%(asctime)s - %(levelname)s - %(message)s')

    # --- IMPORTANT: Set the path to your test PDF file here ---
    # Use an absolute path or a path relative to where you run this script
    script_dir = os.path.dirname(__file__)
    # Assumes PDF is in ../data/ relative to this script's location
    pdf_file_path = os.path.abspath(os.path.join(script_dir, '..', 'data', 'nce_book2.pdf')) # Adjusted default path for testing
    # pdf_file_path = '/path/to/your/actual/nce_book2.pdf' # Or set an absolute path

    print(f"Attempting to process PDF: {pdf_file_path}")

    if os.path.exists(pdf_file_path):
        extracted_data = process_nce_pdf(pdf_file_path)

        print("\n--- Extraction Summary ---")
        print(f"Total Vocabulary Items: {len(extracted_data['vocabulary'])}")
        print(f"Total Lessons Found: {len(extracted_data['lessons'])}")

        # Print sample data
        if extracted_data['lessons']:
            print("\n--- Sample Lesson (First Found) ---")
            sample_lesson = extracted_data['lessons'][0]
            print(f"Lesson Number: {sample_lesson.get('lesson_number')}")
            print(f"Title EN: {sample_lesson.get('title_en')}")
            print(f"Title CN: {sample_lesson.get('title_cn')}")
            print(f"Text EN (Snippet): {sample_lesson.get('text_en', '')[:200]}...")
            print(f"Text CN (Snippet): {sample_lesson.get('text_cn', '')[:200]}...")

        if extracted_data['vocabulary']:
            print("\n--- Sample Vocabulary (First 5 Items) ---")
            for i, item in enumerate(extracted_data['vocabulary'][:5]):
                print(f"  {i+1}. Lesson {item.get('lesson')}: {item.get('english')} ({item.get('part_of_speech')}) - {item.get('chinese')}")
    else:
        print(f"\nError: Test PDF file not found at the specified path: {pdf_file_path}")
        print("Please ensure the path is correct or modify the `pdf_file_path` variable in the script's `if __name__ == '__main__':` block.")