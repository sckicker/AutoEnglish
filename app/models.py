# app/models.py
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask import current_app # 导入 current_app
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # --- 新增：管理员标记 ---
    is_admin = db.Column(db.Boolean, default=False, nullable=False, index=True) # 添加索引

    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy='dynamic')
    wrong_answers = db.relationship('WrongAnswer', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # --- 新增：判断是否为根管理员的属性 ---
    @property
    def is_root(self):
        # 直接比较用户名和配置中的根用户名
        # 提供一个默认值以防配置丢失
        root_user = current_app.config.get('ROOT_ADMIN_USERNAME', 'root')
        return self.username == root_user

    # --- 新增：判断是否拥有管理员权限（根或普通）的属性 ---
    @property
    def has_admin_privileges(self):
        return self.is_root or self.is_admin

    def __repr__(self):
        return f'<User {self.username}>'

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    lessons_attempted = db.Column(db.String(200)) # 存储课程号，例如 "1,5,10"
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    quiz_type = db.Column(db.String(20)) # e.g., 'cn_to_en'
    # Optional: relationship to specific wrong answers in this attempt
    # wrong_answers_in_attempt = db.relationship('WrongAnswer', backref='quiz_attempt', lazy='dynamic')

    def __repr__(self):
         return f'<QuizAttempt {self.id} by User {self.user_id} on {self.timestamp}>'

class WrongAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    vocabulary_id = db.Column(db.Integer, db.ForeignKey('vocabulary.id'), nullable=False, index=True)
    timestamp_last_wrong = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    incorrect_count = db.Column(db.Integer, default=1)
    # quiz_attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempt.id'), nullable=True) # Optional link

    # Add unique constraint for user+vocab ? Or allow multiple entries over time?
    # Let's assume we update timestamp_last_wrong and increment count if pair exists.
    # __table_args__ = (db.UniqueConstraint('user_id', 'vocabulary_id', name='_user_vocab_uc'),)

    # Relationships to easily access related objects
    vocabulary_item = db.relationship('Vocabulary') # No backref needed if Vocab doesn't need direct access to wrong answers

    def __repr__(self):
        return f'<WrongAnswer User {self.user_id} Vocab {self.vocabulary_id}>'

class Vocabulary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_number = db.Column(db.Integer, nullable=False, index=True)
    english_word = db.Column(db.String(200), nullable=False)
    chinese_translation = db.Column(db.String(300), nullable=False)
    # 词性字段保持可为空 (nullable=True)，因为解析器可能无法提取词性
    part_of_speech = db.Column(db.String(20), nullable=True, index=True) # 添加 index=True 推荐
    source_book = db.Column(db.Integer, nullable=False, default=2, index=True)

    # --- 修改唯一约束，加入 part_of_speech ---
    __table_args__ = (
        db.UniqueConstraint(
            'lesson_number',
            'english_word',
            'part_of_speech', # <-- 添加词性字段
            'source_book',
            name='_lesson_word_pos_book_uc' # 约束名称更新
        ),
    )
    # --- 约束修改结束 ---

    def __repr__(self):
        return f'<Vocab L{self.lesson_number}: {self.english_word} ({self.part_of_speech})>'

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_number = db.Column(db.Integer, nullable=False, index=True)
    source_book = db.Column(db.Integer, nullable=False, default=2, index=True)
    # 标题信息 (Title Information)
    title_en = db.Column(db.String(255), nullable=True) # 英文标题
    title_cn = db.Column(db.String(255), nullable=True) # 中文标题
    # 课文内容 (Text Content) - 使用 Text 类型存储较长文本
    text_en = db.Column(db.Text, nullable=True) # 英文课文
    text_cn = db.Column(db.Text, nullable=True) # 中文译文

    # 确保同一本书的课程序号是唯一的
    __table_args__ = (db.UniqueConstraint('lesson_number', 'source_book', name='_lesson_book_uc'),)

    def __repr__(self):
        # 定义对象打印时的表示形式
        return f'<Lesson {self.source_book}-{self.lesson_number}: {self.title_en}>'