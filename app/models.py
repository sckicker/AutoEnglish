# app/models.py - Updated with User Favorites Feature

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db # 导入你的 db 实例

# --- New Association Model for User Favorites ---
class UserFavoriteVocabulary(db.Model):
    """关联表/对象，记录用户收藏的词汇。"""
    __tablename__ = 'user_favorite_vocabulary'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    vocabulary_id = db.Column(db.Integer, db.ForeignKey('vocabulary.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True) # 收藏时间

    # 添加唯一约束，防止同一用户重复收藏同一词汇
    __table_args__ = (db.UniqueConstraint('user_id', 'vocabulary_id', name='_user_vocab_favorite_uc'),)

    # 可以选择性地添加关系回指到 User 和 Vocabulary (如果需要在关联对象上操作)
    # user = db.relationship("User", back_populates="favorite_associations")
    # vocabulary = db.relationship("Vocabulary", back_populates="favorited_by_associations")

    def __repr__(self):
        return f'<UserFavorite User {self.user_id} Vocab {self.vocabulary_id}>'
# --- End Association Model ---

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # --- 关系：指向 WrongAnswer ---
    wrong_answers = db.relationship(
        'WrongAnswer',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # --- 关系：指向 QuizAttempt ---
    quiz_attempts = db.relationship(
        'QuizAttempt',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # --- 新增关系：收藏的词汇 ---
    # 通过 user_favorite_vocabulary 这个中间表/模型连接到 Vocabulary
    favorite_vocabularies = db.relationship(
        'Vocabulary',
        secondary='user_favorite_vocabulary', # 指定中间表的名称
        lazy='dynamic',                       # 返回查询对象
        back_populates='favorited_by_users'   # 与 Vocabulary.favorited_by_users 关联
        # 不需要 cascade delete-orphan，因为删除用户时，中间表的记录会因外键约束而删除或需要手动处理
        # 删除收藏夹条目不应删除词汇本身
    )
    # --- 结束新增关系 ---

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        if not self.password_hash: # 处理密码哈希可能为空的情况
             return False
        return check_password_hash(self.password_hash, password)

    @property
    def has_admin_privileges(self):
        return self.is_admin

    def __repr__(self):
        return f'<User {self.username} (Admin: {self.is_admin})>'


class Vocabulary(db.Model):
    __tablename__ = 'vocabulary'
    id = db.Column(db.Integer, primary_key=True)
    lesson_number = db.Column(db.Integer, nullable=False, index=True)
    english_word = db.Column(db.String(128), nullable=False, index=True)
    part_of_speech = db.Column(db.String(32), nullable=True)
    chinese_translation = db.Column(db.String(256), nullable=True)
    source_book = db.Column(db.Integer, nullable=False, default=2, index=True)

    # --- 关系：关联的错题记录 ---
    wrong_answer_associations = db.relationship(
        'WrongAnswer',
        back_populates='vocabulary_item',
        lazy='dynamic',
        cascade='all, delete-orphan' # 删除词汇时也删除相关的错题记录
    )

    # --- 新增关系：收藏了该词汇的用户 ---
    # 通过 user_favorite_vocabulary 中间表连接到 User
    favorited_by_users = db.relationship(
        'User',
        secondary='user_favorite_vocabulary', # 指定中间表的名称
        lazy='dynamic',                       # 返回查询对象
        back_populates='favorite_vocabularies' # 与 User.favorite_vocabularies 关联
        # 删除词汇时，中间表的记录应该也会级联删除（取决于数据库外键设置）
        # 或者通过事件监听器处理
    )
    # --- 结束新增关系 ---


    # --- 新增：检查当前用户是否收藏了此词汇的方法 (方便模板使用) ---
    def is_favorited_by(self, user):
        if not user or not user.is_authenticated:
             return False
         # 使用 SQLAlchemy 的 any() 或 count() 方法在关系上进行高效查询
        # .any() 检查是否存在至少一个匹配项
        return db.session.query(UserFavoriteVocabulary.query.filter_by(
            user_id=user.id,
            vocabulary_id=self.id
        ).exists()).scalar()
        # 或者，如果关系已经加载了一部分:
        # return any(fav.id == user.id for fav in self.favorited_by_users) # 效率较低如果关系未加载
    # --- 结束新增方法 ---

    def __repr__(self):
        return f'<Vocabulary L{self.lesson_number} Book{self.source_book}: {self.english_word}>'


class WrongAnswer(db.Model):
    __tablename__ = 'wrong_answer'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    vocabulary_id = db.Column(db.Integer, db.ForeignKey('vocabulary.id'), nullable=False, index=True)
    timestamp_first_wrong = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    timestamp_last_wrong = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    incorrect_count = db.Column(db.Integer, default=1)
    is_marked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    category = db.Column(db.String(50), nullable=True, index=True)

    # --- 关系：指向 User ---
    user = db.relationship(
        'User',
        back_populates='wrong_answers'
    )

    # --- 关系：指向 Vocabulary ---
    vocabulary_item = db.relationship(
        'Vocabulary',
        back_populates='wrong_answer_associations'
    )

    def __repr__(self):
        return f'<WrongAnswer User {self.user_id} Vocab {self.vocabulary_id} Marked: {self.is_marked} Cat: {self.category}>'


class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempt'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    lessons_attempted = db.Column(db.String(256))
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    quiz_type = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    # --- 关系：指向 User ---
    user = db.relationship(
        'User',
        back_populates='quiz_attempts'
    )

    def __repr__(self):
        return f'<QuizAttempt User {self.user_id} Score {self.score}/{self.total_questions} on {self.timestamp}>'


class Lesson(db.Model):
    __tablename__ = 'lesson' # 明确表名
    id = db.Column(db.Integer, primary_key=True)
    lesson_number = db.Column(db.Integer, nullable=False, index=True)
    source_book = db.Column(db.Integer, nullable=False, default=2, index=True)
    title_en = db.Column(db.String(255), nullable=True)
    title_cn = db.Column(db.String(255), nullable=True)
    text_en = db.Column(db.Text, nullable=True)
    text_cn = db.Column(db.Text, nullable=True)

    __table_args__ = (db.UniqueConstraint('lesson_number', 'source_book', name='_lesson_book_uc'),)

    def __repr__(self):
        return f'<Lesson {self.source_book}-{self.lesson_number}: {self.title_en}>'