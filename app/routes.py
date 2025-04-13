from flask import current_app, render_template, request, jsonify, Blueprint
from .models import Vocabulary, Lesson
from .pdf_parser import process_nce_pdf # Assuming it exists
from . import db # Import db instance from __init__.py
import random
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session

# If using Blueprints, define one:
# bp = Blueprint('main', __name__)
# Then use @bp.route('/') instead of @current_app.route('/')

# For simplicity without Blueprints for now:
@current_app.route('/')
def index():
    try:
        lessons = db.session.query(Vocabulary.lesson_number.distinct()).order_by(Vocabulary.lesson_number).all()
        lesson_numbers = [l[0] for l in lessons]
        current_app.logger.debug(f"Fetched distinct lessons: {lesson_numbers}") # DEBUG example
    except Exception as e:
        # Use logger for errors
        current_app.logger.error(f"Error fetching lessons from DB: {e}", exc_info=True)
        lesson_numbers = []
    now = datetime.utcnow()
    return render_template('index.html', lessons=lesson_numbers, current_time=now)

@current_app.route('/api/quiz', methods=['GET'])
def get_quiz():
    try:
        lessons_str = request.args.get('lessons')
        num_questions = int(request.args.get('count', 10))
        quiz_type = request.args.get('type', 'cn_to_en')

        if not lessons_str:
            return jsonify({"error": "Missing 'lessons' parameter"}), 400

        lesson_numbers = [int(n) for n in lessons_str.split(',')]

        # Query database using SQLAlchemy ORM
        all_vocab = Vocabulary.query.filter(Vocabulary.lesson_number.in_(lesson_numbers)).all()

        if not all_vocab:
            return jsonify({"error": "No vocabulary found for the selected lessons"}), 404

        num_questions = min(num_questions, len(all_vocab))
        selected_vocab = random.sample(all_vocab, num_questions)

        quiz_questions = []
        for item in selected_vocab:
            if quiz_type == 'cn_to_en':
                question = item.chinese_translation
                answer = item.english_word
            elif quiz_type == 'en_to_cn':
                question = item.english_word
                answer = item.chinese_translation
            else:
                return jsonify({"error": "Invalid quiz type"}), 400

            quiz_questions.append({
                "id": item.id,
                "lesson": item.lesson_number,
                "question": question,
                "correct_answer": answer # For simplicity now, review security later
            })
        return jsonify(quiz_questions)

    except ValueError:
        return jsonify({"error": "Invalid parameter format"}), 400
    except Exception as e:
        current_app.logger.error(f"Error in /api/quiz: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

# app/routes.py (函数定义)

@current_app.route('/admin/process_pdf', methods=['POST'])
def process_pdf_route():
    """
    管理路由: 触发指定 PDF 文件的词汇和课文提取，并存入数据库。
    通过 POST 请求访问此路由。
    !!! 警告: 生产环境中必须对此路由添加认证和授权保护 !!!
    """
    current_app.logger.info("'/admin/process_pdf' route accessed (POST). Attempting to process PDF.")

    # 1. 确定 PDF 文件路径和书籍信息
    pdf_filename = "nce_book2.pdf" # 示例文件名 (NCE Book 2)
    source_book_number = 2        # 对应的书籍编号

    # 检查上传文件夹配置
    if 'UPLOAD_FOLDER' not in current_app.config or not current_app.config['UPLOAD_FOLDER']:
        current_app.logger.error("Configuration error: UPLOAD_FOLDER is not defined in Flask config.")
        return jsonify({"error": "Server configuration error: Upload folder not configured."}), 500

    pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
    current_app.logger.info(f"Target PDF path configured as: {pdf_path}")

    # 2. 检查文件是否存在
    if not os.path.exists(pdf_path) or not os.path.isfile(pdf_path):
        current_app.logger.error(f"PDF file check failed. File not found or is not a file at: {pdf_path}")
        return jsonify({"error": f"Specified PDF file '{pdf_filename}' not found on server."}), 404

    try:
        # 3. 调用 (假设的) 增强版 PDF 解析器
        current_app.logger.info(f"Initiating data extraction from '{pdf_filename}' using 'process_nce_pdf'...")
        # 假设 process_nce_pdf 返回 {'vocabulary': [...], 'lessons': [...]}
        extracted_data = process_nce_pdf(pdf_path)
        current_app.logger.info("PDF parsing function finished.")

        # 检查返回的数据结构
        if not isinstance(extracted_data, dict):
             current_app.logger.error(f"PDF parser function did not return a dictionary. Type received: {type(extracted_data)}")
             return jsonify({"error": "Internal server error: PDF parser returned unexpected data format."}), 500

        vocab_list = extracted_data.get('vocabulary', [])
        lesson_list = extracted_data.get('lessons', [])

        if not vocab_list and not lesson_list:
            current_app.logger.warning(f"No data (vocabulary or lessons) was extracted from '{pdf_filename}'.")
            return jsonify({"message": f"PDF '{pdf_filename}' processed, but no data was extracted."}), 200

        current_app.logger.info(f"Extracted {len(vocab_list)} vocabulary items and {len(lesson_list)} lesson text items.")

        # 4. 处理词汇数据并准备存入数据库
        current_app.logger.info("Processing extracted VOCABULARY data...")
        added_vocab_count = 0
        skipped_vocab_count = 0
        error_vocab_count = 0
        vocab_to_add = []
        processed_vocab_keys_in_batch = set()  # 用于批次内去重

        for item_data in vocab_list:
            try:
                # ... (基本验证) ...
                lesson_num = item_data['lesson']
                eng_word = item_data['english'].strip()
                chn_trans = item_data['chinese'].strip()
                # 获取词性，可能为 None
                pos = item_data.get('part_of_speech')
                # ... (核心数据验证) ...

                # --- 定义包含词性的唯一键 ---
                # 注意: pos 可能为 None，元组可以包含 None
                current_key = (lesson_num, eng_word, pos, source_book_number)

                # --- 检查1：是否已在本批次处理过 (使用新 key) ---
                if current_key in processed_vocab_keys_in_batch:
                    current_app.logger.debug(
                        f"[Vocab] Skipped (duplicate within this batch): L{lesson_num} | {eng_word} | POS: {pos}")
                    continue

                # --- 检查2：是否已存在于数据库 (使用新 key 查询) ---
                # filter_by 会正确处理 pos=None 的情况 (转换为 IS NULL)
                exists_in_db = Vocabulary.query.filter_by(
                    lesson_number=lesson_num,
                    english_word=eng_word,
                    part_of_speech=pos,  # <-- 添加词性到查询条件
                    source_book=source_book_number
                ).first()

                # 将当前键添加到批次跟踪集合 (无论是否在DB中找到)
                # 这样可以避免对同一个键进行多次DB查询
                processed_vocab_keys_in_batch.add(current_key)

                if not exists_in_db:
                    # 如果数据库中不存在，准备添加
                    new_vocab = Vocabulary(
                        lesson_number=lesson_num, english_word=eng_word, chinese_translation=chn_trans,
                        part_of_speech=pos, source_book=source_book_number
                    )
                    vocab_to_add.append(new_vocab)
                    added_vocab_count += 1
                    current_app.logger.debug(f"[Vocab] Prepared to add: L{lesson_num} | {eng_word} | POS: {pos}")
                else:
                    # 如果数据库中已存在，则跳过
                    skipped_vocab_count += 1
                    current_app.logger.debug(
                        f"[Vocab] Skipped (already exists in DB): L{lesson_num} | {eng_word} | POS: {pos}")

            except Exception as item_ex:
                current_app.logger.error(f"[Vocab] Error processing item {item_data}: {item_ex}", exc_info=True)
                error_vocab_count += 1
        current_app.logger.info(
            f"Finished processing vocabulary data loop. Ready to add: {added_vocab_count}, Skipped: {skipped_vocab_count}, Errors: {error_vocab_count}")

        # 5. 处理课文数据并准备存入数据库
        current_app.logger.info("Processing extracted LESSON TEXT data...")
        added_lesson_count = 0
        updated_lesson_count = 0 # 如果实现更新逻辑
        error_lesson_count = 0
        lessons_to_add = [] # 存储待添加的对象
        lessons_to_update = [] # 存储待更新的对象 (如果实现更新)

        for lesson_data in lesson_list:
            try:
                # 基本验证
                if not isinstance(lesson_data, dict) or 'lesson_number' not in lesson_data:
                    current_app.logger.warning(f"[Lesson] Skipping invalid lesson data structure: {lesson_data}")
                    error_lesson_count += 1
                    continue
                lesson_num = lesson_data['lesson_number']
                if not isinstance(lesson_num, int) or lesson_num <= 0:
                     current_app.logger.warning(f"[Lesson] Skipping item with invalid lesson number: {lesson_num}")
                     error_lesson_count += 1
                     continue

                # 查重
                existing_lesson = Lesson.query.filter_by(lesson_number=lesson_num, source_book=source_book_number).first()
                if not existing_lesson:
                    new_lesson = Lesson(
                        lesson_number=lesson_num, source_book=source_book_number,
                        title_en=lesson_data.get('title_en'), title_cn=lesson_data.get('title_cn'),
                        text_en=lesson_data.get('text_en'), text_cn=lesson_data.get('text_cn')
                    )
                    lessons_to_add.append(new_lesson)
                    added_lesson_count += 1
                    current_app.logger.debug(f"[Lesson] Prepared to add: Lesson {lesson_num}")
                else:
                    # 当前选择：跳过已存在的课文。可以修改为更新逻辑。
                    current_app.logger.debug(f"[Lesson] Lesson {lesson_num} already exists, skipping.")
                    # --- 可选：更新逻辑 ---
                    # update_needed = False
                    # if existing_lesson.title_en != lesson_data.get('title_en'): update_needed = True; existing_lesson.title_en = lesson_data.get('title_en')
                    # # ... 检查并更新其他字段 ...
                    # if update_needed:
                    #     lessons_to_update.append(existing_lesson)
                    #     updated_lesson_count += 1
                    #     current_app.logger.debug(f"[Lesson] Prepared to update: Lesson {lesson_num}")
                    # --- 更新逻辑结束 ---
            except Exception as item_ex:
                current_app.logger.error(f"[Lesson] Error processing item for lesson {lesson_data.get('lesson_number', 'N/A')}: {item_ex}", exc_info=True)
                error_lesson_count += 1
        current_app.logger.info(f"Finished processing lesson text data. Ready to add: {added_lesson_count}, Ready to update: {updated_lesson_count}, Errors: {error_lesson_count}")

        # 6. 提交数据库事务
        current_app.logger.info("Attempting to commit changes to database...")
        if not vocab_to_add and not lessons_to_add and not lessons_to_update:
             current_app.logger.info("No new or updated data to commit.")
        else:
            try:
                # 批量添加到 Session
                if vocab_to_add:
                    db.session.add_all(vocab_to_add)
                    current_app.logger.debug(f"Added {len(vocab_to_add)} vocabulary items to session.")
                if lessons_to_add:
                    db.session.add_all(lessons_to_add)
                    current_app.logger.debug(f"Added {len(lessons_to_add)} lesson items to session.")
                if lessons_to_update:
                     # 对于更新，如果对象是从数据库查询出来的并且修改了，
                     # 只需要 commit 即可，不需要再次 add_all
                     # 如果是创建新对象来替换，则需要 add_all
                     pass # 假设我们是直接修改 existing_lesson 对象
                     current_app.logger.debug(f"Marked {len(lessons_to_update)} lesson items for update in session.")

                # 执行提交
                db.session.commit()
                current_app.logger.info("Database commit successful.")
            except Exception as commit_ex:
                db.session.rollback() # 关键：提交失败时必须回滚
                current_app.logger.error(f"Database commit failed! Rolling back session: {commit_ex}", exc_info=True)
                return jsonify({"error": "Database commit failed. Check server logs for details."}), 500

        # 7. 返回成功响应
        final_message = f"PDF '{pdf_filename}' processed successfully."
        response_data = {
            "message": final_message,
            "vocabulary_summary": {
                "extracted": len(vocab_list),
                "added_to_db": added_vocab_count,
                "skipped_duplicates": skipped_vocab_count,
                "processing_errors": error_vocab_count
            },
            "lesson_text_summary": {
                 "extracted": len(lesson_list),
                 "added_to_db": added_lesson_count,
                 "updated_in_db": updated_lesson_count, # 如果实现了更新
                 "processing_errors": error_lesson_count
            }
        }
        current_app.logger.info(f"Process summary: {response_data}")
        return jsonify(response_data), 200

    # 8. 处理整个过程中的主要异常
    except Exception as e:
        db.session.rollback() # 确保在任何顶层错误时回滚
        current_app.logger.error(f"Critical error during '/admin/process_pdf' execution for {pdf_filename}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred during PDF processing. Please check server logs."}), 500

@current_app.route('/lesson/<int:lesson_number>')
def view_lesson(lesson_number):
    """
    显示指定 Lesson 编号的课文内容。
    """
    current_app.logger.info(f"Request received for lesson {lesson_number}")
    # 假设我们只处理 source_book=2 (NCE Book 2)
    # 使用 first_or_404() 可以简化未找到课文的处理
    lesson_data = Lesson.query.filter_by(lesson_number=lesson_number, source_book=2).first_or_404()

    # 如果找到了课文数据，渲染 lesson_text.html 模板并传递数据
    # 同时传递 current_time 如果 base.html 需要它
    now = datetime.utcnow()
    return render_template('lesson_text.html', lesson=lesson_data, current_time=now)


ADMIN_USERNAME = "jeff"
ADMIN_PASSWORD = "su"

@current_app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form['username']
    password = request.form['password']

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return redirect(url_for('admin'))
    else:
        error = '用户名或密码错误'
        print(error)
        return redirect(url_for('index')) # 如果不是管理员，重定向到首页

@current_app.route('/admin')
def admin():
    current_time = datetime.now()  # 获取当前时间
    if session.get('is_admin'):
        return render_template('admin/admin.html', current_time=current_time)  # 将 current_time 传递给模板
    else:
        return redirect(url_for('index')) # 如果不是管理员，重定向到首页

@current_app.route('/admin/lessons')
def view_lessons():
    if session.get('is_admin'):
        # 这里添加获取和展示课程数据的逻辑
        return render_template('admin/view_lessons.html')
    else:
        return redirect(url_for('index'))

@current_app.route('/admin/vocabulary')
def manage_vocabulary():
    if session.get('is_admin'):
        # 这里添加管理词汇数据的逻辑
        return render_template('admin/manage_vocabulary.html')
    else:
        return redirect(url_for('index'))

@current_app.route('/admin/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))
