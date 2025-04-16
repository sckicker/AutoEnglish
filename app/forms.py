from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from .models import User # 需要导入 User 模型以检查用户名/邮箱是否已存在

class LoginForm(FlaskForm):
    username = StringField('用户名 (Username)', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('密码 (Password)', validators=[DataRequired()])
    remember_me = BooleanField('记住我 (Remember Me)')
    submit = SubmitField('登录 (Sign In)')

class RegistrationForm(FlaskForm):
    username = StringField('用户名 (Username)', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('邮箱 (Email)', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('密码 (Password)', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField(
        '重复密码 (Repeat Password)', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('注册 (Register)')

    # 自定义验证器，检查用户名是否已被使用
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('该用户名已被使用，请选用其他用户名。 (Please use a different username.)')

    # 自定义验证器，检查邮箱是否已被使用
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('该邮箱已被注册，请选用其他邮箱。 (Please use a different email address.)')