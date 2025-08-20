from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, TextAreaField, SelectField, TimeField, BooleanField
from wtforms.validators import DataRequired, Email, Length
from models import db, User, SupportMessage, SupportResponse, EscalationRule, ResponseTemplate, ScheduleSlot, AppearanceSettings, KnowledgeBase, MessageAnalysis, ConversationState, NodeRedConnection, NodeRedWidget, VpnConnection, NodeRedConnectionVpn, Unit, AIServiceConfig, Notification, AutoResponse, TroubleshootingSession, SystemConfig, TelegramGroup
from ai_support import ai_support
from conversation_manager import ConversationManager
from datetime import datetime, time, timedelta
import os
import json
from dotenv import load_dotenv
import requests
import re
from urllib.parse import unquote
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/support_system.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize conversation manager with Flask app context
conversation_manager = ConversationManager(app)

# System configuration helpers
def get_system_config_value(key, default=None):
    cfg = SystemConfig.query.filter_by(key=key).first()
    return cfg.value if cfg else default

def set_system_config_value(key, value, description=None):
    cfg = SystemConfig.query.filter_by(key=key).first()
    if not cfg:
        cfg = SystemConfig(key=key, value=str(value), description=description)
        db.session.add(cfg)
    else:
        cfg.value = str(value)
        if description is not None:
            cfg.description = description

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class ResponseForm(FlaskForm):
    response_text = TextAreaField('Response', validators=[DataRequired(), Length(min=1, max=1000)])

class ScheduleForm(FlaskForm):
    user_id = SelectField('Tech Team Member', coerce=int, validators=[DataRequired()])
    # Multiple day selection using checkboxes
    monday = BooleanField('Monday')
    tuesday = BooleanField('Tuesday')
    wednesday = BooleanField('Wednesday')
    thursday = BooleanField('Thursday')
    friday = BooleanField('Friday')
    saturday = BooleanField('Saturday')
    sunday = BooleanField('Sunday')
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    is_primary = BooleanField('Primary On-Call')
    
    def validate(self, extra_validators=None):
        """Custom validation to ensure at least one day is selected"""
        if not super().validate(extra_validators):
            return False
        
        # Check if at least one day is selected
        days_selected = any([
            self.monday.data, self.tuesday.data, self.wednesday.data,
            self.thursday.data, self.friday.data, self.saturday.data, self.sunday.data
        ])
        
        if not days_selected:
            self.monday.errors.append('Please select at least one day of the week.')
            return False
        
        return True
    
    def get_selected_days(self):
        """Return list of selected day numbers (0=Monday, 6=Sunday)"""
        selected_days = []
        day_mapping = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        for day_name, day_number in day_mapping.items():
            if getattr(self, day_name).data:
                selected_days.append(day_number)
        
        return selected_days

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    is_admin = BooleanField('Admin Access')
    telegram_user_id = StringField('Telegram User ID', validators=[Length(max=50)])

class AdminSettingsForm(FlaskForm):
    """Form for admin dashboard settings with CSRF protection"""
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=100)])
    color_scheme = SelectField('Color Scheme', choices=[
        ('blue', 'Blue'), ('green', 'Green'), ('purple', 'Purple'), 
        ('red', 'Red'), ('dark', 'Dark'), ('custom', 'Custom')
    ], validators=[DataRequired()])
    primary_color = StringField('Primary Color')
    secondary_color = StringField('Secondary Color')
    accent_color = StringField('Accent Color')
    logo_max_height = SelectField('Logo Max Height (px)', choices=[
        ('80', '80px'), ('100', '100px'), ('120', '120px'), ('150', '150px'), 
        ('180', '180px'), ('200', '200px'), ('250', '250px'), ('300', '300px')
    ], default='120')
    logo_max_width = SelectField('Logo Max Width (px)', choices=[
        ('200', '200px'), ('250', '250px'), ('300', '300px'), ('350', '350px'), 
        ('400', '400px'), ('450', '450px'), ('500', '500px'), ('600', '600px')
    ], default='300')
    custom_css = TextAreaField('Custom CSS')

    # AI Service configuration
    ai_provider = SelectField('AI Provider', choices=[
        ('openai', 'OpenAI'),
        ('azure_openai', 'Azure OpenAI'),
        ('anthropic', 'Anthropic'),
        ('ollama', 'Ollama (local)'),
        ('custom', 'Custom API')
    ], default='openai')
    ai_model = StringField('Model', render_kw={'placeholder': 'e.g., gpt-4o, gpt-4o-mini'})
    ai_api_key = PasswordField('API Key')
    ai_base_url = StringField('Base URL', render_kw={'placeholder': 'Optional, e.g., https://api.openai.com/v1'})
    ai_temperature = SelectField('Temperature', choices=[
        ('0.0','0.0'),('0.1','0.1'),('0.2','0.2'),('0.3','0.3'),('0.4','0.4'),
        ('0.5','0.5'),('0.6','0.6'),('0.7','0.7'),('0.8','0.8'),('0.9','0.9'),('1.0','1.0')
    ], default='0.7')
    ai_top_p = SelectField('Top P', choices=[
        ('','(default)'),('0.1','0.1'),('0.2','0.2'),('0.3','0.3'),('0.4','0.4'),('0.5','0.5'),
        ('0.6','0.6'),('0.7','0.7'),('0.8','0.8'),('0.9','0.9'),('1.0','1.0')
    ], default='')
    ai_max_tokens = StringField('Max Tokens', render_kw={'placeholder': 'Optional max output tokens'})
    ai_organization = StringField('Organization (optional)')
    ai_is_enabled = BooleanField('Enable AI Auto Support')
    ai_system_prompt = TextAreaField('AI System Prompt', render_kw={'placeholder': 'Optional system prompt to guide AI behavior (e.g., tone, role, constraints).', 'rows': 6})

    # AI Auto-Acknowledgement settings
    ack_text = TextAreaField('AI Acknowledgement Text', render_kw={'placeholder': 'Message sent to users when no confident AI answer is available.', 'rows': 3})
    ack_interval_minutes = SelectField('Ack Min Interval (minutes)', choices=[
        ('0', 'No rate limit'), ('5', '5'), ('10', '10'), ('15', '15'), ('30', '30'), ('60', '60')
    ], default='10')

class KnowledgeBaseForm(FlaskForm):
    """Form for managing AI knowledge base entries"""
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    question_pattern = TextAreaField('Question Pattern', validators=[DataRequired()], 
                                   render_kw={'placeholder': 'Describe the type of question this answers (e.g., "How to reset password")'})
    solution_text = TextAreaField('Solution', validators=[DataRequired()],
                                render_kw={'placeholder': 'Provide the solution or answer'})
    category = SelectField('Category', choices=[
        ('password_reset', 'Password Reset'),
        ('login_issue', 'Login Issues'),
        ('technical_error', 'Technical Errors'),
        ('account_management', 'Account Management'),
        ('billing', 'Billing'),
        ('feature_request', 'Feature Requests'),
        ('general_inquiry', 'General Inquiries')
    ], validators=[DataRequired()])
    keywords = StringField('Keywords', render_kw={'placeholder': 'Comma-separated keywords for matching'})
    troubleshooting_steps = TextAreaField('Troubleshooting Steps (JSON)', 
                                        render_kw={'placeholder': '["Step 1", "Step 2", "Step 3"]'})
    confidence_threshold = SelectField('Confidence Threshold', choices=[
        ('0.5', '50% - Low (more responses)'),
        ('0.6', '60% - Medium-Low'),
        ('0.7', '70% - Medium (recommended)'),
        ('0.8', '80% - Medium-High'),
        ('0.9', '90% - High (fewer responses)')
    ], default='0.7', validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get recent support messages
    recent_messages = SupportMessage.query.order_by(SupportMessage.created_at.desc()).limit(10).all()
    
    # Get statistics
    total_messages = SupportMessage.query.count()
    open_messages = SupportMessage.query.filter_by(status='open').count()
    in_progress_messages = SupportMessage.query.filter_by(status='in_progress').count()
    resolved_messages = SupportMessage.query.filter_by(status='resolved').count()
    
    # Get current on-call person
    current_on_call_schedule = get_current_on_call()
    current_on_call = current_on_call_schedule.user if current_on_call_schedule else None
    
    stats = {
        'total': total_messages,
        'open': open_messages,
        'in_progress': in_progress_messages,
        'resolved': resolved_messages
    }
    
    return render_template('dashboard.html', 
                         messages=recent_messages, 
                         stats=stats,
                         current_on_call=current_on_call)

@app.route('/messages')
@login_required
def messages():
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = SupportMessage.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    messages = query.order_by(SupportMessage.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('messages.html', messages=messages, status_filter=status_filter)

@app.route('/message/<int:message_id>')
@login_required
def message_detail(message_id):
    message = SupportMessage.query.get_or_404(message_id)
    form = ResponseForm()
    return render_template('message_detail.html', message=message, form=form)

@app.route('/message/<int:message_id>/respond', methods=['POST'])
@login_required
def respond_to_message(message_id):
    message = SupportMessage.query.get_or_404(message_id)
    form = ResponseForm()
    
    if form.validate_on_submit():
        # Create response
        response = SupportResponse(
            message_id=message_id,
            user_id=current_user.id,
            response_text=form.response_text.data
        )
        db.session.add(response)
        
        # Update message status
        if message.status == 'open':
            message.status = 'in_progress'
            message.assigned_to_id = current_user.id
        
        message.updated_at = datetime.utcnow()
        
        # Update conversation manager with technician response
        try:
            print(f"DEBUG: Attempting to update conversation for user {message.telegram_user_id} with response {response.id}")
            conversation_manager.update_conversation_response(
                user_telegram_id=message.telegram_user_id,
                response_id=response.id
            )
            print(f"DEBUG: Successfully updated conversation manager for response {response.id}")
        except Exception as e:
            print(f"DEBUG ERROR: Failed to update conversation manager: {e}")
            import traceback
            traceback.print_exc()
        
        # Send response via Telegram bot
        success = send_telegram_response(message, form.response_text.data)
        if success:
            response.sent_to_telegram = True
            flash('Response sent successfully!', 'success')
        else:
            flash('Response saved but failed to send via Telegram', 'warning')
        
        db.session.commit()
        return redirect(url_for('message_detail', message_id=message_id))
    
    return render_template('message_detail.html', message=message, form=form)

@app.route('/message/<int:message_id>/status', methods=['POST'])
@login_required
def update_message_status(message_id):
    message = SupportMessage.query.get_or_404(message_id)
    new_status = request.form.get('status')
    
    if new_status in ['open', 'in_progress', 'resolved', 'escalated']:
        message.status = new_status
        message.updated_at = datetime.utcnow()
        
        if new_status == 'resolved':
            message.resolved_at = datetime.utcnow()
        elif new_status == 'in_progress' and not message.assigned_to_id:
            message.assigned_to_id = current_user.id
        
        db.session.commit()
        flash(f'Message status updated to {new_status}', 'success')
    
    return redirect(url_for('message_detail', message_id=message_id))

@app.route('/schedule')
@login_required
def schedule():
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))
    
    schedules = ScheduleSlot.query.join(User).order_by(ScheduleSlot.day_of_week, ScheduleSlot.start_time).all()
    form = ScheduleForm()
    form.user_id.choices = [(u.id, f"{u.first_name} {u.last_name}") for u in User.query.filter_by(is_active=True).all()]
    
    return render_template('schedule.html', schedules=schedules, form=form)

@app.route('/schedule/add', methods=['POST'])
@login_required
def add_schedule():
    """Add new schedule slots for selected days"""
    form = ScheduleForm()
    form.user_id.choices = [(u.id, f"{u.first_name} {u.last_name}") for u in User.query.all()]
    
    if form.validate_on_submit():
        selected_days = form.get_selected_days()
        created_count = 0
        
        for day_number in selected_days:
            # Check if schedule already exists for this user/day/time combination
            existing_schedule = ScheduleSlot.query.filter_by(
                user_id=form.user_id.data,
                day_of_week=day_number,
                start_time=form.start_time.data,
                end_time=form.end_time.data
            ).first()
            
            if not existing_schedule:
                schedule = ScheduleSlot(
                    user_id=form.user_id.data,
                    day_of_week=day_number,
                    start_time=form.start_time.data,
                    end_time=form.end_time.data,
                    is_primary=form.is_primary.data
                )
                db.session.add(schedule)
                created_count += 1
            else:
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                flash(f'Schedule for {day_names[day_number]} already exists for this user and time slot.', 'warning')
        
        if created_count > 0:
            db.session.commit()
            if created_count == 1:
                flash('Schedule slot added successfully!', 'success')
            else:
                flash(f'{created_count} schedule slots added successfully!', 'success')
        
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('schedule'))

@app.route('/schedule/<int:schedule_id>/delete', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))
    
    schedule = ScheduleSlot.query.get_or_404(schedule_id)
    db.session.delete(schedule)
    db.session.commit()
    flash('Schedule deleted successfully!', 'success')
    
    return redirect(url_for('schedule'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))
    
    # Create form instance for the template
    form = UserForm()
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        telegram_user_id = request.form.get('telegram_user_id')
        phone = request.form.get('phone')
        department = request.form.get('department')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already exists!', 'error')
        else:
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin,
                telegram_user_id=telegram_user_id if telegram_user_id else None,
                phone=phone,
                department=department
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'User {username} created successfully!', 'success')
    
    users = User.query.all()
    return render_template('users.html', users=users, form=form)

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Edit user page (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.first_name = request.form['first_name']
        user.last_name = request.form['last_name']
        user.is_admin = 'is_admin' in request.form
        user.is_active = 'is_active' in request.form
        user.telegram_user_id = request.form.get('telegram_user_id') or None
        user.phone = request.form.get('phone')
        user.department = request.form.get('department')
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete user (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting the last admin
    if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
        flash('Cannot delete the last admin user!', 'error')
        return redirect(url_for('users'))
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Cannot delete your own account!', 'error')
        return redirect(url_for('users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User {username} deleted successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/telegram-groups', methods=['GET'])
@login_required
def telegram_groups():
    """Admin page for managing Telegram groups"""
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))
    # Redirect to Admin Settings tab
    return redirect(url_for('admin_settings', tab='telegram-groups'))

@app.route('/templates', methods=['GET', 'POST'])
@login_required
def response_templates():
    """Response templates management"""
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        template_text = request.form['template_text']
        
        template = ResponseTemplate(
            name=name,
            category=category,
            template_text=template_text,
            created_by_id=current_user.id
        )
        db.session.add(template)
        db.session.commit()
        flash(f'Template "{name}" created successfully!', 'success')
    
    templates = ResponseTemplate.query.filter_by(is_active=True).order_by(ResponseTemplate.category, ResponseTemplate.name).all()
    return render_template('templates.html', templates=templates)

@app.route('/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    """Delete response template"""
    template = ResponseTemplate.query.get_or_404(template_id)
    
    # Only creator or admin can delete
    if template.created_by_id != current_user.id and not current_user.is_admin:
        flash('Access denied. You can only delete your own templates.', 'error')
        return redirect(url_for('response_templates'))
    
    template.is_active = False
    db.session.commit()
    flash(f'Template "{template.name}" deleted successfully!', 'success')
    return redirect(url_for('response_templates'))

@app.route('/escalation', methods=['GET', 'POST'])
@login_required
def escalation_rules():
    """Escalation rules management (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        priority = request.form['priority']
        escalation_timeout = int(request.form['escalation_timeout'])
        max_escalation_level = int(request.form['max_escalation_level'])
        
        # Check if rule already exists for this priority
        existing_rule = EscalationRule.query.filter_by(priority=priority, is_active=True).first()
        if existing_rule:
            existing_rule.escalation_timeout = escalation_timeout
            existing_rule.max_escalation_level = max_escalation_level
            flash(f'Escalation rule for {priority} priority updated!', 'success')
        else:
            rule = EscalationRule(
                priority=priority,
                escalation_timeout=escalation_timeout,
                max_escalation_level=max_escalation_level
            )
            db.session.add(rule)
            flash(f'Escalation rule for {priority} priority created!', 'success')
        
        db.session.commit()
    
    # Create default escalation rules
    if not EscalationRule.query.first():
        default_rules = [
            EscalationRule(
                name="Standard Support",
                priority="medium",
                timeout_minutes=30,
                escalation_level=1,
                description="Standard escalation for medium priority issues"
            ),
            EscalationRule(
                name="High Priority",
                priority="high",
                timeout_minutes=15,
                escalation_level=1,
                description="Fast escalation for high priority issues"
            ),
            EscalationRule(
                name="Critical Issues",
                priority="critical",
                timeout_minutes=5,
                escalation_level=1,
                description="Immediate escalation for critical issues"
            )
        ]
        
        for rule in default_rules:
            db.session.add(rule)
        
        db.session.commit()
        print("Default escalation rules created")
    
    # Create default appearance settings
    if not AppearanceSettings.query.first():
        default_appearance = AppearanceSettings(
            company_name="Support System",
            color_scheme="blue",
            primary_color="#0d6efd",
            secondary_color="#6c757d",
            accent_color="#198754"
        )
        db.session.add(default_appearance)
        db.session.commit()
        print("Default appearance settings created")
    
    rules = EscalationRule.query.filter_by(is_active=True).order_by(EscalationRule.priority).all()
    return render_template('escalation.html', rules=rules)

@app.route('/escalation/<int:rule_id>/delete', methods=['POST'])
@login_required
def delete_escalation_rule(rule_id):
    """Delete escalation rule (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    rule = EscalationRule.query.get_or_404(rule_id)
    rule.is_active = False
    db.session.commit()
    flash(f'Escalation rule for {rule.priority} priority deleted!', 'success')
    return redirect(url_for('escalation_rules'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Admin settings for dashboard appearance (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get or create appearance settings
    appearance = AppearanceSettings.query.first()
    if not appearance:
        appearance = AppearanceSettings()
        db.session.add(appearance)
        db.session.commit()

    # Get or create AI service config
    ai_config = AIServiceConfig.query.first()
    if not ai_config:
        ai_config = AIServiceConfig(provider='openai', model='gpt-4o-mini', temperature=0.7, is_enabled=True)
        db.session.add(ai_config)
        db.session.commit()
        
    # Create form with current values
    form = AdminSettingsForm(
        company_name=appearance.company_name,
        color_scheme=appearance.color_scheme,
        primary_color=appearance.primary_color,
        secondary_color=appearance.secondary_color,
        accent_color=appearance.accent_color,
        logo_max_height=str(appearance.logo_max_height or 120),
        logo_max_width=str(appearance.logo_max_width or 300),
        custom_css=appearance.custom_css,
        ai_provider=ai_config.provider or 'openai',
        ai_model=ai_config.model or '',
        ai_api_key='',  # never prefill sensitive values
        ai_base_url=ai_config.base_url or '',
        ai_temperature=str(ai_config.temperature if ai_config.temperature is not None else '0.7'),
        ai_top_p='' if ai_config.top_p is None else str(ai_config.top_p),
        ai_max_tokens='' if ai_config.max_tokens is None else str(ai_config.max_tokens),
        ai_organization=ai_config.organization or '',
        ai_is_enabled=ai_config.is_enabled,
        ai_system_prompt=ai_config.system_prompt or '',
        ack_text=get_system_config_value('ai_ack_text', "Thanks for reaching out! I've notified our on-call technician and someone will assist you shortly. This is an automated acknowledgement."),
        ack_interval_minutes=str(get_system_config_value('ai_ack_interval_minutes', '10'))
    )

    # Conditional processing based on submitted form section
    if request.method == 'POST':
        section = request.form.get('form_section', 'general')

        # Handle support-routing separately (no form validation needed)
        if section == 'support-routing':
            # Handle notification groups configuration
            support_group_id = request.form.get('support_group_id', '').strip()
            forward_to_group = request.form.get('forward_to_group') == 'on'
            escalation_group_id = request.form.get('escalation_group_id', '').strip()
            enable_escalation = request.form.get('enable_escalation') == 'on'
            tech_team_group_id = request.form.get('tech_team_group_id', '').strip()
            enable_tech_notifications = request.form.get('enable_tech_notifications') == 'on'
            
            # Update .env file with new configuration
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            env_lines = []
            
            try:
                # Read existing .env file
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        env_lines = f.readlines()
                
                # Configuration to update
                configs = {
                    'SUPPORT_GROUP_ID': support_group_id,
                    'FORWARD_SUPPORT_TO_GROUP': 'true' if forward_to_group else 'false',
                    'ESCALATION_GROUP_ID': escalation_group_id,
                    'ENABLE_ESCALATION_ALERTS': 'true' if enable_escalation else 'false',
                    'TECH_TEAM_GROUP_ID': tech_team_group_id,
                    'ENABLE_TECH_NOTIFICATIONS': 'true' if enable_tech_notifications else 'false'
                }
                
                # Update existing configs
                found_configs = set()
                for i, line in enumerate(env_lines):
                    for key, value in configs.items():
                        if line.startswith(f'{key}='):
                            env_lines[i] = f'{key}={value}\n'
                            found_configs.add(key)
                            break
                
                # Add missing configurations
                missing_configs = set(configs.keys()) - found_configs
                if missing_configs:
                    # Find or create notification configuration section
                    section_found = False
                    for i, line in enumerate(env_lines):
                        if 'Support Group Configuration' in line or 'Notification Configuration' in line:
                            # Insert missing configs after section header
                            insert_pos = i + 1
                            for key in missing_configs:
                                env_lines.insert(insert_pos, f'{key}={configs[key]}\n')
                                insert_pos += 1
                            section_found = True
                            break
                    
                    if not section_found:
                        # Add new section at end
                        env_lines.append('\n# Notification Configuration\n')
                        for key in missing_configs:
                            env_lines.append(f'{key}={configs[key]}\n')
                
                # Write updated .env file
                with open(env_path, 'w') as f:
                    f.writelines(env_lines)
                
                flash('Notification groups configuration updated successfully! Please restart the bot for changes to take effect.', 'success')
            except Exception as e:
                logger.error(f"Failed to update notification groups configuration: {e}")
                flash(f'Error updating notification groups configuration: {str(e)}', 'error')
            
            db.session.commit()
            return redirect(url_for('admin_settings', tab='telegram-groups'))
        
        # Handle Telegram user IDs configuration
        if section == 'telegram-users':
            import json
            # Get the list of user IDs and names from the form
            user_ids = request.form.getlist('telegram_user_ids[]')
            user_names = request.form.getlist('telegram_user_names[]')
            
            # Combine IDs with names and filter out empty values
            users_data = []
            for i in range(len(user_ids)):
                uid = user_ids[i].strip() if i < len(user_ids) else ''
                uname = user_names[i].strip() if i < len(user_names) else ''
                
                # Only add if user ID is valid (numeric and not empty)
                if uid and uid.isdigit():
                    users_data.append({
                        'id': uid,
                        'name': uname or f'User {uid}'  # Default name if empty
                    })
            
            # Store as JSON in the database
            appearance.telegram_default_users = json.dumps(users_data)
            appearance.updated_at = datetime.utcnow()
            appearance.updated_by_id = current_user.id
            
            db.session.commit()
            flash(f'Saved {len(users_data)} Telegram user(s) with names', 'success')
            return redirect(url_for('admin_settings', tab='users'))

        # Ensure CSRF + validators for other forms. Partial forms should include hidden required fields.
        if not form.validate_on_submit():
            flash('Please correct the errors and try again.', 'error')
            return redirect(url_for('admin_settings', tab=section))

        if section == 'general':
            # Handle logo upload
            logo_file = request.files.get('logo')
            if logo_file and logo_file.filename and logo_file.filename.strip() != '':
                try:
                    upload_dir = os.path.join(app.static_folder, 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)

                    filename = secure_filename(logo_file.filename)
                    if not filename:
                        filename = 'logo.png'

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    filename = timestamp + filename
                    logo_path = os.path.join(upload_dir, filename)

                    logo_file.save(logo_path)
                    appearance.logo_filename = filename
                    flash('Logo uploaded successfully!', 'success')
                except Exception as e:
                    flash(f'Error uploading logo: {str(e)}', 'error')

            # Handle favicon upload
            if 'favicon' in request.files:
                favicon_file = request.files['favicon']
                if favicon_file and favicon_file.filename:
                    upload_dir = os.path.join(app.static_folder, 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)

                    filename = secure_filename(favicon_file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    filename = timestamp + filename
                    favicon_path = os.path.join(upload_dir, filename)
                    favicon_file.save(favicon_path)
                    appearance.favicon_filename = filename

            # Update appearance settings only
            appearance.color_scheme = form.color_scheme.data
            appearance.company_name = form.company_name.data
            appearance.custom_css = form.custom_css.data
            appearance.logo_max_height = int(form.logo_max_height.data)
            appearance.logo_max_width = int(form.logo_max_width.data)

            # Update custom colors if scheme is 'custom'
            if appearance.color_scheme == 'custom':
                appearance.primary_color = form.primary_color.data
                appearance.secondary_color = form.secondary_color.data
                appearance.accent_color = form.accent_color.data

            appearance.updated_by_id = current_user.id
            appearance.updated_at = datetime.utcnow()


        elif section == 'ai-integration':
            # Update AI config only (preserve API key if blank)
            ai_config.provider = form.ai_provider.data
            ai_config.model = form.ai_model.data
            if form.ai_api_key.data and form.ai_api_key.data.strip():
                ai_config.api_key = form.ai_api_key.data.strip()
            ai_config.base_url = form.ai_base_url.data or None
            # temperature
            try:
                ai_config.temperature = float(form.ai_temperature.data)
            except Exception:
                ai_config.temperature = 0.7
            # top_p (optional)
            try:
                ai_config.top_p = float(form.ai_top_p.data) if form.ai_top_p.data else None
            except Exception:
                ai_config.top_p = None
            # max_tokens (optional)
            try:
                ai_config.max_tokens = int(form.ai_max_tokens.data) if form.ai_max_tokens.data else None
            except Exception:
                ai_config.max_tokens = None
            ai_config.organization = form.ai_organization.data or None
            ai_config.is_enabled = bool(form.ai_is_enabled.data)
            ai_config.system_prompt = (form.ai_system_prompt.data or '').strip() or None
            ai_config.updated_by_id = current_user.id
            ai_config.updated_at = datetime.utcnow()

            # Persist AI acknowledgement settings
            try:
                set_system_config_value('ai_ack_text', (form.ack_text.data or "Thanks for reaching out! I've notified our on-call technician and someone will assist you shortly. This is an automated acknowledgement.").strip(), description='Text sent when AI cannot answer confidently')
                set_system_config_value('ai_ack_interval_minutes', str(form.ack_interval_minutes.data or '10'), description='Minimum minutes between acknowledgements per conversation')
            except Exception as e:
                logger.error(f"Failed saving ack settings: {e}")

        else:
            # Unknown or unhandled section; no changes
            pass

        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin_settings', tab=section))
    
    # Determine which tab to show
    active_tab = (request.args.get('tab', 'general') or 'general').strip().lower()
    # Normalize aliases to avoid blank content if an unknown value is passed
    alias_map = {
        'ai': 'ai-integration',
        'ai_integration': 'ai-integration',
        'ai-knowledge-base': 'ai-knowledge',
        'knowledge': 'ai-knowledge',
        'analytics': 'ai-analytics',
        'telegram': 'telegram-groups',
        'node': 'node-red',
        'node_red': 'node-red',
        'escalation-rules': 'escalation',
    }
    active_tab = alias_map.get(active_tab, active_tab)
    valid_tabs = {'general','ai-integration','telegram-groups','ai-knowledge','ai-analytics','templates','users','escalation','node-red'}
    if active_tab not in valid_tabs:
        active_tab = 'general'

    # Data for AI Knowledge Base tab
    knowledge_entries = KnowledgeBase.query.order_by(KnowledgeBase.created_at.desc()).all()

    # Data for AI Analytics tab
    total_analyses = MessageAnalysis.query.count()
    total_auto_responses = AutoResponse.query.count()
    active_sessions = TroubleshootingSession.query.filter_by(status='active').count()

    category_stats_raw = db.session.query(
        MessageAnalysis.category,
        db.func.count(MessageAnalysis.id).label('count')
    ).group_by(MessageAnalysis.category).all()
    
    # Convert Row objects to tuples for template compatibility
    category_stats = [(row[0], row[1]) for row in category_stats_raw] if category_stats_raw else []

    kb_performance_raw = db.session.query(
        KnowledgeBase.title,
        KnowledgeBase.usage_count,
        KnowledgeBase.success_rate
    ).filter(KnowledgeBase.usage_count > 0).order_by(KnowledgeBase.usage_count.desc()).limit(10).all()
    
    # Convert Row objects to dicts for template compatibility
    kb_performance = [
        {
            'title': row[0],
            'usage_count': row[1],
            'success_rate': row[2]
        }
        for row in kb_performance_raw
    ] if kb_performance_raw else []

    recent_responses = db.session.query(
        AutoResponse,
        SupportMessage.message_text,
        KnowledgeBase.title
    ).join(SupportMessage).join(KnowledgeBase).order_by(
        AutoResponse.created_at.desc()
    ).limit(10).all()

    # Fetch users for the Users tab
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Fetch templates for the Templates tab
    templates = ResponseTemplate.query.order_by(ResponseTemplate.category, ResponseTemplate.name).all()
    
    # Fetch escalation rules for the Escalation tab
    escalation_rules = EscalationRule.query.order_by(EscalationRule.priority.desc()).all()
    
    # Fetch telegram groups for the Telegram Groups tab
    telegram_groups = TelegramGroup.query.order_by(TelegramGroup.created_at.desc()).all()
    
    # Fetch Node-RED connection data
    node_red_connection = NodeRedConnection.query.first()
    node_red_widgets = NodeRedWidget.query.all() if node_red_connection else []
    
    # Read current notification groups configuration from .env
    support_group_id = os.getenv('SUPPORT_GROUP_ID', '')
    forward_to_group = os.getenv('FORWARD_SUPPORT_TO_GROUP', 'false').lower() == 'true'
    escalation_group_id = os.getenv('ESCALATION_GROUP_ID', '')
    enable_escalation = os.getenv('ENABLE_ESCALATION_ALERTS', 'true').lower() == 'true'
    tech_team_group_id = os.getenv('TECH_TEAM_GROUP_ID', '')
    enable_tech_notifications = os.getenv('ENABLE_TECH_NOTIFICATIONS', 'false').lower() == 'true'
    
    # Parse Telegram default users for the template
    import json
    telegram_user_ids = []
    if appearance.telegram_default_users:
        try:
            telegram_user_ids = json.loads(appearance.telegram_default_users)
        except:
            telegram_user_ids = []

    return render_template(
        'admin_settings.html',
        appearance=appearance,
        telegram_user_ids=telegram_user_ids,
        form=form,
        ai_config=ai_config,
        active_tab=active_tab,
        knowledge_entries=knowledge_entries,
        total_analyses=total_analyses,
        total_auto_responses=total_auto_responses,
        active_sessions=active_sessions,
        category_stats=category_stats,
        kb_performance=kb_performance,
        recent_responses=recent_responses,
        users=users,
        templates=templates,
        escalation_rules=escalation_rules,
        telegram_groups=telegram_groups,
        node_red_connection=node_red_connection,
        node_red_widgets=node_red_widgets,
        support_group_id=support_group_id,
        forward_to_group=forward_to_group,
        escalation_group_id=escalation_group_id,
        enable_escalation=enable_escalation,
        tech_team_group_id=tech_team_group_id,
        enable_tech_notifications=enable_tech_notifications,
    )

@app.route('/api/ai/chat', methods=['POST'])
@login_required
def api_ai_chat():
    """Proxy chat completion to configured AI provider with system prompt injection."""
    payload = request.get_json(silent=True) or {}

    # Load saved config as defaults
    existing_ai = AIServiceConfig.query.first()
    if not existing_ai:
        return jsonify({'success': False, 'message': 'AI is not configured'}), 400
    if not existing_ai.is_enabled:
        return jsonify({'success': False, 'message': 'AI Auto Support is disabled'}), 400

    provider = (payload.get('provider') or existing_ai.provider or 'openai').strip()
    base_url = (payload.get('base_url') or existing_ai.base_url or '').strip() or None
    api_key = (payload.get('api_key') or existing_ai.api_key or '').strip() or None
    organization = (payload.get('organization') or existing_ai.organization or '').strip() or None
    model = (payload.get('model') or existing_ai.model or '').strip()
    temperature = payload.get('temperature', existing_ai.temperature)
    top_p = payload.get('top_p', existing_ai.top_p)
    max_tokens = payload.get('max_tokens', existing_ai.max_tokens)
    system_prompt = (payload.get('system_prompt') or existing_ai.system_prompt or '').strip() or None
    api_version = payload.get('api_version') or os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

    # Messages: allow OpenAI-style messages or single prompt
    messages = payload.get('messages')
    prompt = payload.get('prompt')
    if not messages and not prompt:
        return jsonify({'success': False, 'message': 'Provide either messages[] or prompt'}), 400

    # Normalize OpenAI-style messages array
    if not messages:
        messages = [{'role': 'user', 'content': str(prompt)}]

    try:
        if provider == 'openai' or (provider == 'custom' and (base_url and 'openai' in base_url)):
            url = (base_url or 'https://api.openai.com/v1').rstrip('/') + '/chat/completions'
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            if organization:
                headers['OpenAI-Organization'] = organization

            # Inject system prompt
            oai_messages = []
            if system_prompt:
                oai_messages.append({'role': 'system', 'content': system_prompt})
            oai_messages.extend(messages)

            body = {
                'model': model or 'gpt-4o-mini',
                'messages': oai_messages,
                'temperature': temperature
            }
            if top_p is not None and top_p != '':
                body['top_p'] = top_p
            if max_tokens is not None and max_tokens != '':
                body['max_tokens'] = max_tokens

            resp = requests.post(url, headers=headers, json=body, timeout=30)
            if resp.status_code >= 400:
                return jsonify({'success': False, 'message': f'OpenAI error: {resp.status_code} {resp.text[:200]}'}), resp.status_code
            data = resp.json()
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({'success': True, 'provider': 'openai', 'text': text, 'raw': data})

        elif provider == 'azure_openai':
            if not base_url:
                return jsonify({'success': False, 'message': 'Base URL required for Azure OpenAI'}), 400
            if not model:
                return jsonify({'success': False, 'message': 'Azure deployment name required as model'}), 400
            url = base_url.rstrip('/') + f'/openai/deployments/{model}/chat/completions?api-version={api_version}'
            headers = {'api-key': api_key or ''}

            az_messages = []
            if system_prompt:
                az_messages.append({'role': 'system', 'content': system_prompt})
            az_messages.extend(messages)

            body = {
                'messages': az_messages,
                'temperature': temperature
            }
            if top_p is not None and top_p != '':
                body['top_p'] = top_p
            if max_tokens is not None and max_tokens != '':
                body['max_tokens'] = max_tokens

            resp = requests.post(url, headers=headers, json=body, timeout=30)
            if resp.status_code >= 400:
                return jsonify({'success': False, 'message': f'Azure OpenAI error: {resp.status_code} {resp.text[:200]}'}), resp.status_code
            data = resp.json()
            # Azure mirrors OpenAI response structure
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({'success': True, 'provider': 'azure_openai', 'text': text, 'raw': data})

        elif provider == 'anthropic':
            url = (base_url or 'https://api.anthropic.com/v1').rstrip('/') + '/messages'
            headers = {
                'x-api-key': api_key or '',
                'anthropic-version': '2023-06-01'
            }
            # Convert OpenAI-style to Anthropic messages
            # Anthropic supports top-level 'system' and 'messages' with roles 'user'/'assistant'
            anthro_messages = []
            for m in messages:
                role = m.get('role', 'user')
                content = m.get('content', '')
                if not content:
                    continue
                if role not in ('user', 'assistant'):
                    # Map unknown roles to user
                    role = 'user'
                anthro_messages.append({'role': role, 'content': content})

            body = {
                'model': model or 'claude-3-haiku-20240307',
                'messages': anthro_messages,
                'max_tokens': max_tokens or 512
            }
            if system_prompt:
                body['system'] = system_prompt
            if temperature is not None and temperature != '':
                body['temperature'] = temperature
            if top_p is not None and top_p != '':
                body['top_p'] = top_p

            resp = requests.post(url, headers=headers, json=body, timeout=30)
            if resp.status_code >= 400:
                return jsonify({'success': False, 'message': f'Anthropic error: {resp.status_code} {resp.text[:200]}'}), resp.status_code
            data = resp.json()
            # Anthropic returns content list
            content_list = data.get('content') or []
            text = ''
            if content_list and isinstance(content_list, list):
                first_item = content_list[0]
                if isinstance(first_item, dict):
                    text = first_item.get('text') or first_item.get('content') or ''
            return jsonify({'success': True, 'provider': 'anthropic', 'text': text, 'raw': data})

        elif provider == 'ollama':
            url = (base_url or 'http://localhost:11434').rstrip('/') + '/api/chat'
            # Ollama accepts messages with optional system role
            ollama_messages = []
            if system_prompt:
                ollama_messages.append({'role': 'system', 'content': system_prompt})
            ollama_messages.extend(messages)

            body = {
                'model': model or 'llama3.1',
                'messages': ollama_messages,
                'stream': False
            }
            # Ollama supports temperature in options
            options = {}
            if temperature is not None and temperature != '':
                options['temperature'] = temperature
            if top_p is not None and top_p != '':
                options['top_p'] = top_p
            if max_tokens is not None and max_tokens != '':
                options['num_predict'] = max_tokens
            if options:
                body['options'] = options

            resp = requests.post(url, json=body, timeout=60)
            if resp.status_code >= 400:
                return jsonify({'success': False, 'message': f'Ollama error: {resp.status_code} {resp.text[:200]}'}), resp.status_code
            data = resp.json()
            text = data.get('message', {}).get('content') or data.get('response') or ''
            return jsonify({'success': True, 'provider': 'ollama', 'text': text, 'raw': data})

        else:
            # Custom: treat as OpenAI-compatible
            if not base_url:
                return jsonify({'success': False, 'message': 'Base URL required for custom provider'}), 400
            url = base_url.rstrip('/') + '/chat/completions'
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'

            cust_messages = []
            if system_prompt:
                cust_messages.append({'role': 'system', 'content': system_prompt})
            cust_messages.extend(messages)

            body = {
                'model': model or 'gpt-4o-mini',
                'messages': cust_messages,
                'temperature': temperature
            }
            if top_p is not None and top_p != '':
                body['top_p'] = top_p
            if max_tokens is not None and max_tokens != '':
                body['max_tokens'] = max_tokens

            resp = requests.post(url, headers=headers, json=body, timeout=30)
            if resp.status_code >= 400:
                return jsonify({'success': False, 'message': f'Custom provider error: {resp.status_code} {resp.text[:200]}'}), resp.status_code
            data = resp.json()
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({'success': True, 'provider': 'custom', 'text': text, 'raw': data})

    except requests.Timeout:
        return jsonify({'success': False, 'message': 'Provider request timed out'}), 504
    except Exception as e:
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'}), 500

@app.route('/ai-knowledge')
@login_required
def ai_knowledge():
    """AI Knowledge Base management (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    # Redirect to Admin Settings tab
    return redirect(url_for('admin_settings', tab='ai-knowledge'))

@app.route('/ai-knowledge/add', methods=['GET', 'POST'])
@login_required
def add_knowledge():
    """Add new AI knowledge base entry"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    form = KnowledgeBaseForm()
    
    if form.validate_on_submit():
        # Validate troubleshooting steps JSON if provided
        troubleshooting_steps = None
        if form.troubleshooting_steps.data:
            try:
                steps = json.loads(form.troubleshooting_steps.data)
                if isinstance(steps, list):
                    troubleshooting_steps = form.troubleshooting_steps.data
                else:
                    flash('Troubleshooting steps must be a JSON array of strings.', 'error')
                    return render_template('add_knowledge.html', form=form)
            except json.JSONDecodeError:
                flash('Invalid JSON format for troubleshooting steps.', 'error')
                return render_template('add_knowledge.html', form=form)
        
        knowledge_entry = KnowledgeBase(
            title=form.title.data,
            question_pattern=form.question_pattern.data,
            solution_text=form.solution_text.data,
            category=form.category.data,
            keywords=form.keywords.data,
            troubleshooting_steps=troubleshooting_steps,
            confidence_threshold=float(form.confidence_threshold.data),
            is_active=form.is_active.data,
            created_by_id=current_user.id
        )
        
        db.session.add(knowledge_entry)
        db.session.commit()
        
        flash('Knowledge base entry added successfully!', 'success')
        return redirect(url_for('ai_knowledge'))
    
    return render_template('add_knowledge.html', form=form)

@app.route('/ai-knowledge/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_knowledge(id):
    """Edit AI knowledge base entry"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    knowledge_entry = KnowledgeBase.query.get_or_404(id)
    form = KnowledgeBaseForm(obj=knowledge_entry)
    
    # Set form data from the knowledge entry
    if request.method == 'GET':
        form.confidence_threshold.data = str(knowledge_entry.confidence_threshold)
    
    if form.validate_on_submit():
        # Validate troubleshooting steps JSON if provided
        troubleshooting_steps = None
        if form.troubleshooting_steps.data:
            try:
                steps = json.loads(form.troubleshooting_steps.data)
                if isinstance(steps, list):
                    troubleshooting_steps = form.troubleshooting_steps.data
                else:
                    flash('Troubleshooting steps must be a JSON array of strings.', 'error')
                    return render_template('edit_knowledge.html', form=form, knowledge_entry=knowledge_entry)
            except json.JSONDecodeError:
                flash('Invalid JSON format for troubleshooting steps.', 'error')
                return render_template('edit_knowledge.html', form=form, knowledge_entry=knowledge_entry)
        
        knowledge_entry.title = form.title.data
        knowledge_entry.question_pattern = form.question_pattern.data
        knowledge_entry.solution_text = form.solution_text.data
        knowledge_entry.category = form.category.data
        knowledge_entry.keywords = form.keywords.data
        knowledge_entry.troubleshooting_steps = troubleshooting_steps
        knowledge_entry.confidence_threshold = float(form.confidence_threshold.data)
        knowledge_entry.is_active = form.is_active.data
        knowledge_entry.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Knowledge base entry updated successfully!', 'success')
        return redirect(url_for('ai_knowledge'))
    
    return render_template('edit_knowledge.html', form=form, knowledge_entry=knowledge_entry)

@app.route('/ai-knowledge/delete/<int:id>', methods=['POST'])
@login_required
def delete_knowledge(id):
    """Delete AI knowledge base entry"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    knowledge_entry = KnowledgeBase.query.get_or_404(id)
    db.session.delete(knowledge_entry)
    db.session.commit()
    
    flash('Knowledge base entry deleted successfully!', 'success')
    return redirect(url_for('ai_knowledge'))

@app.route('/ai-analytics')
@login_required
def ai_analytics():
    """AI Support Analytics dashboard"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    # Redirect to Admin Settings tab
    return redirect(url_for('admin_settings', tab='ai-analytics'))

@app.route('/api/templates/<category>', methods=['GET'])
@login_required
def api_get_templates(category):
    """API endpoint to get templates by category"""
    templates = ResponseTemplate.query.filter_by(category=category, is_active=True).all()
    return jsonify([
        {
            'id': t.id,
            'name': t.name,
            'template_text': t.template_text
        } for t in templates
    ])

@app.route('/api/messages/bulk-action', methods=['POST'])
@login_required
def api_bulk_message_action():
    """API endpoint for bulk message actions (delete, archive, resolve)"""
    try:
        action = request.form.get('action')
        message_ids_json = request.form.get('message_ids')
        
        if not action or not message_ids_json:
            return jsonify({'success': False, 'message': 'Missing action or message IDs'}), 400
        
        # Parse message IDs
        try:
            message_ids = json.loads(message_ids_json)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'message': 'Invalid message IDs format'}), 400
        
        if not message_ids:
            return jsonify({'success': False, 'message': 'No messages selected'}), 400
        
        # Validate action
        if action not in ['delete', 'archive', 'resolve']:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        # Get messages belonging to the user (security check)
        messages = SupportMessage.query.filter(SupportMessage.id.in_(message_ids)).all()
        
        if not messages:
            return jsonify({'success': False, 'message': 'No valid messages found'}), 404
        
        processed_count = 0
        
        # Perform bulk action
        if action == 'delete':
            # Admin-only action for security
            if not current_user.is_admin:
                return jsonify({'success': False, 'message': 'Admin privileges required for delete action'}), 403
            
            for message in messages:
                # Also delete related conversation states
                ConversationState.query.filter_by(user_telegram_id=message.telegram_user_id).delete()
                # Delete message analyses and auto responses
                MessageAnalysis.query.filter_by(message_id=message.id).delete()
                AutoResponse.query.filter_by(message_id=message.id).delete()
                db.session.delete(message)
                processed_count += 1
            
            message_text = f'Successfully deleted {processed_count} message(s)'
            
        elif action == 'archive':
            for message in messages:
                message.status = 'archived'
                message.updated_at = datetime.utcnow()
                processed_count += 1
            
            message_text = f'Successfully archived {processed_count} message(s)'
            
        elif action == 'resolve':
            for message in messages:
                message.status = 'resolved'
                message.updated_at = datetime.utcnow()
                # End any active conversations for resolved messages
                ConversationState.query.filter_by(
                    user_telegram_id=message.telegram_user_id,
                    awaiting_reply=True
                ).update({
                    'awaiting_reply': False,
                    'last_activity': datetime.utcnow()
                })
                processed_count += 1
            
            message_text = f'Successfully marked {processed_count} message(s) as resolved'
        
        # Commit changes
        db.session.commit()
        
        # Log the bulk action
        print(f"Bulk {action} performed by {current_user.username}: {processed_count} messages processed")
        
        return jsonify({
            'success': True,
            'message': message_text,
            'processed_count': processed_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in bulk message action: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }), 500

@app.route('/api/ai/models', methods=['POST'])
@login_required
def api_list_ai_models():
    """Return available AI models for the configured or provided provider/API key."""
    # Admin-only for safety
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin privileges required'}), 403

    payload = request.get_json(silent=True) or {}

    # Use provided values if present, otherwise fall back to saved config
    existing_ai = AIServiceConfig.query.first()
    provider = (payload.get('provider') or (existing_ai.provider if existing_ai else None) or 'openai')
    base_url = payload.get('base_url') or (existing_ai.base_url if existing_ai else None)
    organization = payload.get('organization') or (existing_ai.organization if existing_ai else None)
    api_key = payload.get('api_key') or (existing_ai.api_key if existing_ai else None)
    api_version = payload.get('api_version') or os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

    models = []
    source = None

    try:
        if provider == 'openai' or (provider == 'custom' and (base_url and 'openai' in base_url)):
            url = (base_url or 'https://api.openai.com/v1').rstrip('/') + '/models'
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
            if organization:
                headers['OpenAI-Organization'] = organization
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data_json = resp.json()
                items = data_json.get('data', [])
                for item in items:
                    mid = item.get('id')
                    if mid:
                        models.append({'id': mid, 'label': mid})
                source = 'openai'
            else:
                return jsonify({'success': False, 'message': f'OpenAI error: {resp.status_code} {resp.text[:200]}'}), resp.status_code

        elif provider == 'azure_openai':
            if not base_url:
                return jsonify({'success': False, 'message': 'Base URL required for Azure OpenAI'}), 400
            tried = []
            for ver in [api_version, '2024-02-15-preview', '2023-12-01-preview']:
                if not ver or ver in tried:
                    continue
                tried.append(ver)
                url = base_url.rstrip('/') + f'/openai/deployments?api-version={ver}'
                headers = {'api-key': api_key} if api_key else {}
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data_json = resp.json()
                    items = data_json.get('data') or data_json.get('value') or []
                    for item in items:
                        mid = item.get('model') or item.get('model_name') or item.get('id')
                        if mid:
                            models.append({'id': mid, 'label': mid})
                    source = f'azure_openai:{ver}'
                    break
            if not models:
                return jsonify({'success': False, 'message': 'Azure OpenAI error listing deployments'}), 502

        elif provider == 'anthropic':
            url = (base_url or 'https://api.anthropic.com/v1').rstrip('/') + '/models'
            headers = {
                'x-api-key': api_key or '',
                'anthropic-version': '2023-06-01'
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data_json = resp.json()
                items = data_json.get('data', [])
                for item in items:
                    mid = item.get('id')
                    if mid:
                        models.append({'id': mid, 'label': mid})
                source = 'anthropic'
            else:
                # Fallback to a curated list if API call fails
                curated = [
                    'claude-3-5-sonnet-20240620',
                    'claude-3-5-haiku-20241022',
                    'claude-3-opus-20240229',
                    'claude-3-sonnet-20240229',
                    'claude-3-haiku-20240307'
                ]
                models = [{'id': m, 'label': m} for m in curated]
                source = 'anthropic:curated'

        elif provider == 'ollama':
            url = (base_url or 'http://localhost:11434').rstrip('/') + '/api/tags'
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data_json = resp.json()
                items = data_json.get('models', [])
                for item in items:
                    mid = item.get('name') or item.get('model')
                    if mid:
                        models.append({'id': mid, 'label': mid})
                source = 'ollama'
            else:
                return jsonify({'success': False, 'message': f'Ollama error: {resp.status_code} {resp.text[:200]}'}), resp.status_code

        else:
            # Custom: try OpenAI-compatible /models
            if not base_url:
                return jsonify({'success': False, 'message': 'Base URL required for custom provider'}), 400
            url = base_url.rstrip('/') + '/models'
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data_json = resp.json()
                items = data_json.get('data') or data_json
                if isinstance(items, dict):
                    items = items.get('models') or []
                for item in items:
                    if isinstance(item, str):
                        mid = item
                    else:
                        mid = item.get('id') or item.get('name')
                    if mid:
                        models.append({'id': mid, 'label': mid})
                source = 'custom'
            else:
                return jsonify({'success': False, 'message': f'Custom provider error: {resp.status_code} {resp.text[:200]}'}), resp.status_code

        # Deduplicate and sort
        uniq = {}
        for m in models:
            uniq[m['id']] = m
        models = sorted(uniq.values(), key=lambda x: x['id'])

        return jsonify({'success': True, 'provider': provider, 'models': models, 'source': source}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching models: {str(e)}'}), 500

# API Routes for bot integration
@app.route('/api/support_message', methods=['POST'])
def api_create_support_message():
    """API endpoint for bot to create support messages"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['telegram_user_id', 'telegram_first_name', 'chat_id', 'message_text']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if this is a user reply to an existing conversation
        is_reply = data.get('is_followup', False) or data.get('message_type') == 'reply'
        conversation_id = data.get('conversation_id')
        
        if is_reply:
            # This is a user reply - create a response record instead of a new message
            if conversation_id:
                print(f"DEBUG: Processing user reply with conversation_id {conversation_id}")
            else:
                print("DEBUG: Processing user reply without conversation_id; using latest case for user")

            # Resolve the original message robustly
            original_message = None
            if conversation_id:
                # 1) Interpret as SupportMessage ID first
                try_msg = SupportMessage.query.get(conversation_id)
                if try_msg and str(try_msg.telegram_user_id) == str(data['telegram_user_id']):
                    original_message = try_msg
                else:
                    # 2) Interpret as ConversationState ID
                    try:
                        conv = ConversationState.query.get(conversation_id)
                    except Exception:
                        conv = None
                    if conv and conv.last_message_id:
                        original_message = SupportMessage.query.get(conv.last_message_id)

            # 3) Try active conversation for this user
            if not original_message:
                conv = ConversationState.query.filter_by(user_telegram_id=str(data['telegram_user_id']), is_active=True).first()
                if conv and conv.last_message_id:
                    original_message = SupportMessage.query.get(conv.last_message_id)

            # 4) Most recent message with a technician response for this user
            if not original_message:
                original_message = db.session.query(SupportMessage).join(
                    SupportResponse, SupportMessage.id == SupportResponse.message_id
                ).filter(
                    SupportMessage.telegram_user_id == str(data['telegram_user_id']),
                    SupportResponse.is_user_reply == False
                ).order_by(SupportResponse.created_at.desc()).first()

            # 5) Absolute fallback: most recent message for this user
            if not original_message:
                original_message = SupportMessage.query.filter_by(
                    telegram_user_id=str(data['telegram_user_id'])
                ).order_by(SupportMessage.created_at.desc()).first()
            
            if original_message:
                # Create a response record to track the user's reply
                user_reply = SupportResponse(
                    message_id=original_message.id,
                    user_id=None,
                    response_text=data['message_text'],
                    is_user_reply=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(user_reply)
                
                # Update original message status and timestamp
                original_message.status = 'pending_response'
                original_message.updated_at = datetime.utcnow()
                
                db.session.commit()
                
                # Attempt automated reply (AI first; else notify human on-call)
                try:
                    notify_on_call_person(original_message, incoming_text=data['message_text'])
                except Exception as e:
                    logger.error(f"Auto-reply attempt failed: {e}")
                
                print(f"DEBUG: User reply saved as response {user_reply.id} to message {original_message.id}")
                return jsonify({
                    'message_id': original_message.id,
                    'response_id': user_reply.id,
                    'status': 'reply_saved',
                    'conversation_id': conversation_id
                }), 201
            else:
                print(f"DEBUG: Could not find original message for user {data['telegram_user_id']}")
        
        # Standard new support message handling
        message = SupportMessage(
            telegram_user_id=data['telegram_user_id'],
            telegram_username=data.get('telegram_username'),
            telegram_first_name=data['telegram_first_name'],
            telegram_last_name=data.get('telegram_last_name'),
            chat_id=data['chat_id'],
            chat_title=data.get('chat_title'),
            message_text=data['message_text'],
            priority=data.get('priority', 'normal')
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Notify on-call person only for new support messages (not replies)
        if not is_reply:
            notify_on_call_person(message)
        
        return jsonify({'message_id': message.id, 'status': 'created'}), 201
    except Exception as e:
        logger.error(f"Error creating support message: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/current_oncall', methods=['GET'])
def api_current_oncall():
    """API endpoint to get current on-call person and stats"""
    try:
        current_on_call = get_current_on_call()
        
        # Get statistics
        total_messages = SupportMessage.query.count()
        open_messages = SupportMessage.query.filter_by(status='open').count()
        in_progress_messages = SupportMessage.query.filter_by(status='in_progress').count()
        resolved_today = SupportMessage.query.filter(
            SupportMessage.status == 'resolved',
            SupportMessage.resolved_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        response_data = {
            'on_call_user': {
                'first_name': current_on_call.user.first_name,
                'last_name': current_on_call.user.last_name,
                'email': current_on_call.user.email
            } if current_on_call else None,
            'total_messages': total_messages,
            'open_messages': open_messages,
            'in_progress_messages': in_progress_messages,
            'resolved_today': resolved_today
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        logger.error(f"Error getting current on-call: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/message/<int:message_id>/status', methods=['GET'])
def api_message_status(message_id):
    """API endpoint to get message status"""
    try:
        message = SupportMessage.query.get_or_404(message_id)
        return jsonify({
            'status': message.status,
            'assigned_to': message.assigned_to.username if message.assigned_to else None,
            'updated_at': message.updated_at.isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error getting message status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/escalate/<int:message_id>', methods=['POST'])
def api_escalate_message(message_id):
    """API endpoint to escalate a message"""
    try:
        data = request.get_json()
        escalation_level = data.get('escalation_level', 2)
        
        message = SupportMessage.query.get_or_404(message_id)
        
        # Find next backup on-call person
        backup_on_call = get_backup_on_call(escalation_level)
        
        if backup_on_call and backup_on_call.user.telegram_user_id:
            # Safety: avoid notifying the requester
            if message.telegram_user_id and str(backup_on_call.user.telegram_user_id) == str(message.telegram_user_id):
                return jsonify({'error': 'Backup on-call is the requester; not notifying'}), 400
            # Create notification record
            notification = Notification(
                message_id=message_id,
                user_id=backup_on_call.user.id,
                notification_type='telegram',
                escalation_level=escalation_level
            )
            db.session.add(notification)
            db.session.commit()
            
            # Send Telegram notification to backup
            send_telegram_notification(backup_on_call.user, message)
            
            return jsonify({'status': 'escalated', 'escalation_level': escalation_level}), 200
        else:
            return jsonify({'error': 'No backup on-call person available'}), 404
            
    except Exception as e:
        logger.error(f"Error escalating message: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Context processors
@app.context_processor
def inject_appearance_settings():
    """Make appearance settings available in all templates"""
    appearance = AppearanceSettings.query.first()
    if not appearance:
        appearance = AppearanceSettings()
    return dict(appearance_settings=appearance)

# Helper functions
def get_current_on_call():
    """Get the current on-call person based on schedule"""
    now = datetime.now()
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_time = now.time()
    
    # Find primary on-call person for current time
    schedule = ScheduleSlot.query.filter_by(
        day_of_week=current_day,
        is_primary=True,
        is_active=True
    ).filter(
        ScheduleSlot.start_time <= current_time,
        ScheduleSlot.end_time >= current_time
    ).first()
    
    return schedule if schedule else None

def get_backup_on_call(escalation_level=2):
    """Get backup on-call person for escalation"""
    now = datetime.now()
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_time = now.time()
    
    # Find backup on-call persons for current time
    backup_schedules = ScheduleSlot.query.filter_by(
        day_of_week=current_day,
        is_primary=False,  # Backup personnel
        is_active=True
    ).filter(
        ScheduleSlot.start_time <= current_time,
        ScheduleSlot.end_time >= current_time
    ).all()
    
    # Return the backup person based on escalation level
    if backup_schedules and len(backup_schedules) >= (escalation_level - 1):
        return backup_schedules[escalation_level - 2]  # -2 because escalation_level starts at 2
    
    return None

def notify_on_call_person(message, incoming_text=None):
    """Attempt AI auto-response first; if none, notify current human on-call."""
    ai_username = os.getenv('AI_BOT_USERNAME', 'ai-bot')

    # 1) Try AI regardless of schedule
    try:
        analysis = ai_support.analyze_text_for_message(message, incoming_text) if incoming_text else ai_support.analyze_message(message)
        auto_response = ai_support.generate_auto_response(message, analysis)

        if auto_response:
            # Record AI response as a technician response from AI user (if exists)
            ai_user = User.query.filter_by(username=ai_username).first()
            tech_response = SupportResponse(
                message_id=message.id,
                user_id=(ai_user.id if ai_user else None),
                response_text=auto_response.response_text,
                is_user_reply=False
            )
            if ai_user:
                message.assigned_to_id = ai_user.id
            message.status = 'in_progress'
            message.updated_at = datetime.utcnow()

            db.session.add(tech_response)
            db.session.commit()

            # Update conversation state so the next user message is treated as a reply
            try:
                conversation_manager.update_conversation_response(
                    user_telegram_id=message.telegram_user_id,
                    response_id=tech_response.id
                )
            except Exception as e:
                logger.error(f"Failed to update conversation after AI response: {e}")

            # Send AI response to the user
            send_telegram_response(message, auto_response.response_text, responder_name='AI Assistant')
            return
    except Exception as e:
        logger.error(f"AI auto-reply failed: {e}")

    # 1b) Default acknowledgement if AI couldn't generate a confident answer (with rate limiting)
    try:
        # Load settings
        cfg_ack_text = get_system_config_value('ai_ack_text', "Thanks for reaching out! I've notified our on-call technician and someone will assist you shortly. This is an automated acknowledgement.")
        try:
            cfg_ack_interval = int(str(get_system_config_value('ai_ack_interval_minutes', '10')).strip() or '10')
        except Exception:
            cfg_ack_interval = 10

        # Rate-limit per user conversation
        should_send_ack = True
        if cfg_ack_interval > 0:
            conv = ConversationState.query.filter_by(user_telegram_id=message.telegram_user_id).first()
            if conv and conv.conversation_context:
                try:
                    ctx = json.loads(conv.conversation_context)
                except Exception:
                    ctx = {}
            else:
                ctx = {}

            last_ack_at = ctx.get('last_ack_at')
            if last_ack_at:
                try:
                    last_dt = datetime.fromisoformat(last_ack_at)
                    if datetime.utcnow() - last_dt < timedelta(minutes=cfg_ack_interval):
                        should_send_ack = False
                except Exception:
                    pass

        if should_send_ack:
            ai_user = User.query.filter_by(username=ai_username).first()
            ack_response = SupportResponse(
                message_id=message.id,
                user_id=(ai_user.id if ai_user else None),
                response_text=cfg_ack_text,
                is_user_reply=False
            )
            db.session.add(ack_response)
            db.session.commit()
            send_telegram_response(message, cfg_ack_text, responder_name='AI Assistant')

            # Update conversation state last_ack_at
            try:
                conv = ConversationState.query.filter_by(user_telegram_id=message.telegram_user_id).first()
                if not conv:
                    conv = ConversationState(user_telegram_id=message.telegram_user_id, username=message.telegram_username or None, last_message_id=message.id, awaiting_reply=False)
                    db.session.add(conv)
                    db.session.flush()
                ctx = {}
                if conv.conversation_context:
                    try:
                        ctx = json.loads(conv.conversation_context)
                    except Exception:
                        ctx = {}
                ctx['last_ack_at'] = datetime.utcnow().isoformat()
                conv.conversation_context = json.dumps(ctx)
                conv.last_message_id = message.id
                conv.last_activity = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to update conversation ack state: {e}")
        else:
            logger.info("Skipping AI acknowledgement due to rate limit window")
    except Exception as e:
        logger.error(f"Failed to process default AI acknowledgement: {e}")

    # 2) Fall back to notifying the current human on-call
    on_call_schedule = get_current_on_call()
    if not on_call_schedule:
        return

    oncall_user = on_call_schedule.user
    requester_tid = str(message.telegram_user_id) if message.telegram_user_id is not None else None

    # Choose a recipient distinct from the requester to avoid echoing staff notifications to the user
    notify_recipient = None
    if oncall_user and oncall_user.telegram_user_id and str(oncall_user.telegram_user_id) != requester_tid:
        notify_recipient = oncall_user
    else:
        # Try backup on-call
        try:
            backup_schedule = get_backup_on_call(escalation_level=2)
            if backup_schedule and backup_schedule.user and backup_schedule.user.telegram_user_id and str(backup_schedule.user.telegram_user_id) != requester_tid:
                notify_recipient = backup_schedule.user
        except Exception as e:
            logger.error(f"Error selecting backup on-call: {e}")

    if notify_recipient:
        notification = Notification(
            message_id=message.id,
            user_id=notify_recipient.id,
            notification_type='telegram',
            escalation_level=1
        )
        db.session.add(notification)
        db.session.commit()
        send_telegram_notification(notify_recipient, message)
    else:
        logger.info("No suitable on-call recipient distinct from requester; skipping Telegram on-call notification for this case")

def send_telegram_notification(user, message):
    """Send Telegram notification to on-call person"""
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token or not user.telegram_user_id:
        return False
    
    # Safety: never send staff notifications to the requester themselves
    try:
        if message.telegram_user_id and str(user.telegram_user_id) == str(message.telegram_user_id):
            logger.warning("Skipping staff notification: recipient is the requester")
            return False
    except Exception:
        pass
    
    notification_text = (
        f"🚨 NEW SUPPORT REQUEST\n\n"
        f"From: {message.telegram_first_name} {message.telegram_last_name or ''}\n"
        f"Username: @{message.telegram_username or 'N/A'}\n"
        f"Message: {message.message_text}\n\n"
        f"Please respond via the web dashboard: {request.host_url}message/{message.id}"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': user.telegram_user_id,
        'text': notification_text,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=data)
        return response.status_code == 200
    except:
        return False

def send_telegram_response(message, response_text, responder_name=None):
    """Send response back to user via Telegram"""
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        return False
    
    # Build destination priority list:
    # 1) Private group (if exists)
    # 2) Direct message to user
    # 3) Original chat where message originated
    destinations = []
    if message.private_group_id and message.private_group_created:
        destinations.append({
            'chat_id': message.private_group_id,
            'context': f"Private Support: {message.private_group_title or 'Support Chat'}"
        })
    # DM to user
    if message.telegram_user_id:
        destinations.append({
            'chat_id': message.telegram_user_id,
            'context': 'Direct Message'
        })
    # Original chat fallback
    if message.chat_id:
        destinations.append({
            'chat_id': message.chat_id,
            'context': 'Original Chat'
        })
    
    # Determine responder display name
    if responder_name:
        responder_display = responder_name
    else:
        try:
            responder_display = f"{current_user.first_name} {current_user.last_name}" if current_user.is_authenticated else "Support Technician"
        except Exception:
            responder_display = "Support Technician"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    last_error = None
    for dest in destinations:
        chat_id = dest['chat_id']
        chat_context = dest['context']
        print(f"DEBUG: Attempting to send response for message #{message.id} to {chat_context} (chat_id={chat_id})")

        response_message = (
            f"📞 **SUPPORT RESPONSE**\n\n"
            f"{response_text}\n\n"
            f"👤 **Responded by:** {responder_display}\n"
            f"📍 **Context:** {chat_context}"
        )
        data = {
            'chat_id': chat_id,
            'text': response_message,
            'parse_mode': 'Markdown'
        }
        try:
            resp = requests.post(url, json=data)
            if resp.status_code == 200:
                print(f"DEBUG: Response sent successfully to {chat_context} for message #{message.id}")
                return True
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(f"Telegram send failed to {chat_context} (chat_id={chat_id}) for message #{message.id}: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Exception sending Telegram message to {chat_context} (chat_id={chat_id}) for message #{message.id}: {e}")

    logger.error(f"All Telegram send attempts failed for message #{message.id}. Last error: {last_error}")
    return False

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(debug=True, host='0.0.0.0', port=5001)
