# app/routes.py

import os
import random
from datetime import datetime
from flask import (current_app, render_template, request, jsonify, Blueprint,
                   redirect, url_for, session, flash, abort, send_from_directory)
# --- 修改这里的导入 ---
from flask_login import current_user, login_user, logout_user, login_required # <-- 直接从 flask_login 导入 login_required
from sqlalchemy.orm import joinedload
from urllib.parse import urlsplit

# --- Import from local package ---
from . import db
from .models import Vocabulary, Lesson, User, QuizAttempt, WrongAnswer, UserFavoriteVocabulary, PronunciationScore
from .forms import LoginForm, RegistrationForm
from .pdf_parser import process_nce_pdf
from .decorators import admin_required, root_admin_required # <-- 从这里只导入你自定义的装饰器
from .tts_utils import generate_and_save_audio_if_not_exists, get_audio_filename
from flask import jsonify, request, abort, current_app, flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError # <--- 导入 IntegrityError
from werkzeug.utils import secure_filename # 用于基本的安全检查（虽然我们自己生成文件名）
from .scoring_utils import evaluate_audio_recording # 导入主评估函数

# --- Define allowed categories (can be moved to config.py later) ---
ALLOWED_WRONG_ANSWER_CATEGORIES = ["重点复习", "易混淆", "拼写困难", "用法模糊", "暂不复习"]


# === Core Application Routes ===

@current_app.route('/')
def index():
    """Homepage: Displays lesson list for selection."""
    lesson_numbers = []
    try:
        lessons_q = Lesson.query.with_entities(Lesson.lesson_number).distinct().order_by(Lesson.lesson_number).all()
        if lessons_q:
            lesson_numbers = [l[0] for l in lessons_q]
        else:
             lessons_q_vocab = db.session.query(Vocabulary.lesson_number.distinct()).order_by(Vocabulary.lesson_number).all()
             lesson_numbers = [l[0] for l in lessons_q_vocab]
        current_app.logger.debug(f"Fetched distinct lessons for index: {lesson_numbers}")
    except Exception as e:
        current_app.logger.error(f"Error fetching lessons from DB for index: {e}", exc_info=True)

    now = datetime.utcnow()
    return render_template('index.html', lessons=lesson_numbers, current_time=now)


@current_app.route('/lessons', endpoint='view_lessons')
def view_lessons():
    """Displays a list of all available lessons."""
    lessons_data = []
    try:
        lessons_data = Lesson.query.order_by(Lesson.lesson_number).all()
        if not lessons_data:
             lessons_q_vocab = db.session.query(Vocabulary.lesson_number.distinct()).order_by(Vocabulary.lesson_number).all()
             lessons_data = [{'lesson_number': l[0]} for l in lessons_q_vocab]
        current_app.logger.debug(f"Fetched all lessons for /lessons page.")
    except Exception as e:
        current_app.logger.error(f"Error fetching lessons from DB for /lessons page: {e}", exc_info=True)
        flash('加载课程列表时出错。(Error loading lesson list.)', 'danger')

    now = datetime.utcnow()
    return render_template('lessons_list.html', title='课程列表 (Lesson List)', lessons=lessons_data, current_time=now)


@current_app.route('/lesson/<int:lesson_number>')
@login_required
def view_lesson(lesson_number):
    """显示指定 Lesson 的课文内容，并检查音频文件（预生成和用户录音）。"""
    current_app.logger.info(f"Request received for lesson {lesson_number} by user {current_user.id}")
    lesson_data = Lesson.query.filter_by(lesson_number=lesson_number, source_book=2).first_or_404()

    # --- 查找预生成音频 (逻辑保持不变，使用 PREGENERATED_AUDIO_FOLDER) ---
    pregen_audio_url = None
    audio_folder = current_app.config.get('PREGENERATED_AUDIO_FOLDER')
    filename_template = current_app.config.get('PREGENERATED_AUDIO_FILENAME_TEMPLATE', 'lesson_{lesson_number}.{ext}')
    possible_extensions = current_app.config.get('PREGENERATED_AUDIO_EXTENSIONS', ['.wav'])
    if audio_folder:
        for ext in possible_extensions:
            clean_ext = ext.lstrip('.')
            try:
                filename = filename_template.format(lesson_number=lesson_number, ext=clean_ext)
                absolute_filepath = os.path.join(audio_folder, filename)
                current_app.logger.debug(f"Checking for pre-generated audio at: {absolute_filepath}")
                if os.path.exists(absolute_filepath):
                    pregen_audio_url = url_for('get_pregenerated_audio', lesson_number=lesson_number, filename=filename)
                    current_app.logger.info(f"Found pre-generated audio file: {filename}, URL: {pregen_audio_url}")
                    break
            except KeyError as e: current_app.logger.error(f"Filename template error: {e}"); break
            except Exception as e: current_app.logger.error(f"Error check pre-gen audio '{filename}': {e}", exc_info=True)
    else: current_app.logger.warning("PREGENERATED_AUDIO_FOLDER not configured.")
    # --- 结束查找预生成音频 ---

    # --- 修改：检查用户之前的录音（匹配新的目录结构） ---
    user_recording_url = None
    # 1. 获取基础录音目录
    base_recordings_folder = current_app.config.get('USER_RECORDINGS_BASE_FOLDER')
    if base_recordings_folder:
        # 2. 构建当前用户的专属子目录路径
        user_specific_folder = os.path.join(base_recordings_folder, f"user_{current_user.id}")
        current_app.logger.debug(f"Checking for user recording in: {user_specific_folder}")

        # 3. 在用户专属子目录中查找文件
        user_rec_extensions = ['.webm', '.ogg', '.wav'] # 与上传/获取逻辑一致
        for ext in user_rec_extensions:
            # 4. 文件名只包含课程号和扩展名
            filename = f"lesson_{lesson_number}{ext}"
            filepath = os.path.join(user_specific_folder, filename) # 检查的绝对路径

            current_app.logger.debug(f"Checking for user recording file at: {filepath}")
            if os.path.exists(filepath):
                # 5. 如果文件存在，生成指向 get_user_recording 路由的 URL
                #    该路由知道如何根据 user_id 和 lesson_number 找到正确的子目录和文件
                user_recording_url = url_for('get_user_recording', user_id=current_user.id, lesson_number=lesson_number)
                current_app.logger.info(f"Found previous user recording file: {filename} in user's folder. URL: {user_recording_url}")
                break # 找到一个就停止
    else:
        current_app.logger.warning("USER_RECORDINGS_BASE_FOLDER not configured.")
    # --- 结束修改 ---

    # --- 新增：查找用户之前的评分记录 ---
    previous_score_data = None
    score_record = PronunciationScore.query.filter_by(user_id=current_user.id, lesson_number=lesson_number).first()
    if score_record:
        previous_score_data = {
            'final_score': score_record.final_score,
            'accuracy_score': score_record.accuracy_score,
            'fluency_score': score_record.fluency_score,
            'speed_score': score_record.speed_score,
            'recognized_text': score_record.recognized_text,
            'wer': score_record.wer,
            'speech_rate_wps': score_record.speech_rate_wps,
            'timestamp': score_record.timestamp.strftime(
                '%Y-%m-%d %H:%M:%S') + ' UTC' if score_record.timestamp else None
        }
        current_app.logger.info(f"Found previous score record for user {current_user.id}, lesson {lesson_number}.")
    # --- 结束查找评分 ---

    now = datetime.utcnow()
    return render_template('lesson_text.html',
                           lesson=lesson_data,
                           current_time=now,
                           audio_url=pregen_audio_url,
                           user_recording_audio_url=user_recording_url,
                           previous_score=previous_score_data)  # <--- 传递评分数据


# === 新增：提供预生成音频文件的路由 ===
@current_app.route('/pregen_audio/<int:lesson_number>/<filename>')
# 这个路由是否需要登录取决于你的需求，如果音频内容不敏感可以不加
# @login_required
def get_pregenerated_audio(lesson_number, filename):
    """安全地提供 instance/tts_cache 目录下的音频文件。"""
    audio_folder = current_app.config.get('PREGENERATED_AUDIO_FOLDER')
    if not audio_folder:
        current_app.logger.error("PREGENERATED_AUDIO_FOLDER is not configured.")
        return jsonify({"error": "Audio folder not configured"}), 500

    # --- 安全检查 (非常重要) ---
    # 1. 清理文件名，防止路径遍历攻击
    safe_filename = secure_filename(filename)
    # 2. 再次检查文件名是否与预期的模式匹配 (防止访问其他文件)
    expected_template = current_app.config.get('PREGENERATED_AUDIO_FILENAME_TEMPLATE', 'lesson_{lesson_number}.{ext}')
    possible_extensions = current_app.config.get('PREGENERATED_AUDIO_EXTENSIONS', ['.wav'])
    is_expected_format = False
    for ext in possible_extensions:
         clean_ext = ext.lstrip('.')
         try:
             # 检查 safe_filename 是否能由模板和当前 lesson_number 生成
             expected_name = expected_template.format(lesson_number=lesson_number, ext=clean_ext)
             if safe_filename == expected_name:
                  is_expected_format = True
                  break
         except KeyError:
              pass # 模板错误

    if not is_expected_format or safe_filename != filename: # 如果清理后的名字变了，或者格式不匹配
        current_app.logger.warning(f"Attempt to access potentially unsafe/unexpected file: '{filename}' (safe: '{safe_filename}') for lesson {lesson_number}")
        return jsonify({"error": "Invalid filename"}), 400
    # --- 结束安全检查 ---

    current_app.logger.debug(f"Attempting to serve file: {safe_filename} from folder: {audio_folder}")
    try:
        # 使用 send_from_directory 发送文件，它会处理路径拼接和安全问题
        # 需要提供目录的绝对路径
        return send_from_directory(audio_folder, safe_filename, as_attachment=False)
    except FileNotFoundError:
         current_app.logger.error(f"File not found: {safe_filename} in {audio_folder}")
         return jsonify({"error": "Audio file not found"}), 404
    except Exception as e:
         current_app.logger.error(f"Error sending file {safe_filename}: {e}", exc_info=True)
         return jsonify({"error": "Error serving file"}), 500


# === User Authentication Routes ===

@current_app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        # Allow login with username or email
        user = User.query.filter((User.username == form.username.data) | (User.email == form.username.data)).first()
        if user is None or not user.check_password(form.password.data):
            flash('无效的用户名或密码。(Invalid username or password.)', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        flash(f'登录成功，欢迎回来, {user.username}! (Login successful!)', 'success')

        next_page = request.args.get('next')
        # Security check for next_page redirect
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)

    now = datetime.utcnow()
    return render_template('login.html', title='登录 (Sign In)', form=form, current_time=now)


@current_app.route('/logout')
@login_required
def logout():
    """Logs the current user out."""
    logout_user()
    flash('你已成功登出。 (You have been logged out.)', 'info')
    return redirect(url_for('index'))


@current_app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        # --- Check if user should be admin based on config ---
        is_admin_by_config = False
        admin_usernames_str = current_app.config.get('ADMIN_USERNAMES', '')
        admin_usernames = [name.strip() for name in admin_usernames_str.split(',') if name.strip()]
        if form.username.data in admin_usernames:
            is_admin_by_config = True
        # ----------------------------------------------------

        user = User(
            username=form.username.data,
            email=form.email.data,
            is_admin=is_admin_by_config # Set admin status during creation if configured
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            if is_admin_by_config:
                flash(f'管理员账号 {user.username} 注册成功！请登录。(Admin account {user.username} registered successfully!)', 'success')
            else:
                flash('恭喜，注册成功！请登录。(Congratulations, you are now registered!)', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during user registration commit: {e}", exc_info=True)
            flash('注册过程中发生错误，请稍后重试。(An error occurred during registration.)', 'danger')
            # Re-render registration form on commit error
            now = datetime.utcnow()
            return render_template('register.html', title='注册 (Register)', form=form, current_time=now)

    now = datetime.utcnow()
    return render_template('register.html', title='注册 (Register)', form=form, current_time=now)


# === Learning Features Routes ===

@current_app.route('/history')
@login_required
def history():
    """Displays the user's quiz attempt history (paginated)."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('POSTS_PER_PAGE', 10)
    attempts = None
    try:
        attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
                                .order_by(QuizAttempt.timestamp.desc())\
                                .paginate(page=page, per_page=per_page, error_out=False)
    except Exception as e:
         current_app.logger.error(f"Error fetching history for user {current_user.id}: {e}", exc_info=True)
         flash('无法加载测试历史记录。(Failed to load quiz history.)', 'danger')

    now = datetime.utcnow()
    return render_template('history.html', title='测试历史 (Quiz History)', attempts=attempts, current_time=now)


@current_app.route('/wrong_answers')
@login_required
def wrong_answers():
    """Displays the user's list of wrong answers (enhanced)."""
    wrong_answer_records = []
    favorited_ids = set()
    try:
        wrong_answer_records = WrongAnswer.query.filter_by(user_id=current_user.id)\
                                            .options(joinedload(WrongAnswer.vocabulary_item))\
                                            .order_by(WrongAnswer.timestamp_last_wrong.desc()).all()
        # Get IDs of favorited vocab for the current user to pass to template
        favorited_ids = {fav.vocabulary_id for fav in UserFavoriteVocabulary.query.filter_by(user_id=current_user.id).with_entities(UserFavoriteVocabulary.vocabulary_id).all()}
        current_app.logger.debug(f"User {current_user.id} favorited vocab IDs: {favorited_ids}")
    except Exception as e:
        current_app.logger.error(f"Error fetching wrong answers for user {current_user.id}: {e}", exc_info=True)
        flash('加载错题本时发生错误，请稍后重试。(An error occurred loading wrong answers.)', 'danger')
        # Return empty list if query fails
        # return redirect(url_for('index')) # Or redirect on critical error

    now = datetime.utcnow()
    return render_template('wrong_answers.html',
                           title='错题本 (Wrong Answers)',
                           wrong_answers=wrong_answer_records,
                           allowed_categories=ALLOWED_WRONG_ANSWER_CATEGORIES, # Defined globally in this file
                           favorited_ids=favorited_ids, # Pass the set of favorited IDs
                           current_time=now)


# === NEW: Favorites Page Route ===
@current_app.route('/favorites')
@login_required
def view_favorites():
    """Displays the list of vocabulary items favorited by the current user."""
    favorite_vocab_items = []
    try:
        # Use the relationship to get Vocabulary items ordered by when they were favorited
        favorite_vocab_items = current_user.favorite_vocabularies.join(
                UserFavoriteVocabulary, Vocabulary.id == UserFavoriteVocabulary.vocabulary_id
            ).filter(
                UserFavoriteVocabulary.user_id == current_user.id
            ).order_by(
                UserFavoriteVocabulary.timestamp.desc()
            ).all()
        current_app.logger.debug(f"Fetched {len(favorite_vocab_items)} favorites for user {current_user.id}")
    except Exception as e:
        current_app.logger.error(f"Error fetching favorites for user {current_user.id}: {e}", exc_info=True)
        flash("加载收藏列表时出错。(Error loading favorites list.)", "danger")

    now = datetime.utcnow()
    return render_template('favorites.html',
                           title='我的收藏 (My Favorites)',
                           favorites=favorite_vocab_items,
                           current_time=now)
# === End Favorites Page Route ===


# === API Routes ===

@current_app.route('/api/quiz', methods=['GET'])
def get_quiz():
    """API endpoint to generate quiz questions."""
    # ... (Keep existing get_quiz logic as before) ...
    try:
        lessons_str = request.args.get('lessons')
        num_questions_str = request.args.get('count', '10')
        quiz_type = request.args.get('type', 'cn_to_en')

        if not lessons_str: return jsonify({"error": "Missing 'lessons' parameter"}), 400
        try:
             lesson_numbers = [int(n) for n in lessons_str.split(',')]
             num_questions = int(num_questions_str)
             if num_questions <= 0: num_questions = 10
        except ValueError: return jsonify({"error": "Invalid 'lessons' or 'count' format."}), 400

        all_vocab = Vocabulary.query.filter(Vocabulary.lesson_number.in_(lesson_numbers)).all()
        if not all_vocab: return jsonify({"error": "No vocabulary found for selected lessons"}), 404

        num_questions = min(num_questions, len(all_vocab))
        selected_vocab = random.sample(all_vocab, num_questions)

        quiz_questions = []
        for item in selected_vocab:
            question = item.chinese_translation if quiz_type == 'cn_to_en' else item.english_word
            answer = item.english_word if quiz_type == 'cn_to_en' else item.chinese_translation
            quiz_questions.append({
                "id": item.id, "lesson": item.lesson_number, "question": question,
                "part_of_speech": item.part_of_speech, "correct_answer": answer
            })
        return jsonify(quiz_questions)
    except Exception as e:
        current_app.logger.error(f"Error in /api/quiz generation: {e}", exc_info=True)
        return jsonify({"error": "Internal server error generating quiz."}), 500


@current_app.route('/api/submit_quiz', methods=['POST'])
@login_required # Ensure user is logged in
def submit_quiz_results():
    """
    Receives quiz results (JSON), scores them server-side, saves attempt and wrong answers.
    Returns scoring results (JSON). Includes extensive debugging logs.
    """
    user_id_for_logs = current_user.id if current_user else 'Unknown'
    print(f"\n--- submit_quiz_results for User {user_id_for_logs} START ---") # Start marker

    # --- 1. Get and Validate Input Data ---
    data = request.get_json()
    if not data or not isinstance(data.get('answers'), dict) or not isinstance(data.get('quiz_context'), dict):
        print(f"DEBUG User {user_id_for_logs}: Invalid data format received: {data}")
        current_app.logger.warning(f"Submit quiz from user {user_id_for_logs}: Invalid data format received.")
        return jsonify({'error': 'Invalid data format received.'}), 400

    user_answers = data.get('answers', {})
    quiz_context = data.get('quiz_context', {})
    print(f"DEBUG User {user_id_for_logs}: Received answers: {user_answers}")
    print(f"DEBUG User {user_id_for_logs}: Received quiz_context: {quiz_context}")

    # --- Extract Context Info ---
    question_ids_str = quiz_context.get('question_ids', [])
    quiz_type = quiz_context.get('quiz_type', 'cn_to_en') # Default cn_to_en
    lesson_ids = quiz_context.get('lesson_ids', []) # Keep lesson_ids

    # --- Convert and Validate Question IDs ---
    try:
        # Ensure question_ids are converted to integers
        question_ids = [int(qid) for qid in question_ids_str if str(qid).isdigit()]
        print(f"DEBUG User {user_id_for_logs}: Parsed question_ids: {question_ids}") # Log parsed IDs
    except (ValueError, TypeError) as e:
         print(f"DEBUG User {user_id_for_logs}: Invalid question IDs format: {question_ids_str}. Error: {e}")
         current_app.logger.warning(f"Submit quiz from user {user_id_for_logs}: Invalid question IDs format: {question_ids_str}. Error: {e}")
         return jsonify({'error': 'Invalid question ID format received.'}), 400

    # --- Check if we have questions to process ---
    if not question_ids: # Check if the list is empty after parsing
         print(f"DEBUG User {user_id_for_logs}: No valid question IDs found after parsing/validation.")
         current_app.logger.warning(f"Submit quiz from user {user_id_for_logs}: No valid question IDs received.")
         return jsonify({
             'message': 'No valid questions to process.',
             'score': 0,
             'total_questions': 0,
             'wrong_answers': []
         }), 200 # Return 0/0 if no questions

    current_app.logger.info(f"Processing quiz submission for user {user_id_for_logs}. Context: {quiz_context}. Answers received for {len(user_answers)} items.")

    # --- 2. Server-side Scoring and Wrong Answer Tracking ---
    total_questions = len(question_ids) # Base total on the question IDs received
    score = 0                           # Initialize score
    wrong_answer_details_for_response = []
    wrong_answer_ids_to_save = set()

    print(f"DEBUG User {user_id_for_logs}: Initial total_questions based on context: {total_questions}")

    try:
        # --- Fetch Vocabulary Items from Database ---
        print(f"DEBUG User {user_id_for_logs}: Querying DB for vocab items with IDs: {question_ids}")
        vocab_items = Vocabulary.query.filter(Vocabulary.id.in_(question_ids)).all()
        print(f"DEBUG User {user_id_for_logs}: Found {len(vocab_items)} vocab items in DB.")
        # Optional: Print details of found items if needed for deeper debugging
        # for item in vocab_items: print(f"  - Found DB item: ID={item.id}, Word='{item.english_word}'")

        # --- Adjust total_questions if DB query returned fewer items ---
        if len(vocab_items) != len(question_ids):
             print(f"DEBUG User {user_id_for_logs}: WARNING - Mismatch! Expected {len(question_ids)} questions based on context, but found {len(vocab_items)} in DB.")
             total_questions = len(vocab_items) # Adjust total to actual items found for scoring
             print(f"DEBUG User {user_id_for_logs}: Adjusted total_questions to: {total_questions}")
             if total_questions == 0:
                 print(f"DEBUG User {user_id_for_logs}: No matching vocab items found in DB. Returning 0/0 score.")
                 # If no items found, return 0 score now, maybe save attempt later or not
                 return jsonify({
                     'message': 'No matching vocabulary found for scoring.',
                     'score': 0,
                     'total_questions': 0,
                     'wrong_answers': []
                 }), 200 # Still a successful process, just no score

        # --- Build Vocabulary Map for Efficient Lookup ---
        vocab_map = {item.id: item for item in vocab_items}
        print(f"DEBUG User {user_id_for_logs}: Built vocab_map with {len(vocab_map)} items.")

        # --- Iterate Through User Answers for Scoring ---
        print(f"DEBUG User {user_id_for_logs}: Starting scoring loop for {len(user_answers)} submitted answers...")
        for vocab_id_str, user_answer in user_answers.items():
            try:
                vocab_id = int(vocab_id_str)
                print(f"  - Processing answer for vocab_id: {vocab_id}")
                if vocab_id in vocab_map:
                    item = vocab_map[vocab_id]
                    correct_answer = item.english_word if quiz_type == 'cn_to_en' else item.chinese_translation
                    user_answer_cleaned = user_answer.strip() if isinstance(user_answer, str) else ""

                    print(f"    User Answer (cleaned): '{user_answer_cleaned}'")
                    print(f"    Correct Answer:        '{correct_answer}'")

                    # Core Scoring Comparison (case-insensitive)
                    is_correct = user_answer_cleaned.lower() == correct_answer.lower()
                    print(f"    Comparison Result: {is_correct}")

                    if is_correct:
                        score += 1
                        print(f"    Score increased to: {score}")
                    else:
                        wrong_answer_ids_to_save.add(vocab_id)
                        wrong_answer_details_for_response.append({
                            'vocab_id': vocab_id,
                            'question': item.chinese_translation if quiz_type == 'cn_to_en' else item.english_word,
                            'part_of_speech': item.part_of_speech,
                            'user_answer': user_answer, # Keep original answer for display
                            'correct_answer': correct_answer
                        })
                        print(f"    Marked as incorrect. wrong_answer_ids_to_save: {wrong_answer_ids_to_save}")
                else:
                    # This case means user submitted an answer for an ID that wasn't in the fetched items
                    print(f"  - WARNING: Submitted answer for vocab_id {vocab_id}, but it was not found in the fetched vocab_map!")
                    current_app.logger.warning(f"User {user_id_for_logs}: Submitted answer for vocab_id {vocab_id} which was not in the fetched items for this quiz.")
            except ValueError:
                 print(f"  - ERROR: Invalid vocab ID format in user answers: '{vocab_id_str}'")
                 current_app.logger.warning(f"User {user_id_for_logs}: Invalid vocab ID format in user answers: {vocab_id_str}")
            except Exception as scoring_ex:
                 print(f"  - ERROR: Exception during scoring loop for vocab_id '{vocab_id_str}': {scoring_ex}")
                 current_app.logger.error(f"User {user_id_for_logs}: Error scoring question vocab_id={vocab_id_str}: {scoring_ex}", exc_info=True)
        print(f"DEBUG User {user_id_for_logs}: Scoring loop finished.")
        print(f"DEBUG User {user_id_for_logs}: Final score before commit: {score}")
        print(f"DEBUG User {user_id_for_logs}: Final total_questions before commit: {total_questions}") # Based on items found in DB

        # --- 3. Save Quiz Attempt Record ---
        print(f"DEBUG User {user_id_for_logs}: Preparing to save QuizAttempt...")
        attempt = QuizAttempt(
            user_id=current_user.id,
            lessons_attempted=",".join(map(str, sorted(list(set(lesson_ids))))) if lesson_ids else "",
            score=score,
            total_questions=total_questions, # Use the potentially adjusted total_questions
            quiz_type=quiz_type
        )
        db.session.add(attempt)
        print(f"DEBUG User {user_id_for_logs}: QuizAttempt object created and added to session.")

        # --- 4. Update/Save Wrong Answers ---
        print(f"DEBUG User {user_id_for_logs}: Preparing to update/save {len(wrong_answer_ids_to_save)} wrong answers...")
        now = datetime.utcnow()
        if wrong_answer_ids_to_save:
            # ... (Keep the existing logic for finding existing wrongs and updating/creating new ones) ...
             # Query existing wrong answers for these specific vocab IDs for this user
            existing_wrongs = WrongAnswer.query.filter(
                WrongAnswer.user_id == current_user.id,
                WrongAnswer.vocabulary_id.in_(wrong_answer_ids_to_save)
            ).all()
            existing_wrongs_map = {wrong.vocabulary_id: wrong for wrong in existing_wrongs}
            print(f"DEBUG User {user_id_for_logs}: Found {len(existing_wrongs_map)} existing wrong answers to update.")

            for vocab_id in wrong_answer_ids_to_save:
                if vocab_id in vocab_map: # Ensure vocab data still exists
                    if vocab_id in existing_wrongs_map:
                        # Update existing record
                        wrong_record = existing_wrongs_map[vocab_id]
                        wrong_record.timestamp_last_wrong = now
                        wrong_record.incorrect_count = (wrong_record.incorrect_count or 0) + 1
                        db.session.add(wrong_record) # Add to session for update
                        print(f"  - Updating existing wrong answer for vocab_id {vocab_id}")
                    else:
                        # Create new record
                        new_wrong = WrongAnswer(
                            user_id=current_user.id,
                            vocabulary_id=vocab_id,
                            timestamp_last_wrong=now,
                            incorrect_count=1
                        )
                        db.session.add(new_wrong)
                        print(f"  - Creating new wrong answer for vocab_id {vocab_id}")
                else:
                     print(f"  - WARNING: Cannot save wrong answer for vocab_id {vocab_id} as it's not in vocab_map.")
        else:
            print(f"DEBUG User {user_id_for_logs}: No wrong answers to save/update.")


        # --- 5. Commit Database Transaction ---
        print(f"DEBUG User {user_id_for_logs}: Attempting db.session.commit()...")
        db.session.commit()
        print(f"DEBUG User {user_id_for_logs}: Database commit successful.")
        current_app.logger.info(f"User {user_id_for_logs}: Quiz results processing complete and committed. Score: {score}/{total_questions}")

        # --- 6. Return Results to Frontend ---
        print(f"DEBUG User {user_id_for_logs}: Returning score: {score}, total_questions: {total_questions}")
        return jsonify({
            'message': '测验结果已成功保存。(Results saved successfully.)',
            'score': score,
            'total_questions': total_questions, # Return the potentially adjusted total_questions
            'wrong_answers': wrong_answer_details_for_response
        }), 200

    except Exception as e:
        # --- Catch any exception during the process ---
        db.session.rollback() # Rollback any potential DB changes
        print(f"DEBUG User {user_id_for_logs}: EXCEPTION occurred: {e}")
        current_app.logger.error(f"User {user_id_for_logs}: Critical error processing quiz results: {e}", exc_info=True)
        return jsonify({'error': f'处理测验结果时发生内部错误: {str(e)}'}), 500
    finally:
        print(f"--- submit_quiz_results for User {user_id_for_logs} END ---") # End marker


@current_app.route('/api/vocabulary/<int:vocabulary_id>/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite(vocabulary_id):
    """
    切换当前用户对指定词汇的收藏状态。
    如果已收藏，则取消收藏；如果未收藏，则添加收藏。
    能较好地处理因前端重复提交导致的 IntegrityError。
    """
    log = current_app.logger
    user_id = current_user.id
    log.info(f"[Favorite Toggle] User {user_id} initiated toggle for vocab_id: {vocabulary_id}")

    # 确保词汇存在
    vocab_item = Vocabulary.query.get(vocabulary_id)
    if not vocab_item:
        log.warning(f"[Favorite Toggle] Vocabulary item with id {vocabulary_id} not found.")
        return jsonify({'success': False, 'error': '词汇不存在 (Vocabulary not found)'}), 404

    # 初始化将要返回的状态
    final_favorite_status = False

    try:
        # 1. 查询当前的收藏状态
        existing_favorite = UserFavoriteVocabulary.query.filter_by(
            user_id=user_id,
            vocabulary_id=vocabulary_id
        ).first()
        log.debug(f"[Favorite Toggle] Initial check found existing favorite: {existing_favorite is not None}")

        action_taken = None # 记录尝试的操作类型 ('add' or 'delete')

        if existing_favorite:
            # 2a. 如果已存在，准备删除（取消收藏）
            log.info(f"[Favorite Toggle] Action: Deleting existing favorite record (ID: {existing_favorite.id})")
            db.session.delete(existing_favorite)
            final_favorite_status = False # 期望的最终状态
            action_taken = 'delete'
        else:
            # 2b. 如果不存在，准备添加（收藏）
            log.info(f"[Favorite Toggle] Action: Adding new favorite record for user {user_id}, vocab {vocabulary_id}")
            new_favorite = UserFavoriteVocabulary(user_id=user_id, vocabulary_id=vocabulary_id)
            db.session.add(new_favorite)
            final_favorite_status = True # 期望的最终状态
            action_taken = 'add'

        # 3. 尝试提交更改
        log.debug("[Favorite Toggle] Attempting to commit database changes...")
        db.session.commit()
        log.info(f"[Favorite Toggle] Successfully {'unfavorited' if not final_favorite_status else 'favorited'} vocabulary {vocabulary_id} for user {user_id}.")

        # 4. 返回成功和最终状态
        return jsonify({'success': True, 'is_favorite': final_favorite_status})

    except IntegrityError as ie:
        # 5. 特别处理唯一约束冲突 (很可能是前端重复添加请求导致)
        db.session.rollback() # 必须先回滚失败的事务
        log.warning(f"[Favorite Toggle] IntegrityError encountered (likely concurrent add): {ie}")

        if action_taken == 'add':
            # 如果我们是想添加但遇到了冲突，说明记录其实已经存在了
            log.info("[Favorite Toggle] IntegrityError on add implies item IS already favorited. Returning success with is_favorite=True.")
            # 可以选择再次查询确认，但通常可以直接返回 True
            # final_check = UserFavoriteVocabulary.query.filter_by(user_id=user_id, vocabulary_id=vocabulary_id).count() > 0
            return jsonify({'success': True, 'is_favorite': True}) # 返回最终状态为 True
        else:
            # 如果是在删除时遇到 IntegrityError (理论上不太可能，除非约束或表结构异常)
            log.error("[Favorite Toggle] Unexpected IntegrityError during delete operation.")
            return jsonify({'success': False, 'error': '数据库约束错误 (DB Constraint Error on delete)'}), 500

    except Exception as e:
        # 6. 处理其他所有数据库异常或未知错误
        db.session.rollback() # 回滚事务
        log.error(f"[Favorite Toggle] Generic error during favorite toggle for user {user_id}, vocab {vocabulary_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': '数据库操作时发生错误。(Database operation failed.)'}), 500

# === API Routes for Wrong Answer Enhancements ===
@current_app.route('/api/wrong_answer/<int:wrong_answer_id>/toggle_mark', methods=['POST'])
@login_required
def toggle_mark_wrong_answer(wrong_answer_id):
    """API endpoint to mark or unmark a wrong answer item."""
    # ... (Keep existing toggle_mark_wrong_answer logic) ...
    wrong_answer = WrongAnswer.query.get_or_404(wrong_answer_id)
    if wrong_answer.user_id != current_user.id: abort(403)
    try:
        wrong_answer.is_marked = not wrong_answer.is_marked
        db.session.commit()
        return jsonify({'success': True, 'is_marked': wrong_answer.is_marked})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggle mark WA {wrong_answer_id}: {e}")
        return jsonify({'success': False, 'error': 'DB error'}), 500


@current_app.route('/api/wrong_answer/<int:wrong_answer_id>/set_category', methods=['POST'])
@login_required
def set_category_wrong_answer(wrong_answer_id):
    """API endpoint to set the category for a wrong answer item."""
    # ... (Keep existing set_category_wrong_answer logic) ...
    wrong_answer = WrongAnswer.query.get_or_404(wrong_answer_id)
    if wrong_answer.user_id != current_user.id: abort(403)
    data = request.get_json()
    if not data or 'category' not in data: return jsonify({'success': False, 'error': 'Missing category'}), 400
    new_category = data.get('category')
    if new_category is not None and new_category not in ALLOWED_WRONG_ANSWER_CATEGORIES:
         return jsonify({'success': False, 'error': 'Invalid category'}), 400
    try:
        wrong_answer.category = new_category
        db.session.commit()
        return jsonify({'success': True, 'category': wrong_answer.category})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error set category WA {wrong_answer_id}: {e}")
        return jsonify({'success': False, 'error': 'DB error'}), 500


# === Admin Routes ===

@current_app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
     """Admin dashboard homepage."""
     now = datetime.utcnow()
     # Pass necessary data if needed, e.g., user count, lesson count
     return render_template('admin/admin.html', current_time=now)


@current_app.route('/admin/vocabulary', endpoint='manage_vocabulary')
@login_required
@admin_required
def manage_vocabulary():
    """Admin page to view/manage all vocabulary."""
    vocab_list = []
    favorited_ids = set() # Needed for the template, even if admin doesn't favorite
    try:
        vocab_list = Vocabulary.query.order_by(Vocabulary.lesson_number, Vocabulary.id).all()
        # Admins might also want to see which words *they* favorited on this page
        if current_user.is_authenticated:
            favorited_ids = {fav.vocabulary_id for fav in UserFavoriteVocabulary.query.filter_by(user_id=current_user.id).with_entities(UserFavoriteVocabulary.vocabulary_id).all()}

    except Exception as e:
        current_app.logger.error(f"Error fetching vocabulary for management page: {e}", exc_info=True)
        flash("加载词汇列表时出错。(Error loading vocabulary list.)", "danger")

    now = datetime.utcnow()
    # Pass favorited_ids here as well
    return render_template('admin/manage_vocabulary.html',
                           title='管理词汇 (Manage Vocabulary)',
                           vocabulary=vocab_list,
                           favorited_ids=favorited_ids, # Pass favorite status for the admin user
                           current_time=now)


# --- 完善用户管理路由 ---
@current_app.route('/admin/users')
@login_required        # 必须登录
@root_admin_required   # 必须是配置文件中指定的 ROOT_ADMIN_USERNAME
def manage_users():
    """显示用户列表，供超级管理员管理普通管理员权限。"""
    log = current_app.logger
    users_list = []
    root_username = current_app.config.get('ROOT_ADMIN_USERNAME', 'root') # 获取配置的根用户名
    log.debug(f"Root admin '{current_user.username}' accessing user management. Configured ROOT_ADMIN_USERNAME: '{root_username}'")

    try:
        # 查询所有用户，排除根管理员自己，按用户名排序
        users_list = User.query.filter(User.username != root_username)\
                              .order_by(User.username).all()
        log.debug(f"Fetched {len(users_list)} users for management page.")
    except Exception as e:
        log.error(f"Error fetching users for admin management by {current_user.username}: {e}", exc_info=True)
        flash("加载用户列表失败。(Failed to load user list.)", "danger")

    now = datetime.utcnow() # For footer
    return render_template('admin/manage_users.html',
                           title="管理用户 (Manage Users)",
                           users=users_list, # 传递用户列表
                           root_admin_username=root_username, # 传递根用户名给模板（虽然模板里可能不需要）
                           current_time=now)


@current_app.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST']) # 必须是 POST 请求
@login_required         # 必须登录
@root_admin_required    # 必须是根管理员才能执行此操作
# @csrf.exempt # 如果你的表单没有 CSRF token，可能需要取消注释，但更推荐使用表单或 AJAX+Token
def toggle_admin_status(user_id):
    """切换指定用户的 is_admin 状态。"""
    log = current_app.logger
    root_username = current_app.config.get('ROOT_ADMIN_USERNAME', 'root')
    log.info(f"Root admin '{current_user.username}' attempting to toggle admin status for user ID {user_id}")

    # 1. 查找目标用户
    user_to_modify = User.query.get_or_404(user_id) # 如果用户不存在，返回 404

    # 2. 安全检查：不能修改自己，也不能修改根管理员账号的状态
    if user_to_modify.id == current_user.id:
         log.warning(f"User '{current_user.username}' attempted to modify their own admin status.")
         flash("你不能修改自己的管理员状态。(You cannot modify your own admin status.)", "warning")
         return redirect(url_for('manage_users'))
    elif user_to_modify.username == root_username:
         log.warning(f"User '{current_user.username}' attempted to modify root admin '{root_username}' status.")
         flash("不能修改根管理员的状态。(Cannot modify the root admin's status.)", "danger")
         return redirect(url_for('manage_users'))

    # 3. 执行切换并提交数据库
    try:
        original_status = user_to_modify.is_admin
        user_to_modify.is_admin = not original_status # 切换布尔值
        db.session.add(user_to_modify) # 标记对象已更改
        db.session.commit() # 提交更改

        action_text = "授予 (granted)" if user_to_modify.is_admin else "撤销 (revoked)"
        log.info(f"Successfully {action_text} admin status for user '{user_to_modify.username}' (ID: {user_id}) by '{current_user.username}'.")
        flash(f"用户 '{user_to_modify.username}' 的管理员权限已被 {action_text}。(Admin status for user '{user_to_modify.username}' has been {action_text}.)", "success")
    except Exception as e:
        db.session.rollback() # 出错时回滚
        log.error(f"Error toggling admin status for user {user_id} by '{current_user.username}': {e}", exc_info=True)
        flash("修改管理员状态时出错。(Error changing admin status.)", "danger")

    # 4. 重定向回用户列表页面
    return redirect(url_for('manage_users'))


@current_app.route('/admin/process_pdf', methods=['POST'], endpoint='process_pdf_route_admin')
@login_required
@admin_required
def process_pdf_route_admin():
    """Handles the PDF processing request from the admin panel."""
    # ... (Keep existing, corrected process_pdf_route_admin logic) ...
    # Ensure this function correctly calls process_nce_pdf and updates DB
    # Placeholder for brevity, use your full implementation
    log = current_app.logger
    try:
        pdf_path = current_app.config.get('NCE_PDF_PATH')
        if not pdf_path or not os.path.exists(pdf_path):
             log.error(f"PDF Error: Path '{pdf_path}' not found/configured.")
             return jsonify({"error": "PDF 文件路径配置错误或文件不存在。"}), 500
        log.info(f"Admin '{current_user.username}' starting PDF process: {pdf_path}")
        results = process_nce_pdf(pdf_path) # This needs DB interaction
        # ... (Database update logic based on 'results' as shown previously) ...
        log.info("PDF processing finished and DB updated (logic assumed).")
        # Return a summary matching JS expectations
        dummy_summary = {
             "lessons_added": 0, "lessons_updated": 0, "lesson_errors": 0,
             "vocab_added": 0, "vocab_updated": 0, "vocab_skipped": 0, "vocab_errors": 0
         }
        return jsonify({
            "message": "PDF 处理完成 (模拟)。",
            "lesson_summary": dummy_summary,
            "vocabulary_summary": dummy_summary
        }), 200
    except Exception as e:
         log.error(f"Unhandled error during PDF processing: {e}", exc_info=True)
         return jsonify({"error": f"处理 PDF 时发生内部错误: {str(e)}"}), 500


# === Optional TTS Routes ===

@current_app.route('/audio/<path:filename>')
@login_required
def serve_audio(filename):
    """Serves previously generated audio files."""
    cache_dir_base = current_app.config.get('TTS_AUDIO_CACHE_DIR', 'tts_cache')
    cache_dir = os.path.join(current_app.instance_path, cache_dir_base)
    current_app.logger.debug(f"Attempting to serve audio: {os.path.join(cache_dir, filename)}")
    try:
        return send_from_directory(cache_dir, filename, as_attachment=False)
    except FileNotFoundError: abort(404)
    except Exception as e:
        current_app.logger.error(f"Error serving audio {filename}: {e}")
        abort(500)


@current_app.route('/api/speak/lesson/<int:lesson_number>')
@login_required
def speak_lesson_text(lesson_number):
    """API endpoint to generate (if needed) and serve TTS audio for a lesson."""
    # ... (Keep existing speak_lesson_text logic using tts_utils) ...
    # Placeholder for brevity
    log = current_app.logger
    lesson = Lesson.query.filter_by(lesson_number=lesson_number).first()
    if not lesson or not lesson.text_en: return jsonify({"error": "Lesson text not found."}), 404
    audio_filepath = get_audio_filename(lesson_number)
    if not audio_filepath: return jsonify({"error": "Config error for audio path."}), 500
    generated_path = generate_and_save_audio_if_not_exists(lesson_number, lesson.text_en, 'en')
    if not generated_path: return jsonify({"error": "Failed to generate/retrieve audio."}), 500
    try:
        directory = os.path.dirname(generated_path)
        filename = os.path.basename(generated_path)
        return send_from_directory(directory, filename, mimetype='audio/wav')
    except Exception as e:
         log.error(f"Error sending audio file {generated_path}: {e}")
         return jsonify({"error": "Could not send audio file."}), 500

# === 修改：处理用户录音上传的 API ===
@current_app.route('/api/lesson/<int:lesson_number>/upload_recording', methods=['POST'])
@login_required
def upload_user_recording(lesson_number):
    """接收用户对特定课程的录音并保存到用户专属目录（覆盖旧的）。"""
    user_id = current_user.id
    current_app.logger.info(f"Upload request for lesson {lesson_number} from user {user_id}")

    # --- 1. 检查文件 ---
    if 'audio_data' not in request.files: return jsonify({'error': 'No audio_data part'}), 400
    file = request.files['audio_data']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400

    # --- 2. (可选) 检查课程 ---
    #lesson = Lesson.query.get(lesson_number)
    #if not lesson: return jsonify({'error': 'Lesson not found'}), 404

    # --- 3. 确定用户专属保存目录 ---
    base_folder = current_app.config.get('USER_RECORDINGS_BASE_FOLDER')
    if not base_folder: return jsonify({'error': 'User recordings base folder not configured'}), 500
    # --- 创建用户子目录路径 ---
    user_specific_folder = os.path.join(base_folder, f"user_{user_id}")
    # -------------------------

    # --- 4. 生成固定文件名 (课程相关) ---
    original_filename = secure_filename(file.filename or 'audio')
    _, ext = os.path.splitext(original_filename)
    # 保留之前的扩展名推断逻辑，或者直接用上传时的MIME类型推断
    possible_extensions = ['.webm', '.ogg', '.wav'] # 默认尝试 webm
    if not ext or ext.lower() not in possible_extensions:
        # 尝试从 Content-Type 获取 (如果浏览器发送了)
        content_type = file.content_type
        if content_type == 'audio/webm': ext = '.webm'
        elif content_type == 'audio/ogg': ext = '.ogg'
        elif content_type == 'audio/wav': ext = '.wav'
        else: ext = '.webm' # 最终默认 .webm
        current_app.logger.warning(f"Cannot determine extension reliably, using '{ext}'")

    filename = f"lesson_{lesson_number}{ext}" # 文件名只包含课程号和扩展名
    # --------------------------------

    # --- 5. 确保用户子目录存在并保存文件 ---
    try:
        os.makedirs(user_specific_folder, exist_ok=True) # 创建用户子目录（如果不存在）
        filepath = os.path.join(user_specific_folder, filename) # 完整保存路径
        current_app.logger.info(f"Attempting to save user recording to: {filepath}")
        file.save(filepath) # 保存文件，会覆盖同名文件
        current_app.logger.info(f"User recording saved successfully: {filepath}")
        return jsonify({'success': True, 'message': '录音已保存。'}), 200
    except OSError as e:
         current_app.logger.error(f"Could not create directory or save file '{filepath}': {e}", exc_info=True)
         return jsonify({'success': False, 'error': '创建目录或保存文件时出错。'}), 500
    except Exception as e:
        current_app.logger.error(f"Error saving recording file '{filepath}': {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'保存录音时出错: {e}'}), 500

# === 修改：获取用户录音的 API ===
@current_app.route('/user_recording/<int:user_id>/<int:lesson_number>')
@login_required
def get_user_recording(user_id, lesson_number):
    """提供特定用户特定课程的录音文件。"""
    # --- 权限检查 (保持不变) ---
    if user_id != current_user.id and not current_user.is_admin:
         return jsonify({"error": "Forbidden"}), 403

    # --- 确定用户专属目录 ---
    base_folder = current_app.config.get('USER_RECORDINGS_BASE_FOLDER')
    if not base_folder: return jsonify({"error": "User recordings base folder not configured"}), 500
    user_specific_folder = os.path.join(base_folder, f"user_{user_id}")
    # -------------------------

    # --- 在用户目录中查找文件 ---
    possible_extensions = ['.webm', '.ogg', '.wav'] # 与上传逻辑匹配
    found_file = None
    for ext in possible_extensions:
         # 文件名现在只包含课程号和扩展名
         filename = f"lesson_{lesson_number}{ext}"
         filepath = os.path.join(user_specific_folder, filename)
         if os.path.exists(filepath):
              found_file = filename # 只需要文件名，send_from_directory 需要目录+文件名
              break

    if found_file:
         current_app.logger.debug(f"Serving user recording: {found_file} from {user_specific_folder}")
         # 使用 send_from_directory 发送文件
         return send_from_directory(user_specific_folder, found_file, as_attachment=False)
    else:
         current_app.logger.warning(f"User recording not found for user {user_id}, lesson {lesson_number} in {user_specific_folder}")
         return jsonify({"error": "Recording not found"}), 404


# --- 修改：处理和评分 API (由按钮触发) ---
@current_app.route('/api/lesson/<int:lesson_number>/process_recording', methods=['POST']) # 保持 POST
@login_required
def process_user_recording(lesson_number):
    """处理指定课程的用户录音，进行 STT 和评分，并将结果存入数据库。"""
    user_id = current_user.id
    current_app.logger.info(f"Processing recording request for lesson {lesson_number}, user {user_id}")

    # --- 1. 找到录音文件 (逻辑不变) ---
    base_folder = current_app.config.get('USER_RECORDINGS_BASE_FOLDER')
    if not base_folder: return jsonify({'success': False, 'error': '录音文件夹未配置'}), 500
    user_specific_folder = os.path.join(base_folder, f"user_{user_id}")
    possible_extensions = current_app.config.get('PREGENERATED_AUDIO_EXTENSIONS', []) + ['.webm', '.ogg', '.wav', '.mp3', '.m4a', '.aac']
    found_filepath = None; filename_only = None
    for ext in set(possible_extensions):
         filename = f"lesson_{lesson_number}{ext}"
         filepath = os.path.join(user_specific_folder, filename)
         if os.path.exists(filepath): found_filepath = filepath; filename_only = filename; break
    if not found_filepath: return jsonify({'success': False, 'error': '找不到对应的录音文件'}), 404

    # --- 2. 获取标准课文 (逻辑不变) ---
    lesson = Lesson.query.filter_by(lesson_number=lesson_number, source_book=2).first()
    if not lesson or not lesson.text_en: return jsonify({'success': False, 'error': '找不到标准课文'}), 404
    standard_text = lesson.text_en

    # --- 3. 调用评分模块 (逻辑不变) ---
    try:
        evaluation_result = evaluate_audio_recording(found_filepath, standard_text)
    except FileNotFoundError as e: return jsonify({'success': False, 'error': f'评估失败：找不到文件 - {e}'}), 404
    except ValueError as e: return jsonify({'success': False, 'error': f'评估失败：输入无效 - {e}'}), 400
    except Exception as e: current_app.logger.error(f"Crit err processing {found_filepath}: {e}", exc_info=True); return jsonify({'success': False, 'error': f'处理或评分时发生内部错误'}), 500

    # --- 4. 保存/更新评分记录到数据库 ---
    try:
        # 查找是否已存在该用户该课程的评分记录
        score_record = PronunciationScore.query.filter_by(user_id=user_id, lesson_number=lesson_number).first()

        if score_record:
            # 如果存在，则更新记录
            current_app.logger.info(f"Updating existing score record for user {user_id}, lesson {lesson_number}")
            score_record.final_score = evaluation_result.get('final_score')
            score_record.accuracy_score = evaluation_result.get('accuracy')
            score_record.fluency_score = evaluation_result.get('fluency_score')
            score_record.speed_score = evaluation_result.get('speed_score') # 需要评分函数返回
            score_record.recognized_text = evaluation_result.get('recognized_text')
            score_record.wer = evaluation_result.get('wer')
            score_record.speech_rate_wps = evaluation_result.get('speech_rate_wps')
            score_record.timestamp = datetime.utcnow() # 更新时间戳
        else:
            # 如果不存在，则创建新记录
            current_app.logger.info(f"Creating new score record for user {user_id}, lesson {lesson_number}")
            score_record = PronunciationScore(
                user_id=user_id,
                lesson_number=lesson_number,
                final_score = evaluation_result.get('final_score'),
                accuracy_score = evaluation_result.get('accuracy'),
                fluency_score = evaluation_result.get('fluency_score'),
                speed_score = evaluation_result.get('speed_score'),
                recognized_text = evaluation_result.get('recognized_text'),
                wer = evaluation_result.get('wer'),
                speech_rate_wps = evaluation_result.get('speech_rate_wps'),
                # timestamp 使用 default
            )
            db.session.add(score_record)

        db.session.commit()
        current_app.logger.info("Pronunciation score saved/updated successfully.")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving pronunciation score to DB: {e}", exc_info=True)
        # 虽然评分计算成功了，但保存失败，也需要告知前端
        return jsonify({
            'success': False, # 标记操作未完全成功
            'error': '评分计算完成，但保存结果时出错。',
            **evaluation_result # 仍然返回评分结果供查看
            }), 500 # 返回服务器错误

    # --- 5. 返回包含详细结果的 JSON ---
    return jsonify({
        'success': True,
        'message': '评分完成并已保存。(Scoring complete and saved)',
        **evaluation_result
    }), 200