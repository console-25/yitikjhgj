from datetime import timedelta
from functools import wraps
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from flask import abort, current_app, g, redirect, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from .models import db, User, LoginSession, Audit, now

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
PERMISSIONS = {
    'super_admin': {'users','catalog','billing','support','content','audit'},
    'admin': {'users','catalog','billing','support','content','audit'},
    'support': {'support'}, 'billing': {'billing'}, 'client': set(),
}
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def verify(encoded, password):
    try: return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError): return False

def password_valid(value):
    return 12 <= len(value) <= 128 and any(c.isalpha() for c in value) and any(c.isdigit() for c in value)

def audit(event, detail='', actor=None):
    db.session.add(Audit(actor_id=actor or (g.user.id if getattr(g,'user',None) else None),event=event,detail=str(detail)[:4000]))

def load_user():
    g.user = None
    g.login_session = None
    token = session.get('sid')
    if token:
        record = db.session.scalar(db.select(LoginSession).where(LoginSession.token_hash==digest(token)))
        if record and record.expires_at > now() and not record.user.suspended and not record.user.deleted_at:
            g.user, g.login_session = record.user, record
        else: session.clear()

def sign_in(user, remember=False):
    if getattr(g,'login_session',None): db.session.delete(g.login_session)
    session.clear()
    raw = secrets.token_urlsafe(48)
    session['sid'] = raw
    session.permanent = remember
    db.session.add(LoginSession(token_hash=digest(raw),user_id=user.id,
        expires_at=now()+timedelta(days=30 if remember else 1),user_agent=request.user_agent.string[:200]))
    user.last_login_at=now()
    audit('auth.login',actor=user.id)
    db.session.commit()

def revoke(user_id):
    db.session.execute(db.delete(LoginSession).where(LoginSession.user_id==user_id))

def required(permission=None):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            if not g.user: return redirect(url_for('web.login'))
            if permission and permission not in PERMISSIONS[g.user.role]: abort(403)
            return fn(*args,**kwargs)
        return wrapped
    return decorator

def reauthenticate():
    if not verify(g.user.password_hash, request.form.get('current_password','')):
        abort(403, 'Confirm your current password to perform this action.')

def owned(model, ident, permission=None):
    record = db.get_or_404(model, ident)
    if record.user_id != g.user.id and (not permission or permission not in PERMISSIONS[g.user.role]): abort(404)
    return record
