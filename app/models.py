from . import db # Import db instance from __init__.py

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