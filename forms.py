from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, PasswordField
from wtforms.validators import DataRequired, Length, Email, Optional

class AppealForm(FlaskForm):
    appeal_type = SelectField('Тип обращения', 
        choices=[('Жалоба', 'Жалоба'), ('Предложение', 'Предложение'), ('Заявление', 'Заявление')],
        validators=[DataRequired()])
    category = SelectField('Категория',
        choices=[('ЖКХ', 'ЖКХ'), ('Транспорт', 'Транспорт'), ('Социальная сфера', 'Социальная сфера'), 
                 ('Административные вопросы', 'Административные вопросы'), ('Другое', 'Другое')],
        validators=[DataRequired()])
    title = StringField('Тема', validators=[DataRequired(), Length(max=150)])
    description = TextAreaField('Описание', validators=[DataRequired(), Length(max=2000)])
    contact = StringField('Email', validators=[Optional(), Email()])

class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])