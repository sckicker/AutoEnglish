# app/models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin # 假设你的 User 模型需要登录功能
from . import db # 导入你的 db 实例

# 假设你的 User 模型也需要 Flask-Login
class User(UserMixin, db.Model):
    __tablename__ = 'user' # 明确表名（好习惯）
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256)) # 注意长度可能需要调整
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    # 可能还有 last_seen, about_me 等字段...

    # --- 关系定义：指向 WrongAnswer ---
    # 使用 back_populates 明确指定 WrongAnswer 中的 'user' 属性来完成双向链接
    # lazy='dynamic' 使得 user.wrong_answers 返回一个可查询对象，而不是直接加载所有记录
    wrong_answers = db.relationship(
        'WrongAnswer',
        back_populates='user', # 指向 WrongAnswer.user
        lazy='dynamic',        # 返回 Query 对象，适合一对多
        cascade='all, delete-orphan' # 当删除 User 时，同时删除其关联的 WrongAnswer 记录
    )

    # --- 关系定义：指向 QuizAttempt --- (示例，如果需要的话)
    quiz_attempts = db.relationship(
        'QuizAttempt',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    # --- 结束关系定义 ---

    def set_password(self, password):
        # 确保使用足够强的哈希方法
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 如果有 is_admin 字段，可以添加一个 property 供模板或逻辑使用
    @property
    def has_admin_privileges(self):
        # 你可以在这里加入更复杂的逻辑，比如检查角色表
        return self.is_admin

    def __repr__(self):
        return f'<User {self.username} (Admin: {self.is_admin})>'


class WrongAnswer(db.Model):
    __tablename__ = 'wrong_answer' # 明确表名
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True) # 外键指向 user 表的 id
    vocabulary_id = db.Column(db.Integer, db.ForeignKey('vocabulary.id'), nullable=False, index=True) # 外键指向 vocabulary 表的 id
    timestamp_first_wrong = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    timestamp_last_wrong = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    incorrect_count = db.Column(db.Integer, default=1)

    # --- 新增字段 ---
    is_marked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    category = db.Column(db.String(50), nullable=True, index=True)
    # --- 结束新增字段 ---

    # --- 关系定义：指向 User ---
    # 使用 back_populates 明确指定 User 中的 'wrong_answers' 属性来完成双向链接
    user = db.relationship(
        'User',
        back_populates='wrong_answers' # 指向 User.wrong_answers
    )

    # --- 关系定义：指向 Vocabulary ---
    # 假设 Vocabulary 模型中有一个名为 'wrong_answer_associations' (或类似) 的 back_populates
    # 如果 Vocabulary 模型没有反向关系，可以只写 'Vocabulary'
    vocabulary_item = db.relationship(
        'Vocabulary',
        back_populates='wrong_answer_associations' # <--- 你需要在 Vocabulary 模型中定义这个
    )
    # --- 结束关系定义 ---

    def __repr__(self):
        return f'<WrongAnswer User {self.user_id} Vocab {self.vocabulary_id} Marked: {self.is_marked} Cat: {self.category}>'

# --- 你还需要确保 Vocabulary 模型中定义了对应的 back_populates ---
class Vocabulary(db.Model):
    __tablename__ = 'vocabulary'
    id = db.Column(db.Integer, primary_key=True)
    lesson_number = db.Column(db.Integer, nullable=False, index=True)
    english_word = db.Column(db.String(128), nullable=False, index=True)
    part_of_speech = db.Column(db.String(32), nullable=True) # 允许词性为空
    chinese_translation = db.Column(db.String(256), nullable=True) # 允许中文翻译为空

    # ===> 添加 source_book 字段定义 <===
    # 类型通常是 Integer，假设你用数字代表书本
    # nullable=False 强制要求必须有值
    # default=2 如果大部分来自第二册，设置默认值可以简化添加逻辑
    # index=True 如果你经常按书本筛选词汇，可以加索引
    source_book = db.Column(db.Integer, nullable=False, default=2, index=True)
    # ==================================

    # --- 关系定义 (如果需要) ---
    wrong_answer_associations = db.relationship(
        'WrongAnswer',
        back_populates='vocabulary_item',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    # -------------------------

    def __repr__(self):
        return f'<Vocabulary L{self.lesson_number} Book{self.source_book}: {self.english_word}>' # 在 repr 中也加上

# --- 同样，QuizAttempt 模型也需要 back_populates ---
class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempt'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    lessons_attempted = db.Column(db.String(256)) # 逗号分隔的 lesson numbers
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    quiz_type = db.Column(db.String(20)) # e.g., 'cn_to_en', 'en_to_cn'
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    user = db.relationship(
        'User',
        back_populates='quiz_attempts' # 指向 User.quiz_attempts
    )

    def __repr__(self):
        return f'<QuizAttempt User {self.user_id} Score {self.score}/{self.total_questions} on {self.timestamp}>'

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