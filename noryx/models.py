"""Relational business records. Money is stored in integer minor units."""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()
def now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(40), unique=True, index=True)
    first_name = db.Column(db.String(60), nullable=False, default='')
    last_name = db.Column(db.String(60), nullable=False, default='')
    phone = db.Column(db.String(32), nullable=False, default='')
    country = db.Column(db.String(80), nullable=False, default='')
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    notification_preferences = db.Column(db.JSON, nullable=False, default=dict)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='client')
    suspended = db.Column(db.Boolean, nullable=False, default=False)
    demo = db.Column(db.Boolean, nullable=False, default=False)
    billing_address = db.Column(db.Text, default='')
    last_login_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (CheckConstraint("role IN ('super_admin','admin','support','billing','client')"),)

class LoginSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user_agent = db.Column(db.String(200))
    user = db.relationship(User)

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)

class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.ForeignKey('user.id'))
    event = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text, nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class UserNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    actor_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship(User, foreign_keys=[user_id])

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    source_path = db.Column(db.String(200))

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, nullable=False, default=False)

class Processor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, nullable=False, default=False)

class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.ForeignKey('category.id'), nullable=False, index=True)
    location_id = db.Column(db.ForeignKey('location.id'))
    processor_id = db.Column(db.ForeignKey('processor.id'))
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default='')
    specifications = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(20), nullable=False, default='review')
    stock = db.Column(db.Integer, nullable=False, default=0)
    revision = db.Column(db.Integer, nullable=False, default=1)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    source_evidence = db.Column(db.Text, default='')
    category = db.relationship(Category)
    location = db.relationship(Location)
    processor = db.relationship(Processor)
    prices = db.relationship('PlanPrice', backref='plan', lazy='selectin')
    __table_args__ = (CheckConstraint('stock >= 0'), CheckConstraint("status IN ('review','published','hidden','archived')"))

class PlanPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.ForeignKey('plan.id'), nullable=False, index=True)
    cycle = db.Column(db.String(20), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='INR')
    amount = db.Column(db.Integer, nullable=False)
    setup_fee = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('plan_id','cycle'), CheckConstraint('amount >= 0 AND setup_fee >= 0'))

class ProductRevision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.ForeignKey('plan.id'), nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    percent = db.Column(db.Integer, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    max_uses = db.Column(db.Integer, nullable=False)
    uses = db.Column(db.Integer, nullable=False, default=0)
    category_id = db.Column(db.ForeignKey('category.id'))
    __table_args__ = (CheckConstraint('percent BETWEEN 1 AND 100'), CheckConstraint('uses >= 0 AND max_uses >= 0'))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    plan_id = db.Column(db.ForeignKey('plan.id'), nullable=False)
    idempotency_key = db.Column(db.String(64), nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='awaiting_payment')
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship(User)
    __table_args__ = (UniqueConstraint('user_id','idempotency_key'), CheckConstraint('total >= 0'), CheckConstraint("status IN ('awaiting_payment','paid','active','cancelled')"))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.ForeignKey('order.id'), unique=True, nullable=False)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    total = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='unpaid')
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    order = db.relationship(Order)
    @property
    def number(self): return f'NORYX-{self.id:08d}'

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.ForeignKey('invoice.id'), nullable=False, unique=True)
    reference = db.Column(db.String(150), nullable=False, unique=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    actor_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.ForeignKey('order.id'), nullable=False, unique=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='active')
    next_due = db.Column(db.DateTime, nullable=False)
    fulfillment_reference = db.Column(db.String(200), nullable=False)
    order = db.relationship(Order)

class ServiceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.ForeignKey('service.id'), nullable=False)
    kind = db.Column(db.String(30), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class WalletEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='INR')
    reference = db.Column(db.String(150), nullable=False, unique=True)
    reason = db.Column(db.Text, nullable=False)
    actor_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='awaiting_staff')
    priority = db.Column(db.String(12), nullable=False, default='normal')
    assigned_id = db.Column(db.ForeignKey('user.id'))
    assignee = db.relationship(User, foreign_keys=[assigned_id])
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship(User, foreign_keys=[user_id])
    replies = db.relationship('TicketReply', backref='ticket', order_by='TicketReply.id')

class TicketReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.ForeignKey('ticket.id'), nullable=False, index=True)
    user_id = db.Column(db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    internal = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship(User)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    publish_at = db.Column(db.DateTime, nullable=False, default=now)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    pinned = db.Column(db.Boolean, nullable=False, default=False)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, nullable=False, default=False)

class EmailJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(254), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    state = db.Column(db.String(20), nullable=False, default='pending')
    attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

class WorkspaceSetting(db.Model):
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

class PlanAddon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False, default='')
    amount = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False, default='INR')
    active = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint('amount >= 0'),)
