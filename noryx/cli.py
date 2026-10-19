"""Explicit maintenance; no automatic seeding at startup."""
import secrets, re
from decimal import Decimal
from pathlib import Path
import click
from flask import current_app
from .models import *
from .security import hasher, revoke, password_valid
SOURCE_CATEGORIES={'web':'Web Hosting','web-reseller':'Reseller Web Hosting','vps':'VPS Hosting','bot-hosting':'Discord Bot Hosting','rdp-hosting':'RDP Hosting','colocation':'Colocation','game/minecraft':'Minecraft Hosting Premium','game':'Game Hosting',**{'game/'+s:s.title()+' Hosting' for s in ['cs2','hytale','palworld','valheim','rust','fivem','terraria','ark']}}

def register_commands(app):
    def dev_only():
        if current_app.config['ENVIRONMENT']!='development': raise click.ClickException('Demo commands are development-only.')
    def demo_accounts(reset=False):
        dev_only()
        for role in ('client','admin'):
            email=f'{role}@noryx.test'; user=db.session.scalar(db.select(User).where(User.email==email))
            if user and not user.demo: raise click.ClickException('Reserved email is a non-demo account; refusing to overwrite.')
            if user and not reset:
                click.echo(f'{email}: already exists; use reset-demo-credentials.'); continue
            password=secrets.token_urlsafe(24)+'7a'
            if not user:
                user=User(email=email,name='Demo '+role.title(),role=role,demo=True); db.session.add(user)
            else: revoke(user.id)
            user.password_hash=hasher.hash(password); user.suspended=False; db.session.commit()
            click.echo(f'{email}  {password}')
    @app.cli.command('seed-demo')
    def seed_demo(): demo_accounts()
    @app.cli.command('reset-demo-credentials')
    def reset_demo(): demo_accounts(True)
    @app.cli.command('remove-demo')
    @click.confirmation_option(prompt='Delete demo accounts and their owned development records?')
    def remove_demo():
        dev_only(); ids=list(db.session.scalars(db.select(User.id).where(User.demo.is_(True))))
        if not ids: click.echo('No demo accounts.'); return
        invoice_ids=db.select(Invoice.id).where(Invoice.user_id.in_(ids))
        if db.session.scalar(db.select(Payment.id).where(Payment.actor_id.in_(ids),Payment.invoice_id.not_in(invoice_ids)).limit(1)) or db.session.scalar(db.select(WalletEntry.id).where(WalletEntry.actor_id.in_(ids),WalletEntry.user_id.not_in(ids)).limit(1)):
            raise click.ClickException('Demo staff affected non-demo finances. Use a clean production database.')
        service_ids=db.select(Service.id).where(Service.user_id.in_(ids)); ticket_ids=db.select(Ticket.id).where(Ticket.user_id.in_(ids))
        db.session.execute(db.delete(ServiceRequest).where(ServiceRequest.service_id.in_(service_ids)))
        db.session.execute(db.delete(TicketReply).where(TicketReply.ticket_id.in_(ticket_ids)|TicketReply.user_id.in_(ids)))
        db.session.execute(db.update(Ticket).where(Ticket.assigned_id.in_(ids)).values(assigned_id=None))
        for model in (Ticket,Service): db.session.execute(db.delete(model).where(model.user_id.in_(ids)))
        db.session.execute(db.delete(Payment).where(Payment.invoice_id.in_(invoice_ids)))
        db.session.execute(db.delete(Invoice).where(Invoice.user_id.in_(ids)))
        for order in db.session.scalars(db.select(Order).where(Order.user_id.in_(ids),Order.status!='cancelled')):
            db.session.execute(db.update(Plan).where(Plan.id==order.plan_id).values(stock=Plan.stock+1))
        for model in (Order,WalletEntry,LoginSession,PasswordReset): db.session.execute(db.delete(model).where(model.user_id.in_(ids)))
        db.session.execute(db.delete(EmailJob).where(EmailJob.recipient.in_(['client@noryx.test','admin@noryx.test'])))
        db.session.execute(db.update(Audit).where(Audit.actor_id.in_(ids)).values(actor_id=None))
        db.session.execute(db.delete(User).where(User.id.in_(ids))); db.session.commit()
        click.echo('Demo accounts and owned activity removed; catalog changes and anonymized audits retained.')
    @app.cli.command('create-admin')
    @click.option('--email',prompt=True)
    @click.option('--name',prompt=True)
    @click.password_option()
    def create_admin(email,name,password):
        email=email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254: raise click.ClickException('Invalid email.')
        if not password_valid(password): raise click.ClickException('Use 12–128 characters including letters and a number.')
        if db.session.scalar(db.select(User.id).where(User.email==email)): raise click.ClickException('Account already exists.')
        db.session.add(User(email=email,name=name[:100],role='super_admin',password_hash=hasher.hash(password))); db.session.commit(); click.echo('Administrator created.')
    @app.cli.command('import-catalog')
    def import_catalog():
        from bs4 import BeautifulSoup
        count=0
        for path,name in SOURCE_CATEGORIES.items():
            slug=path.replace('/','-'); category=db.session.scalar(db.select(Category).where(Category.slug==slug))
            if not category:
                category=Category(name=name,slug=slug,source_path='/'+path+'/'); db.session.add(category); db.session.flush()
            source=Path(current_app.config['SITE_ROOT'])/path/'index.html'
            if not source.exists(): continue
            soup=BeautifulSoup(source.read_text(),'html.parser')
            for h in soup.select('h3'):
                card=h.parent
                for _ in range(4):
                    if card is None: break
                    text=card.get_text(' ',strip=True)
                    if re.search(r'₹[\d,]+(?:\.\d+)?',text) and re.search(r'\bOrder\b',text): break
                    card=card.parent
                if card is None: continue
                text=card.get_text(' ',strip=True); prices=re.findall(r'₹([\d,]+(?:\.\d+)?)',text)
                if len(prices)!=1 or not re.search(r'\bOrder\b',text): continue
                name=h.get_text(' ',strip=True)
                if db.session.scalar(db.select(Plan.id).where(Plan.category_id==category.id,Plan.name==name)): continue
                evidence=f'Archived source: /{path}/\n{text}\nUnverified display estimate. Confirm specifications, taxes, cycle and availability before publishing.'
                plan=Plan(category_id=category.id,name=name,status='review',stock=0,source_evidence=evidence,specifications={}); db.session.add(plan); db.session.flush()
                if '/month' in text or '/mo' in text:
                    db.session.add(PlanPrice(plan_id=plan.id,cycle='monthly',amount=int(Decimal(prices[0].replace(',',''))*100),setup_fee=0,currency='INR'))
                count+=1
        db.session.commit(); click.echo(f'Imported {count} visible plans into review. Hidden configuration variants need manual review. No stock inferred.')
    @app.cli.command('dispatch-mail')
    def dispatch_mail():
        import os
        if not current_app.config['REDIS_URL'] or not os.getenv('SMTP_HOST'): raise click.ClickException('Configure Redis and SMTP first.')
        from redis import Redis
        from rq import Queue, Retry
        queue=Queue('mail',connection=Redis.from_url(current_app.config['REDIS_URL'])); count=0
        for job in db.session.scalars(db.select(EmailJob).where(EmailJob.state=='pending')):
            changed=db.session.execute(db.update(EmailJob).where(EmailJob.id==job.id,EmailJob.state=='pending').values(state='queued'))
            db.session.commit()
            if not changed.rowcount: continue
            try:
                queue.enqueue('noryx.jobs.send_email',job.id,job_id=f'noryx-mail-{job.id}',retry=Retry(max=3,interval=[60,300,900])); count+=1
            except Exception:
                job.state='pending'; db.session.commit(); raise
        db.session.commit(); click.echo(f'Queued {count} messages.')
