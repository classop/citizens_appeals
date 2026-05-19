# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import csv, io
from datetime import datetime
from config import Config
from models import db, User, Appeal, StatusHistory, ActivityLog, generate_code
from forms import AppealForm, LoginForm

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Необходима авторизация'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Исправленный декоратор проверки ролей
    def role_required(roles):
        def wrapper(f):
            @wraps(f)
            def inner(*args, **kwargs):
                if current_user.role not in roles:
                    flash('Доступ запрещен', 'danger')
                    return redirect(url_for('index'))
                return f(*args, **kwargs)
            return inner
        return wrapper

    # Создание таблиц и тестовых данных при первом запуске
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(login='admin').first():
            admin = User(login='admin', role='admin')
            admin.set_password('123456')
            db.session.add(admin)
        if not User.query.filter_by(login='operator').first():
            op = User(login='operator', role='operator')
            op.set_password('123456')
            db.session.add(op)
        db.session.commit()

    # Публичная страница
    @app.route('/')
    def index():
        form = AppealForm()
        return render_template('index.html', form=form)

    # Обработка формы обращения
    @app.route('/submit', methods=['POST'])
    def submit():
        form = AppealForm()
        if form.validate_on_submit():
            code = generate_code()
            while Appeal.query.filter_by(tracking_code=code).first():
                code = generate_code()
            appeal = Appeal(
                tracking_code=code,
                appeal_type=form.appeal_type.data,
                category=form.category.data,
                title=form.title.data,
                description=form.description.data,
                contact=form.contact.data or 'Анонимно'
            )
            db.session.add(appeal)
            db.session.flush()
            db.session.add(StatusHistory(appeal_id=appeal.id, status='new', comment='Заявка зарегистрирована'))
            db.session.add(ActivityLog(action='Создание обращения', user='Гражданин', detail=code))
            db.session.commit()
            return jsonify({'success': True, 'code': code})
        return jsonify({'success': False, 'error': 'Заполните обязательные поля'}), 400

    @app.route('/track')
    def track_page():
        return render_template('track.html')

    @app.route('/api/track', methods=['POST'])
    def track_api():
        data = request.get_json()
        code = data.get('code', '').upper()
        appeal = Appeal.query.filter_by(tracking_code=code).first()
        if not appeal:
            return jsonify({'success': False, 'error': 'Обращение не найдено'}), 404
        history = []
        for h in sorted(appeal.history, key=lambda x: x.changed_at, reverse=True):
            history.append({
                'status': h.status,
                'comment': h.comment,
                'user': h.user.login if h.user else 'Система',
                'date': h.changed_at.strftime('%d.%m.%Y %H:%M')
            })
        return jsonify({
            'success': True,
            'data': {
                'title': appeal.title,
                'code': appeal.tracking_code,
                'status': appeal.status,
                'type': appeal.appeal_type,
                'category': appeal.category,
                'date': appeal.created_at.strftime('%d.%m.%Y'),
                'description': appeal.description,
                'history': history
            }
        })

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(login=form.login.data).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                flash('Вход выполнен успешно', 'success')
                return redirect(url_for('admin' if user.role == 'admin' else 'operator'))
            flash('Неверный логин или пароль', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Сеанс завершён', 'info')
        return redirect(url_for('index'))

    @app.route('/operator')
    @login_required
    @role_required(['operator', 'admin'])
    def operator():
        return render_template('operator.html')

    @app.route('/api/operator/appeals')
    @login_required
    def operator_appeals():
        status = request.args.get('status', 'all')
        category = request.args.get('category', 'all')
        search = request.args.get('search', '').lower()
        q = Appeal.query
        if status != 'all':
            q = q.filter_by(status=status)
        if category != 'all':
            q = q.filter_by(category=category)
        if search:
            q = q.filter(Appeal.title.ilike(f'%{search}%') | Appeal.tracking_code.ilike(f'%{search}%'))
        appeals = q.order_by(Appeal.created_at.desc()).all()
        return jsonify([{
            'id': a.id, 'code': a.tracking_code, 'type': a.appeal_type, 'title': a.title,
            'status': a.status, 'date': a.created_at.strftime('%d.%m.%Y')
        } for a in appeals])

    @app.route('/api/operator/status', methods=['POST'])
    @login_required
    def update_status():
        data = request.get_json()
        appeal = Appeal.query.get_or_404(data['id'])
        appeal.status = data['new_status']
        appeal.updated_at = datetime.utcnow()
        db.session.add(StatusHistory(
            appeal_id=appeal.id, status=data['new_status'],
            comment=data.get('comment', ''), user_id=current_user.id
        ))
        db.session.add(ActivityLog(action='Изменение статуса', user=current_user.login, detail=f"{appeal.tracking_code} -> {data['new_status']}"))
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/admin')
    @login_required
    @role_required(['admin'])
    def admin():
        return render_template('admin.html')

    @app.route('/api/admin/stats')
    @login_required
    def admin_stats():
        statuses = {'new': 0, 'progress': 0, 'done': 0, 'reject': 0}
        categories = {}
        for a in Appeal.query.all():
            statuses[a.status] = statuses.get(a.status, 0) + 1
            categories[a.category] = categories.get(a.category, 0) + 1
        return jsonify({'status': statuses, 'category': categories})

    @app.route('/api/admin/users')
    @login_required
    def admin_users():
        return jsonify([{
            'id': u.id, 'login': u.login, 'role': u.role, 'created': u.created_at.strftime('%d.%m.%Y')
        } for u in User.query.all()])

    @app.route('/api/admin/users', methods=['POST'])
    @login_required
    def admin_create_user():
        data = request.get_json()
        if User.query.filter_by(login=data['login']).first():
            return jsonify({'success': False, 'error': 'Пользователь уже существует'}), 400
        u = User(login=data['login'], role=data['role'])
        u.set_password(data['password'])
        db.session.add(u)
        db.session.add(ActivityLog(action='Создание пользователя', user=current_user.login, detail=data['login']))
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
    @login_required
    def admin_delete_user(uid):
        u = User.query.get_or_404(uid)
        if u.login == 'admin':
            return jsonify({'success': False, 'error': 'Нельзя удалить главного администратора'}), 403
        db.session.delete(u)
        db.session.add(ActivityLog(action='Удаление пользователя', user=current_user.login, detail=u.login))
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/admin/logs')
    @login_required
    def admin_logs():
        logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(50).all()
        return jsonify([{
            'action': l.action, 'user': l.user, 'detail': l.detail,
            'timestamp': l.timestamp.strftime('%d.%m.%Y %H:%M')
        } for l in logs])

    @app.route('/export/csv')
    @login_required
    def export_csv():
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Код', 'Тип', 'Категория', 'Тема', 'Описание', 'Контакт', 'Статус', 'Дата'])
        for a in Appeal.query.all():
            cw.writerow([a.tracking_code, a.appeal_type, a.category, a.title, a.description, a.contact, a.status, a.created_at.strftime('%d.%m.%Y')])
        out = io.BytesIO()
        out.write(si.getvalue().encode('utf-8-sig'))
        out.seek(0)
        return send_file(out, mimetype='text/csv', as_attachment=True, download_name=f'appeals_{datetime.now().strftime("%Y%m%d")}.csv')

    return app

if __name__ == '__main__':
    import os
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
