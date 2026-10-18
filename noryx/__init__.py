import os
from datetime import timedelta, datetime, timezone
from pathlib import Path
from flask import Flask, render_template, g
from flask_migrate import Migrate
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine
from .models import db, User
from .security import csrf, limiter, load_user, PERMISSIONS

@event.listens_for(Engine, 'connect')
def sqlite_foreign_keys(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        connection.execute('PRAGMA foreign_keys=ON')

def create_app(config=None):
    app = Flask(__name__, static_url_path='/panel-assets')
    env = os.getenv('NORYX_ENV','development')
    app.config.from_mapping(
        ENVIRONMENT=env, SECRET_KEY=os.getenv('SECRET_KEY'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL','sqlite:///noryx.sqlite'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=env=='production', PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=1024*1024, WTF_CSRF_TIME_LIMIT=7200,
        RATELIMIT_STORAGE_URI=os.getenv('REDIS_URL') or 'memory://',
        REDIS_URL=os.getenv('REDIS_URL'), PUBLIC_URL=os.getenv('PUBLIC_URL','http://127.0.0.1:8081'),
        SITE_ROOT=str(Path(__file__).resolve().parent.parent/'site'),
    )
    if config: app.config.update(config)
    if os.getenv('TRUST_PROXY') == '1':
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)
    Path(app.instance_path).mkdir(parents=True,exist_ok=True)
    if not app.config['SECRET_KEY']:
        if app.config['ENVIRONMENT']=='production': raise RuntimeError('SECRET_KEY required in production')
        # Persist a generated development signing key outside the source package.
        keyfile = Path(app.instance_path)/'development-key'
        if not keyfile.exists():
            import secrets
            fd = os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f: f.write(secrets.token_hex(32))
        app.config['SECRET_KEY']=keyfile.read_text()
    if app.config['ENVIRONMENT']=='production':
        if len(app.config['SECRET_KEY']) < 32: raise RuntimeError('Use a random SECRET_KEY of at least 32 characters')
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'): raise RuntimeError('PostgreSQL required in production')
        if not app.config['REDIS_URL']: raise RuntimeError('Redis required in production')
        if not app.config['PUBLIC_URL'].startswith('https://'): raise RuntimeError('HTTPS PUBLIC_URL required')
    db.init_app(app)
    Migrate(app,db)
    csrf.init_app(app)
    limiter.init_app(app)
    app.before_request(load_user)
    from .routes import web
    app.register_blueprint(web)
    from .cli import register_commands
    register_commands(app)
    with app.app_context():
        if app.config['ENVIRONMENT']=='production' and inspect(db.engine).has_table('user'):
            if db.session.scalar(db.select(User.id).where(User.demo.is_(True)).limit(1)):
                raise RuntimeError('Remove development accounts before production startup')
    @app.context_processor
    def common():
        return {'current_user':getattr(g,'user',None), 'permissions':PERMISSIONS.get(g.user.role,set()) if getattr(g,'user',None) else set(),
                'development':app.config['ENVIRONMENT']!='production','current_year':datetime.now(timezone.utc).year}
    @app.template_filter('money')
    def money(v): return f'{v//100:,}.{v%100:02d}' if v>=0 else '-'+money(-v)
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        if getattr(g,'user',None) or response.mimetype=='text/html': response.headers['Cache-Control']='no-store'
        if app.config['ENVIRONMENT']=='production': response.headers['Strict-Transport-Security']='max-age=31536000'
        if request_is_panel():
            response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        return response
    for status in (400,403,404,409,413,429,503):
        app.register_error_handler(status,lambda e: (render_template('error.html',title=str(e.code),message=e.description),e.code))
    return app

def request_is_panel():
    from flask import request
    return request.path.startswith(('/client','/admin','/catalog','/login','/register','/forgot','/reset','/knowledgebase'))
