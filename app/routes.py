# app/routes.py - Complete Version with User Auth and Learning Records

import os
import random
from datetime import datetime
from flask import (current_app, render_template, request, jsonify, Blueprint,
                   redirect, url_for, session, flash, abort)
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy.orm import joinedload
from urllib.parse import urlsplit # <-- 添加这行

from . import db                     # Import db instance from __init__.py
from .models import Vocabulary, Lesson, User, QuizAttempt, WrongAnswer # Import all models
from .forms import LoginForm, RegistrationForm    # Import forms
from .pdf_parser import process_nce_pdf # Import your PDF processing function
from .decorators import admin_required, root_admin_required # 导入装饰器
from flask import abort # 导入 abort
from flask import jsonify, request # Ensure jsonify and request are imported
from .models import WrongAnswer, Vocabulary # Ensure WrongAnswer is imported

from flask import send_from_directory, jsonify, abort, current_app, url_for # 修改导入，增加 send_from_directory
from .models import Lesson, Vocabulary # 导入数据库模型
from flask import jsonify, current_app, flash, redirect, url_for, send_from_directory # 导入 send_from_directory
from flask_login import login_required, current_user
from .models import Lesson # 只需要 Lesson 模型
# --- 修改导入 ---
from .tts_utils import generate_and_save_audio_if_not_exists, get_audio_filename
# ----------------
from .decorators import admin_required
from flask import send_from_directory
import os
from .tts_utils import get_audio_filename # 导入辅助函数

# --- 主要应用路由 ---

@current_app.route('/')
def index():
    """首页，显示课程列表"""
    lesson_numbers = []
    try:
        # 优先从 Lesson 表获取，确保有课文的课程才显示
        lessons_q = Lesson.query.with_entities(Lesson.lesson_number).distinct().order_by(Lesson.lesson_number).all()
        if lessons_q:
            lesson_numbers = [l[0] for l in lessons_q]
        else: # 后备：如果 Lesson 表为空，尝试从 Vocabulary 获取
             lessons_q_vocab = db.session.query(Vocabulary.lesson_number.distinct()).order_by(Vocabulary.lesson_number).all()
             lesson_numbers = [l[0] for l in lessons_q_vocab]
        current_app.logger.debug(f"Fetched distinct lessons for index: {lesson_numbers}")
    except Exception as e:
        current_app.logger.error(f"Error fetching lessons from DB for index: {e}", exc_info=True)
    now = datetime.utcnow()
    # current_user 由 Flask-Login 提供，可以在模板中直接使用
    return render_template('index.html', lessons=lesson_numbers, current_time=now)

@current_app.route('/audio/<path:filename>')
@login_required # 或者根据需要开放权限
def serve_audio(filename):
    # 从配置获取基础缓存目录名
    cache_dir_base = current_app.config.get('TTS_AUDIO_CACHE_DIR', 'tts_cache')
    cache_dir = os.path.join(current_app.instance_path, cache_dir_base)
    current_app.logger.debug(f"Attempting to serve audio from: {cache_dir}, filename: {filename}")
    try:
        # 使用 send_from_directory 安全地提供文件
        return send_from_directory(cache_dir, filename, as_attachment=False) # as_attachment=False 让浏览器直接播放
    except FileNotFoundError:
        current_app.logger.error(f"Audio file not found: {os.path.join(cache_dir, filename)}")
        abort(404)
    except Exception as e:
         current_app.logger.error(f"Error serving audio file {filename}: {e}", exc_info=True)
         abort(500)

@current_app.route('/lesson/<int:lesson_number>')
def view_lesson(lesson_number):
    """显示指定 Lesson 的课文内容和预生成的音频（如果存在）"""
    current_app.logger.info(f"Request received for lesson {lesson_number}")
    try:
        lesson_data = Lesson.query.filter_by(lesson_number=lesson_number).first_or_404()
    except Exception as e:
         current_app.logger.error(f"Error fetching lesson {lesson_number} from DB: {e}", exc_info=True)
         abort(500)

    audio_url = None
    # --- 检查预生成的音频文件是否存在 ---
    expected_audio_path = get_audio_filename(lesson_number) # 获取预期绝对路径
    if expected_audio_path and os.path.exists(expected_audio_path):
        audio_filename = os.path.basename(expected_audio_path)
        # 使用新的 serve_audio 路由生成 URL
        audio_url = url_for('serve_audio', filename=audio_filename)
        current_app.logger.debug(f"Found pre-generated audio for lesson {lesson_number}. URL: {audio_url}")
    else:
        current_app.logger.info(f"Pre-generated audio not found for lesson {lesson_number} at {expected_audio_path}")

    now = datetime.utcnow() # 如果用了 context processor 就不用传了
    return render_template('lesson_text.html',
                           lesson=lesson_data,
                           audio_url=audio_url, # 传递 URL 或 None
                           current_time=now)

@current_app.route('/lessons', endpoint='view_lessons') # 指定 endpoint 为 view_lessons
def view_lessons():
    """显示所有课程的列表页面"""
    lessons_data = []
    try:
        # 查询所有 Lesson 记录，按课号排序
        # 可以只选择需要的列以提高效率，例如 lesson_number 和 title (如果模型中有 title)
        # 这里我们先获取完整的对象列表
        lessons_data = Lesson.query.order_by(Lesson.lesson_number).all()
        # 如果 Lesson 表可能为空，但 Vocabulary 表有数据，可以像 index 页一样做后备查询
        if not lessons_data:
             lessons_q_vocab = db.session.query(Vocabulary.lesson_number.distinct()).order_by(Vocabulary.lesson_number).all()
             # 如果需要显示更多信息，这里可能需要调整，但至少能获得课号列表
             lessons_data = [{'lesson_number': l[0]} for l in lessons_q_vocab] # 创建一个类似 Lesson 对象的结构列表
        current_app.logger.debug(f"Fetched all lessons for /lessons page.")
    except Exception as e:
        current_app.logger.error(f"Error fetching lessons from DB for /lessons page: {e}", exc_info=True)
        flash('加载课程列表时出错。(Error loading lesson list.)', 'danger')
        # 可以选择返回错误页面或空列表
        # return render_template('error.html', message='无法加载课程列表'), 500

    return render_template('lessons_list.html', title='课程列表 (Lesson List)', lessons=lessons_data)


# --- TTS API 路由 ---
@current_app.route('/api/speak/lesson/<int:lesson_number>')
@login_required # 或者移除，如果允许未登录用户听
def speak_lesson_text(lesson_number):
    """API endpoint to generate (if needed) and serve TTS audio for a lesson."""
    log = current_app.logger
    log.info(f"Request received for TTS audio for lesson {lesson_number}")

    # 1. Get Lesson Text from Database
    lesson = Lesson.query.filter_by(lesson_number=lesson_number).first()
    if not lesson or not lesson.text_en:
        log.warning(f"Lesson {lesson_number} not found or has no English text.")
        return jsonify({"error": "Lesson text not found."}), 404

    # 2. Determine Target Filename (using helper)
    audio_filepath = get_audio_filename(lesson_number)
    if not audio_filepath:
        # get_audio_filename 内部会记录错误
        return jsonify({"error": "Could not determine audio file path configuration."}), 500

    log.debug(f"Request for lesson {lesson_number} audio. Checking path: {audio_filepath}")

    # --- 移除对 get_tts_instance() 的调用 ---
    # if get_tts_instance() is None: # <--- 删除或注释掉这一行
    #    log.error("TTS instance is not available.") # <--- 删除或注释掉这一行
    #    return jsonify({"error": "TTS service is not available."}), 503 # Service Unavailable # <--- 删除或注释掉这一行
    # --------------------------------------

    # 3. Generate Audio *Only If It Doesn't Exist* using the new function
    # The function now handles initialization internally if needed.
    # Pass the actual text to the function.
    language_code = 'en' # Assuming English text
    generated_path = generate_and_save_audio_if_not_exists(
        lesson_number=lesson_number,
        text=lesson.text_en,
        language=language_code
    )

    # 4. Check if generation succeeded (or file already existed)
    # generate_and_save_audio_if_not_exists returns None on failure
    if not generated_path:
         log.error(f"Failed to generate or find audio file for lesson {lesson_number} at {audio_filepath}")
         return jsonify({"error": "Failed to generate or retrieve audio."}), 500 # Internal Server Error

    # 5. Serve the File using send_from_directory
    log.info(f"Serving audio file: {generated_path}")
    try:
        # send_from_directory 需要目录路径和文件名
        directory = os.path.dirname(generated_path)
        filename = os.path.basename(generated_path)
        log.debug(f"Serving from directory: {directory}, filename: {filename}")
        return send_from_directory(directory, filename, mimetype='audio/wav')
    except Exception as e:
         log.error(f"Error sending file {generated_path}: {e}", exc_info=True)
         return jsonify({"error": "Could not send audio file."}), 500

# --- API 路由 ---

@current_app.route('/api/quiz', methods=['GET'])
def get_quiz():
    """
    根据请求的课程号、题目数量和类型，生成测验题目列表 (JSON)。
    """
    # ... (此函数逻辑保持和之前版本一致，确保返回 part_of_speech) ...
    try:
        lessons_str = request.args.get('lessons')
        num_questions_str = request.args.get('count', '10') # Get as string first
        quiz_type = request.args.get('type', 'cn_to_en')

        if not lessons_str:
            return jsonify({"error": "Missing 'lessons' parameter"}), 400

        try:
             lesson_numbers = [int(n) for n in lessons_str.split(',')]
             num_questions = int(num_questions_str)
             if num_questions <= 0: num_questions = 10 # Default if invalid count
        except ValueError:
             return jsonify({"error": "Invalid 'lessons' or 'count' parameter format (should be integers)."}), 400


        # Query database using SQLAlchemy ORM
        all_vocab = Vocabulary.query.filter(Vocabulary.lesson_number.in_(lesson_numbers)).all()

        if not all_vocab:
            return jsonify({"error": "No vocabulary found for the selected lessons"}), 404

        num_questions = min(num_questions, len(all_vocab))
        selected_vocab = random.sample(all_vocab, num_questions)

        quiz_questions = []
        for item in selected_vocab:
            question = ""
            answer = ""
            if quiz_type == 'cn_to_en':
                question = item.chinese_translation
                answer = item.english_word
            elif quiz_type == 'en_to_cn':
                question = item.english_word
                answer = item.chinese_translation
            else:
                # Default or handle unknown type
                question = item.chinese_translation
                answer = item.english_word

            pos = item.part_of_speech

            quiz_questions.append({
                "id": item.id, # Vocabulary ID
                "lesson": item.lesson_number,
                "question": question,
                "part_of_speech": pos,
                "correct_answer": answer # Note: Sending answer to client for JS scoring
            })
        return jsonify(quiz_questions)

    except Exception as e:
        current_app.logger.error(f"Error in /api/quiz generation: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while generating quiz."}), 500


@current_app.route('/api/submit_quiz', methods=['POST'])
@login_required # 必须登录才能提交
def submit_quiz_results():
    """
    接收前端提交的测验结果(JSON)，在后端评分，保存测试记录和错题。
    返回评分结果 (JSON)。
    """
    current_app.logger.info(f"User {current_user.username} (ID: {current_user.id}) submitting quiz results.")
    data = request.get_json()

    # 验证输入数据格式
    if not data or not isinstance(data.get('answers'), dict) or not isinstance(data.get('quiz_context'), dict):
        current_app.logger.warning(f"Submit quiz from user {current_user.id} rejected due to invalid data format.")
        return jsonify({'error': 'Invalid data format received.'}), 400

    user_answers = data['answers'] # e.g., {"<vocab_id>": "user_answer", ...}
    quiz_context = data['quiz_context'] # e.g., {"lesson_ids": [1, 2], "quiz_type": "cn_to_en", "question_ids": [id1, id2...]}
    question_ids = quiz_context.get('question_ids', [])
    quiz_type = quiz_context.get('quiz_type', 'cn_to_en') # 获取测试类型
    lesson_ids = quiz_context.get('lesson_ids', [])      # 获取涉及的课程ID

    if not user_answers or not question_ids:
         current_app.logger.warning(f"Submit quiz from user {current_user.id} rejected due to missing answers or question IDs.")
         return jsonify({'error': 'Missing answers or question list.'}), 400

    total_questions = len(question_ids)
    score = 0
    wrong_answer_details_for_response = [] # 用于返回给前端的错题信息
    wrong_answer_ids_to_save = set()       # 用于保存到数据库的错题 Vocab ID 集合

    try:
        # 1. 查询本次测试涉及的所有词汇项 (一次性查询)
        vocab_items = Vocabulary.query.filter(Vocabulary.id.in_(question_ids)).all()
        if len(vocab_items) != len(question_ids):
             current_app.logger.warning(f"Mismatch between requested question IDs ({len(question_ids)}) and found vocab items ({len(vocab_items)}) for user {current_user.id}.")
             # 可以选择继续处理找到的，或者返回错误

        # 构建词汇字典方便查找
        vocab_map = {item.id: item for item in vocab_items}

        # 2. 后端评分并记录错题信息
        for vocab_id_str, user_answer in user_answers.items():
            try:
                vocab_id = int(vocab_id_str)
                if vocab_id in vocab_map:
                    item = vocab_map[vocab_id]
                    # 根据 quiz_type 确定正确答案
                    correct_answer = item.english_word if quiz_type == 'cn_to_en' else item.chinese_translation

                    # 进行评分 (不区分大小写, 去除首尾空格)
                    user_answer_cleaned = user_answer.strip() if user_answer else ""
                    if user_answer_cleaned.lower() == correct_answer.lower():
                        score += 1
                    else:
                        # 记录错题 ID 用于存库
                        wrong_answer_ids_to_save.add(vocab_id)
                        # 记录错题详情用于返回给前端
                        wrong_answer_details_for_response.append({
                            'vocab_id': vocab_id,
                            'question': item.chinese_translation if quiz_type == 'cn_to_en' else item.english_word,
                            'part_of_speech': item.part_of_speech,
                            'user_answer': user_answer, # 返回用户原始答案
                            'correct_answer': correct_answer
                        })
                else:
                    current_app.logger.warning(f"Vocab ID {vocab_id} from user answers not found in vocab_map for user {current_user.id}.")
            except ValueError:
                 current_app.logger.warning(f"Invalid vocab ID format in answers: {vocab_id_str} for user {current_user.id}")
            except Exception as scoring_ex:
                 current_app.logger.error(f"Error scoring question vocab_id={vocab_id_str} for user {current_user.id}: {scoring_ex}", exc_info=True)

        # 3. 保存测试记录 (QuizAttempt)
        attempt = QuizAttempt(
            user_id=current_user.id,
            lessons_attempted=",".join(map(str, sorted(list(set(lesson_ids))))),
            score=score,
            total_questions=total_questions,
            quiz_type=quiz_type
        )
        db.session.add(attempt)
        current_app.logger.debug(f"Attempt record created for user {current_user.id}.")

        # 4. 更新/保存错题记录 (WrongAnswer)
        now = datetime.utcnow()
        if wrong_answer_ids_to_save:
            # 查询这些错题是否已在用户的错题本中
            existing_wrongs = WrongAnswer.query.filter(
                WrongAnswer.user_id == current_user.id,
                WrongAnswer.vocabulary_id.in_(wrong_answer_ids_to_save)
            ).all()
            existing_wrongs_map = {wrong.vocabulary_id: wrong for wrong in existing_wrongs}

            for vocab_id in wrong_answer_ids_to_save:
                if vocab_id in existing_wrongs_map:
                    # 更新记录
                    wrong_record = existing_wrongs_map[vocab_id]
                    wrong_record.timestamp_last_wrong = now
                    wrong_record.incorrect_count = (wrong_record.incorrect_count or 0) + 1
                    db.session.add(wrong_record) # 标记为更新
                    current_app.logger.debug(f"Updating wrong answer: User {current_user.id}, Vocab {vocab_id}")
                else:
                    # 创建新记录
                    new_wrong = WrongAnswer(
                        user_id=current_user.id,
                        vocabulary_id=vocab_id,
                        timestamp_last_wrong=now,
                        incorrect_count=1
                    )
                    db.session.add(new_wrong)
                    current_app.logger.debug(f"Creating wrong answer: User {current_user.id}, Vocab {vocab_id}")

        # 5. 提交数据库
        db.session.commit()
        current_app.logger.info(f"Quiz results committed for user {current_user.id}. Score: {score}/{total_questions}")

        # 6. 返回结果给前端
        return jsonify({
            'message': 'Results saved successfully.',
            'score': score,
            'total_questions': total_questions,
            'wrong_answers': wrong_answer_details_for_response # 返回详细错题信息
        }), 200

    except Exception as e:
        db.session.rollback() # 发生任何错误都要回滚
        current_app.logger.error(f"Critical error in submit_quiz_results for user {current_user.id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save results due to an internal error.'}), 500


# --- Define allowed categories (can be moved to config.py later) ---
ALLOWED_WRONG_ANSWER_CATEGORIES = ["重点复习", "易混淆", "拼写困难", "用法模糊", "暂不复习"]

@current_app.route('/wrong_answers')
@login_required
def wrong_answers():
    """显示用户的错题本"""
    try:
        wrong_answer_records = WrongAnswer.query.filter_by(user_id=current_user.id)\
                                            .options(joinedload(WrongAnswer.vocabulary_item))\
                                            .order_by(WrongAnswer.timestamp_last_wrong.desc()).all()
        return render_template('wrong_answers.html',
                               title='错题本 (Wrong Answers)',
                               wrong_answers=wrong_answer_records,
                               allowed_categories=ALLOWED_WRONG_ANSWER_CATEGORIES)
    except Exception as e:
        current_app.logger.error(f"Error fetching wrong answers for user {current_user.id}: {e}", exc_info=True)
        flash('加载错题本时发生错误，请稍后重试。(An error occurred while loading wrong answers.)', 'danger')
        # --- 返回一个响应 ---
        # 选项 2.1: 重定向回首页
        return redirect(url_for('index'))
        # 选项 2.2: 渲染一个通用的错误模板 (需要创建 error.html)
        # return render_template('error.html', error_message='无法加载错题本'), 500
        # 选项 2.3: 中止请求并显示服务器错误页面
        # abort(500) # 需要导入 abort from flask


# --- NEW API Route: Toggle Mark Status ---
@current_app.route('/api/wrong_answer/<int:wrong_answer_id>/toggle_mark', methods=['POST'])
@login_required
# @csrf.exempt # Uncomment if using Flask-WTF CSRF globally and calling via basic fetch without form
def toggle_mark_wrong_answer(wrong_answer_id):
    """API endpoint to mark or unmark a wrong answer item."""
    wrong_answer = WrongAnswer.query.get_or_404(wrong_answer_id)

    # Security check: Ensure the item belongs to the current user
    if wrong_answer.user_id != current_user.id:
        current_app.logger.warning(f"User {current_user.id} attempted to modify wrong answer {wrong_answer_id} owned by user {wrong_answer.user_id}")
        return jsonify({'success': False, 'error': 'Permission denied'}), 403

    try:
        wrong_answer.is_marked = not wrong_answer.is_marked
        db.session.add(wrong_answer)
        db.session.commit()
        current_app.logger.info(f"User {current_user.id} toggled mark status for wrong answer {wrong_answer_id} to {wrong_answer.is_marked}")
        return jsonify({'success': True, 'is_marked': wrong_answer.is_marked})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling mark status for wrong answer {wrong_answer_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# --- NEW API Route: Set Category ---
@current_app.route('/api/wrong_answer/<int:wrong_answer_id>/set_category', methods=['POST'])
@login_required
# @csrf.exempt # Uncomment if using Flask-WTF CSRF globally and calling via basic fetch without form
def set_category_wrong_answer(wrong_answer_id):
    """API endpoint to set the category for a wrong answer item."""
    wrong_answer = WrongAnswer.query.get_or_404(wrong_answer_id)
    data = request.get_json()

    if not data or 'category' not in data:
        return jsonify({'success': False, 'error': 'Missing category data'}), 400

    new_category = data.get('category')

    # Validate category: allow setting to None (removing category) or selecting from allowed list
    if new_category is not None and new_category not in ALLOWED_WRONG_ANSWER_CATEGORIES:
         return jsonify({'success': False, 'error': 'Invalid category provided'}), 400

    # Security check: Ensure the item belongs to the current user
    if wrong_answer.user_id != current_user.id:
        current_app.logger.warning(f"User {current_user.id} attempted to categorize wrong answer {wrong_answer_id} owned by user {wrong_answer.user_id}")
        return jsonify({'success': False, 'error': 'Permission denied'}), 403

    try:
        wrong_answer.category = new_category # Set to None if empty string or None is passed
        db.session.add(wrong_answer)
        db.session.commit()
        current_app.logger.info(f"User {current_user.id} set category for wrong answer {wrong_answer_id} to '{wrong_answer.category}'")
        return jsonify({'success': True, 'category': wrong_answer.category})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error setting category for wrong answer {wrong_answer_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Database error'}), 500

# --- 用户认证路由 ---
@current_app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter((User.username == form.username.data) | (User.email == form.username.data)).first()
        if user is None or not user.check_password(form.password.data):
            flash('无效的用户名或密码。(Invalid username or password.)', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        flash(f'登录成功，欢迎回来, {user.username}! (Login successful!)', 'success')

        next_page = request.args.get('next')
        # --- 使用 urlsplit 进行检查 ---
        if not next_page or urlsplit(next_page).netloc != '': # <-- 修改此处
            next_page = url_for('index')
        # --------------------------
        return redirect(next_page)
    return render_template('login.html', title='登录 (Sign In)', form=form)


@current_app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('你已成功登出。 (You have been logged out.)', 'info')
    return redirect(url_for('index'))


@current_app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('恭喜，注册成功！请登录。(Congratulations, you are now registered! Please log in.)', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during user registration commit: {e}", exc_info=True)
            flash('注册过程中发生错误，请稍后重试。(An error occurred during registration. Please try again.)', 'danger')
            # 不重定向，留在注册页面显示错误（如果表单能显示的话）或重定向到注册页
            return render_template('register.html', title='注册 (Register)', form=form)

    return render_template('register.html', title='注册 (Register)', form=form)


# --- 学习记录与错题本路由 ---

@current_app.route('/history')
@login_required
def history():
    """显示用户的测试历史记录 (分页)"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('POSTS_PER_PAGE', 10) # 可以考虑在 Config 中定义每页数量

    try:
        attempts = QuizAttempt.query.filter_by(user_id=current_user.id)\
                                .order_by(QuizAttempt.timestamp.desc())\
                                .paginate(page=page, per_page=per_page, error_out=False)
    except Exception as e:
         current_app.logger.error(f"Error fetching history for user {current_user.id}: {e}", exc_info=True)
         flash('无法加载测试历史记录。(Failed to load quiz history.)', 'danger')
         attempts = None # 传递 None 到模板

    now = datetime.utcnow()
    return render_template('history.html', title='测试历史 (Quiz History)', attempts=attempts)

# --- 保护现有管理路由 ---
@current_app.route('/admin/dashboard')
@login_required
@admin_required # 使用新的装饰器
def admin_dashboard():
     if not current_user.has_admin_privileges: # 双重检查或仅依赖装饰器
         abort(403)
     return render_template('admin/admin.html')

# --- 新增用户管理路由 ---
@current_app.route('/admin/users')
@login_required
@root_admin_required # 只有 root 可以管理用户权限
def manage_users():
    try:
        # 查询所有用户，可以排除 root 用户自己
        root_username = current_app.config.get('ROOT_ADMIN_USERNAME', 'root')
        users = User.query.filter(User.username != root_username).order_by(User.username).all()
    except Exception as e:
        current_app.logger.error(f"Error fetching users for admin management: {e}", exc_info=True)
        flash("加载用户列表失败。(Failed to load user list.)", "danger")
        users = []
    return render_template('admin/manage_users.html', users=users, root_admin_username=root_username)


@current_app.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@root_admin_required # 只有 root 可以执行
def toggle_admin_status(user_id):
    # 查找目标用户
    user_to_modify = User.query.get_or_404(user_id)
    root_username = current_app.config.get('ROOT_ADMIN_USERNAME', 'root')

    # 安全检查：不能修改根管理员自己，也不能修改根管理员账号的状态
    if user_to_modify.id == current_user.id:
         flash("你不能修改自己的管理员状态。(You cannot modify your own admin status.)", "warning")
    elif user_to_modify.username == root_username:
         flash("不能修改根管理员的状态。(Cannot modify the root admin's status.)", "danger")
    else:
        try:
            # 切换 is_admin 状态
            user_to_modify.is_admin = not user_to_modify.is_admin
            db.session.add(user_to_modify) # 标记为修改
            db.session.commit()
            action = "授予 (granted)" if user_to_modify.is_admin else "撤销 (revoked)"
            flash(f"用户 '{user_to_modify.username}' 的管理员权限已被 {action}。(Admin status for user '{user_to_modify.username}' has been {action}.)", "success")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error toggling admin status for user {user_id}: {e}", exc_info=True)
            flash("修改管理员状态时出错。(Error changing admin status.)", "danger")

    return redirect(url_for('manage_users')) # 重定向回用户列表

# --- PDF 处理路由 (完整实现) ---
@current_app.route('/admin/process_pdf', methods=['POST'], endpoint='process_pdf_route_admin')
@login_required # 必须登录
@admin_required # 必须是管理员
def process_pdf_route_admin():
    """处理上传的 NCE PDF 文件，提取数据并强制更新或添加到数据库。"""

    log = current_app.logger # 使用 Flask 的 logger

    try:
        # 1. 获取并检查 PDF 文件路径
        pdf_path = current_app.config.get('NCE_PDF_PATH')
        if not pdf_path or not os.path.exists(pdf_path):
             log.error(f"PDF Processing Error: NCE_PDF_PATH '{pdf_path}' not configured or file not found.")
             return jsonify({"error": "PDF 文件路径未配置或文件不存在。(PDF file path not configured or file not found.)"}), 500 # 返回 500 更合适

        log.info(f"Admin '{current_user.username}' initiated PDF processing for: {pdf_path}")

        # 2. 调用 PDF 解析器
        extracted_data = process_nce_pdf(pdf_path)
        lessons_data = extracted_data.get('lessons', [])
        vocabulary_data = extracted_data.get('vocabulary', [])
        log.debug(f"PDF parser returned {len(lessons_data)} lessons and {len(vocabulary_data)} vocab items.")

        # 如果解析器未返回任何数据，也提前告知
        if not lessons_data and not vocabulary_data:
            log.warning("PDF parser did not extract any lesson or vocabulary data.")
            return jsonify({
                "message": "PDF processed, but no lesson or vocabulary data was extracted.",
                "lesson_summary": {"added": 0, "updated": 0, "errors": 0},
                "vocabulary_summary": {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
            }), 200 # 算处理成功，但内容为空

        # 3. 初始化操作总结计数器
        summary = {
            "lessons_added": 0, "lessons_updated": 0, "lesson_errors": 0, # 添加错误计数
            "vocab_added": 0, "vocab_updated": 0, "vocab_skipped": 0, "vocab_errors": 0 # 添加错误和跳过计数
        }

        # 4. 处理课程数据 (添加或更新)
        log.info(f"Starting database update for {len(lessons_data)} lessons...")
        for lesson_info in lessons_data:
            try:
                lesson_num = lesson_info.get('lesson_number')
                if not lesson_num:
                    log.warning(f"Skipping lesson data with missing lesson number: {lesson_info}")
                    summary["lesson_errors"] += 1
                    continue

                # 查找数据库中是否已存在该课程
                existing_lesson = Lesson.query.filter_by(lesson_number=lesson_num).first()

                if existing_lesson:
                    # --- 更新现有课程 ---
                    log.debug(f"Updating existing Lesson {lesson_num} (ID: {existing_lesson.id})")
                    # 使用 get 获取新值，如果新值为 None 则保留旧值 (更安全)
                    existing_lesson.title_en = lesson_info.get('title_en', existing_lesson.title_en)
                    existing_lesson.title_cn = lesson_info.get('title_cn', existing_lesson.title_cn)
                    existing_lesson.text_en = lesson_info.get('text_en', existing_lesson.text_en)
                    existing_lesson.text_cn = lesson_info.get('text_cn', existing_lesson.text_cn)
                    # 假设 source_book 不变
                    db.session.add(existing_lesson) # 标记为更新
                    summary["lessons_updated"] += 1
                    # -------------------
                else:
                    # --- 添加新课程 ---
                    log.debug(f"Adding new Lesson {lesson_num}")
                    new_lesson = Lesson(
                        lesson_number=lesson_num,
                        title_en=lesson_info.get('title_en', ''), # 确保有默认值
                        title_cn=lesson_info.get('title_cn', ''),
                        text_en=lesson_info.get('text_en', ''),
                        text_cn=lesson_info.get('text_cn', ''),
                        source_book=2 # 假设是 Book 2
                    )
                    db.session.add(new_lesson)
                    summary["lessons_added"] += 1
                    # -------------------
            except Exception as lesson_ex:
                log.error(f"Error processing lesson {lesson_info.get('lesson_number', 'N/A')}: {lesson_ex}", exc_info=True)
                summary["lesson_errors"] += 1
                db.session.rollback() # 回滚当前 lesson 的操作，尝试继续下一个
                # 可以考虑添加一个机制来跳过后续处理，或者让外层 except 捕获

        # 5. 处理词汇数据 (添加或更新)
        log.info(f"Starting database update for {len(vocabulary_data)} vocabulary items...")
        # 5. 处理词汇数据 (添加或更新)
        log.info(f"Starting database update for {len(vocabulary_data)} vocabulary items...")
        for vocab_info in vocabulary_data:
            try:
                lesson_num = vocab_info.get('lesson')
                eng_word = vocab_info.get('english')

                if not lesson_num or not eng_word or not vocab_info.get('chinese'):
                    log.warning(
                        f"Skipping vocab data with missing required fields (lesson, english, chinese): {vocab_info}")
                    summary["vocab_skipped"] += 1
                    continue

                from sqlalchemy import func
                existing_vocab = Vocabulary.query.filter(
                    Vocabulary.lesson_number == lesson_num,
                    func.lower(Vocabulary.english_word) == eng_word.lower()
                ).first()

                if existing_vocab:
                    # --- 更新现有词汇 ---
                    log.debug(f"Updating existing Vocab: L{lesson_num} - '{eng_word}' (ID: {existing_vocab.id})")
                    chn_trans = vocab_info.get('chinese', existing_vocab.chinese_translation)
                    pos = vocab_info.get('part_of_speech', existing_vocab.part_of_speech)
                    existing_vocab.chinese_translation = chn_trans
                    existing_vocab.part_of_speech = pos or ''
                    # --- 确保 source_book 也有值（如果允许更新的话，虽然通常不需要）---
                    # existing_vocab.source_book = existing_vocab.source_book or 2 # 确保不为空
                    db.session.add(existing_vocab)
                    summary["vocab_updated"] += 1
                    # --------------------
                else:
                    # --- 添加新词汇 ---
                    log.debug(f"Adding new Vocab: L{lesson_num} - '{eng_word}'")
                    new_vocab = Vocabulary(
                        lesson_number=lesson_num,
                        english_word=eng_word,
                        chinese_translation=vocab_info.get('chinese', ''),
                        part_of_speech=vocab_info.get('part_of_speech', ''),
                        # ===> 添加这一行来设置 source_book <===
                        source_book=2  # 假设 NCE Book 2 对应的值是 2
                        # =====================================
                    )
                    db.session.add(new_vocab)
                    summary["vocab_added"] += 1
                    # -------------------
            except Exception as vocab_ex:
                log.error(
                    f"Error processing vocab item '{vocab_info.get('english', 'N/A')}' for lesson {vocab_info.get('lesson', 'N/A')}: {vocab_ex}",
                    exc_info=True)
                summary["vocab_errors"] += 1
            except Exception as vocab_ex:
                log.error(f"Error processing vocab item '{vocab_info.get('english', 'N/A')}' for lesson {vocab_info.get('lesson', 'N/A')}: {vocab_ex}", exc_info=True)
                summary["vocab_errors"] += 1
                db.session.rollback() # 回滚当前词汇的操作，尝试继续下一个

        # 6. 提交所有数据库更改
        try:
            db.session.commit()
            log.info(f"Database commit successful. Final summary: {summary}")
        except Exception as commit_ex:
            db.session.rollback() # 最终提交失败也要回滚
            log.error(f"Fatal error during final database commit: {commit_ex}", exc_info=True)
            # 返回一个明确的数据库提交错误
            return jsonify({
                "error": f"数据库提交时发生严重错误。(Database commit failed: {str(commit_ex)})",
                "lesson_summary": summary, # 仍然返回处理过程中的统计
                "vocabulary_summary": summary
                }), 500

        # 7. 返回成功响应和操作总结
        return jsonify({
            "message": "PDF 处理完成，数据库已更新。(PDF processed and database updated.)",
            # 构造与前端 JS 期望一致的 summary 结构
            "lesson_summary": {
                "added": summary["lessons_added"],
                "updated": summary["lessons_updated"],
                "errors": summary["lesson_errors"]
            },
            "vocabulary_summary": {
                "added": summary["vocab_added"],
                "updated": summary["vocab_updated"],
                "skipped": summary["vocab_skipped"],
                "errors": summary["vocab_errors"]
            }
        }), 200

    except Exception as e:
        # 捕获 PDF 解析或其他意外错误
        # db.session.rollback() # 如果在 try 块开始前没有启动事务，这里可能不需要回滚
        log.error(f"Unhandled error during PDF processing for user '{current_user.username}': {e}", exc_info=True)
        # 返回通用服务器错误
        return jsonify({"error": f"处理 PDF 时发生内部服务器错误。(An internal server error occurred during PDF processing: {str(e)})"}), 500

# --- Updated Vocabulary Management Route ---
@current_app.route('/admin/vocabulary', endpoint='manage_vocabulary')
@login_required
@admin_required # Or root_admin_required depending on who should manage vocab
def manage_vocabulary():
    """管理词汇页面 - 显示数据库中的词汇"""
    current_app.logger.info(f"Admin user {current_user.username} accessed vocabulary management.")
    try:
        # --- Query the database for all vocabulary items ---
        # Order by lesson number first, then by ID for consistent ordering
        vocab_list = Vocabulary.query.order_by(Vocabulary.lesson_number, Vocabulary.id).all()
        current_app.logger.debug(f"Fetched {len(vocab_list)} vocabulary items for management page.")
        # --------------------------------------------------

    except Exception as e:
        current_app.logger.error(f"Error fetching vocabulary for management page: {e}", exc_info=True)
        flash("加载词汇列表时出错。(Error loading vocabulary list.)", "danger")
        vocab_list = [] # Pass an empty list on error

    # --- Render the template, passing the fetched vocabulary list ---
    try:
        return render_template('admin/manage_vocabulary.html',
                               title='管理词汇 (Manage Vocabulary)',
                               vocabulary=vocab_list) # Pass the list as 'vocabulary'
    except Exception as render_ex: # Catch potential TemplateNotFound or other rendering errors
        current_app.logger.error(f"Error rendering manage_vocabulary template: {render_ex}", exc_info=True)
        # Fallback message if template rendering fails *after* DB query
        flash("无法渲染词汇管理页面。(Could not render vocabulary management page.)", "error")
        return "Vocabulary Management Page (Error rendering template)", 500