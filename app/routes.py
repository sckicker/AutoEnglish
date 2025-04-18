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

@current_app.route('/lesson/<int:lesson_number>')
def view_lesson(lesson_number):
    """显示指定 Lesson 的课文内容"""
    current_app.logger.info(f"Request received for lesson {lesson_number}")
    try:
        # 使用 first_or_404 获取课文，如果找不到会直接返回 404 页面
        lesson_data = Lesson.query.filter_by(lesson_number=lesson_number, source_book=2).first_or_404()
    except Exception as e:
         current_app.logger.error(f"Error fetching lesson {lesson_number} from DB: {e}", exc_info=True)
         abort(500) # 数据库错误返回 500

    now = datetime.utcnow()
    return render_template('lesson_text.html', lesson=lesson_data, current_time=now)

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

# PDF 处理路由保留，但强烈建议加上权限检查
# PDF 处理路由
@current_app.route('/admin/process_pdf', methods=['POST'], endpoint='process_pdf_route_admin') # Added endpoint
@login_required # Add login required
@admin_required # Add admin required
def process_pdf_route_admin(): # Renamed, added checks via decorators
    # Decorators handle the permission checks now
    # if not session.get('is_admin'): ... removed ...
    # --- Call the actual PDF processing logic ---
    try:
        pdf_path = current_app.config.get('NCE_PDF_PATH') # Get path from config
        if not pdf_path or not os.path.exists(pdf_path):
             current_app.logger.error(f"NCE_PDF_PATH '{pdf_path}' not configured or file not found.")
             return jsonify({"error": "PDF file path not configured or file not found."}), 500

        current_app.logger.info(f"Admin {current_user.username} initiated PDF processing.")
        # Call your processing function
        results = process_nce_pdf(pdf_path) # Assuming this returns a dict with summaries

        current_app.logger.info(f"PDF processing completed. Results: {results}")
        # Return the results dictionary directly as JSON
        return jsonify({
            "message": "PDF processed successfully.",
            "vocabulary_summary": results.get('vocabulary_summary', {}),
            "lesson_text_summary": results.get('lesson_text_summary', {})
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error during PDF processing initiated by {current_user.username}: {e}", exc_info=True)
        db.session.rollback() # Rollback any partial DB changes if error occurred mid-process
        return jsonify({"error": f"An internal server error occurred during PDF processing: {str(e)}"}), 500

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