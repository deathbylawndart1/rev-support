from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import bcrypt

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Tech team member model"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    telegram_user_id = db.Column(db.String(50), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    schedule_slots = db.relationship('ScheduleSlot', backref='user', lazy=True)
    responses = db.relationship('SupportResponse', backref='user', lazy=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Check if password matches hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def __repr__(self):
        return f'<User {self.username}>'

class SupportMessage(db.Model):
    """Support messages from Telegram bot"""
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.String(50), nullable=False)
    telegram_username = db.Column(db.String(100), nullable=True)
    telegram_first_name = db.Column(db.String(100), nullable=False)
    telegram_last_name = db.Column(db.String(100), nullable=True)
    chat_id = db.Column(db.String(50), nullable=False)
    chat_title = db.Column(db.String(200), nullable=True)
    message_text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, escalated, archived
    priority = db.Column(db.String(10), default='normal')  # low, normal, high, urgent
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    private_group_id = db.Column(db.String(50), nullable=True)  # Telegram private group chat ID
    private_group_title = db.Column(db.String(200), nullable=True)  # Private group title
    private_group_invite_link = db.Column(db.String(500), nullable=True)  # Private group invite link
    private_group_created = db.Column(db.Boolean, default=False)  # Whether private group was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    assigned_to = db.relationship('User', backref='assigned_messages')
    responses = db.relationship('SupportResponse', backref='message', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='message', lazy=True, cascade='all, delete-orphan')
    active_conversations = db.relationship('ConversationState', backref='last_message', lazy=True, foreign_keys='ConversationState.last_message_id')
    
    def __repr__(self):
        return f'<SupportMessage {self.id}: {self.telegram_first_name}>'

class SupportResponse(db.Model):
    """Responses to support messages"""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('support_message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for user replies
    response_text = db.Column(db.Text, nullable=False)
    is_user_reply = db.Column(db.Boolean, default=False)  # True if this is a user reply, False if technician response
    sent_to_telegram = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SupportResponse {self.id}>'

class ScheduleSlot(db.Model):
    """On-call schedule slots"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_primary = db.Column(db.Boolean, default=True)  # Primary or backup
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ScheduleSlot {self.user.username}: {self.day_of_week} {self.start_time}-{self.end_time}>'

class Notification(db.Model):
    """Notification tracking for escalation"""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('support_message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_type = db.Column(db.String(20), nullable=False)  # telegram, email
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    escalation_level = db.Column(db.Integer, default=1)  # 1=primary, 2=backup, etc.
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.notification_type} to {self.user.username}>'

class TelegramGroup(db.Model):
    """Telegram group configuration for notifications and routing"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    telegram_group_id = db.Column(db.String(50), unique=True, nullable=False)  # Telegram group chat ID
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TelegramGroup {self.name}:{self.telegram_group_id}>'

class ResponseTemplate(db.Model):
    """Response templates for quick replies"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'greeting', 'troubleshooting', 'escalation', 'closing'
    template_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by = db.relationship('User', backref='response_templates')
    
    def __repr__(self):
        return f'<ResponseTemplate {self.name}>'

class EscalationRule(db.Model):
    """Escalation rules and timers"""
    id = db.Column(db.Integer, primary_key=True)
    priority = db.Column(db.String(10), nullable=False)  # 'low', 'normal', 'high', 'critical'
    escalation_timeout = db.Column(db.Integer, nullable=False)  # seconds
    max_escalation_level = db.Column(db.Integer, default=3)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EscalationRule {self.priority}: {self.escalation_timeout}s>'

class AppearanceSettings(db.Model):
    """Dashboard appearance customization settings"""
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), default='Support System')
    color_scheme = db.Column(db.String(20), default='blue')  # blue, green, purple, red, dark, custom
    primary_color = db.Column(db.String(7), default='#0d6efd')  # Hex color
    secondary_color = db.Column(db.String(7), default='#6c757d')
    accent_color = db.Column(db.String(7), default='#198754')
    logo_filename = db.Column(db.String(255))  # Uploaded logo file
    logo_max_height = db.Column(db.Integer, default=120)  # Logo max height in pixels
    logo_max_width = db.Column(db.Integer, default=300)  # Logo max width in pixels
    favicon_filename = db.Column(db.String(255))  # Uploaded favicon file
    custom_css = db.Column(db.Text)  # Custom CSS overrides
    telegram_default_users = db.Column(db.Text)  # JSON list of Telegram user IDs to add to new groups
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AppearanceSettings {self.company_name}>'

class AIServiceConfig(db.Model):
    """Configuration for external AI service providers"""
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), default='openai')  # openai, azure_openai, ollama, anthropic, custom
    base_url = db.Column(db.String(255), nullable=True)  # Optional override or custom endpoint
    api_key = db.Column(db.String(255), nullable=True)
    model = db.Column(db.String(100), nullable=True)  # e.g., gpt-4o, gpt-4o-mini, etc.
    temperature = db.Column(db.Float, default=0.7)
    top_p = db.Column(db.Float, nullable=True)
    max_tokens = db.Column(db.Integer, nullable=True)
    organization = db.Column(db.String(100), nullable=True)
    system_prompt = db.Column(db.Text, nullable=True)
    is_enabled = db.Column(db.Boolean, default=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AIServiceConfig {self.provider}:{self.model}>'

class KnowledgeBase(db.Model):
    """AI Knowledge Base for automated support responses"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    question_pattern = db.Column(db.Text, nullable=False)  # Pattern or keywords to match
    solution_text = db.Column(db.Text, nullable=False)  # The solution/response
    category = db.Column(db.String(50), nullable=False)  # e.g., 'password_reset', 'login_issue'
    keywords = db.Column(db.Text)  # Comma-separated keywords for matching
    troubleshooting_steps = db.Column(db.Text)  # JSON string of step-by-step guidance
    confidence_threshold = db.Column(db.Float, default=0.7)  # Minimum confidence to auto-respond
    usage_count = db.Column(db.Integer, default=0)  # How many times this was used
    success_rate = db.Column(db.Float, default=0.0)  # Success rate based on user feedback
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    created_by = db.relationship('User')
    
    def __repr__(self):
        return f'<KnowledgeBase {self.title}>'

class MessageAnalysis(db.Model):
    """Analysis of support messages for AI processing"""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('support_message.id'), nullable=False)
    processed_question = db.Column(db.Text, nullable=False)  # Cleaned/processed version
    extracted_keywords = db.Column(db.Text)  # Comma-separated keywords
    category = db.Column(db.String(50))  # Detected category
    sentiment = db.Column(db.String(20))  # positive, negative, neutral
    urgency_score = db.Column(db.Float, default=0.5)  # 0-1 urgency rating
    similarity_vector = db.Column(db.Text)  # JSON string for ML similarity matching
    matched_knowledge_id = db.Column(db.Integer, db.ForeignKey('knowledge_base.id'))
    confidence_score = db.Column(db.Float, default=0.0)  # Confidence in the match
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    message = db.relationship('SupportMessage', backref='analysis')
    matched_knowledge = db.relationship('KnowledgeBase', backref='matched_messages')
    
    def __repr__(self):
        return f'<MessageAnalysis {self.message_id}>'

class AutoResponse(db.Model):
    """Log of automated AI responses"""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('support_message.id'), nullable=False)
    knowledge_base_id = db.Column(db.Integer, db.ForeignKey('knowledge_base.id'), nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    was_helpful = db.Column(db.Boolean)  # User feedback (thumbs up/down)
    human_reviewed = db.Column(db.Boolean, default=False)
    escalated_to_human = db.Column(db.Boolean, default=False)
    response_time_seconds = db.Column(db.Float)  # Time taken to generate response
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    message = db.relationship('SupportMessage', backref='auto_responses')
    knowledge_base = db.relationship('KnowledgeBase', backref='auto_responses')
    
    def __repr__(self):
        return f'<AutoResponse {self.message_id}>'

class TroubleshootingSession(db.Model):
    """Interactive troubleshooting sessions with users"""
    id = db.Column(db.Integer, primary_key=True)
    user_telegram_id = db.Column(db.String(50), nullable=False)
    knowledge_base_id = db.Column(db.Integer, db.ForeignKey('knowledge_base.id'), nullable=False)
    session_token = db.Column(db.String(100), unique=True, nullable=False)  # Unique session identifier
    current_step = db.Column(db.Integer, default=0)  # Current step in troubleshooting
    total_steps = db.Column(db.Integer, default=0)  # Total steps in the process
    session_data = db.Column(db.Text)  # JSON string storing session state
    status = db.Column(db.String(20), default='active')  # active, completed, abandoned
    user_responses = db.Column(db.Text)  # JSON array of user responses to each step
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    knowledge_base = db.relationship('KnowledgeBase', backref='troubleshooting_sessions')
    
    def __repr__(self):
        return f'<TroubleshootingSession {self.session_token}>'

class ConversationState(db.Model):
    """Track active conversations with users for reply detection"""
    id = db.Column(db.Integer, primary_key=True)
    user_telegram_id = db.Column(db.String(50), nullable=False, unique=True)
    username = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_message_id = db.Column(db.Integer, db.ForeignKey('support_message.id'))
    last_response_id = db.Column(db.Integer, db.ForeignKey('support_response.id'))
    conversation_context = db.Column(db.Text)  # JSON string storing conversation context
    awaiting_reply = db.Column(db.Boolean, default=False)  # Whether we're expecting a user reply
    conversation_topic = db.Column(db.String(100))  # Current topic/category
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # When conversation expires (inactive timeout)
    
    def __repr__(self):
        return f'<ConversationState {self.user_telegram_id}>'
    
    def is_expired(self):
        """Check if conversation has expired"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def update_activity(self):
        """Update last activity and extend expiration"""
        from datetime import timedelta
        self.last_activity = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(hours=2)  # 2 hour conversation timeout

class SystemConfig(db.Model):
    """System configuration settings"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemConfig {self.key}: {self.value}>'

# Node-RED Integration Models
class NodeRedConnection(db.Model):
    """Node-RED server connection configuration"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Connection name
    host = db.Column(db.String(255), nullable=False)  # Node-RED server host
    port = db.Column(db.Integer, default=1880)  # Node-RED server port
    username = db.Column(db.String(100), nullable=True)  # Optional authentication
    password = db.Column(db.String(255), nullable=True)  # Optional authentication
    api_key = db.Column(db.String(255), nullable=True)  # Optional API key
    vpn_connection_id = db.Column(db.Integer, db.ForeignKey('vpn_connection.id'), nullable=True)  # Optional VPN
    auto_connect_vpn = db.Column(db.Boolean, default=True)  # Auto-connect VPN before Node-RED
    is_active = db.Column(db.Boolean, default=True)
    is_connected = db.Column(db.Boolean, default=False)  # Connection status
    last_connected = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    widgets = db.relationship('NodeRedWidget', backref='connection', cascade='all, delete-orphan')
    
    @property
    def base_url(self):
        return f"http://{self.host}:{self.port}"
    
    def __repr__(self):
        return f'<NodeRedConnection {self.name}: {self.base_url}>'

class NodeRedWidget(db.Model):
    """Node-RED dashboard widgets configuration"""
    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey('node_red_connection.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Widget display name
    widget_type = db.Column(db.String(50), nullable=False)  # gauge, chart, text, switch, etc.
    endpoint = db.Column(db.String(255), nullable=False)  # Node-RED endpoint/topic
    refresh_interval = db.Column(db.Integer, default=5)  # Seconds between updates
    position_x = db.Column(db.Integer, default=0)  # Grid position X
    position_y = db.Column(db.Integer, default=0)  # Grid position Y
    width = db.Column(db.Integer, default=2)  # Grid width
    height = db.Column(db.Integer, default=2)  # Grid height
    config = db.Column(db.JSON, nullable=True)  # Widget-specific configuration
    is_active = db.Column(db.Boolean, default=True)
    last_value = db.Column(db.Text, nullable=True)  # Last received value
    last_updated = db.Column(db.DateTime, nullable=True)  # Last data update
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<NodeRedWidget {self.name}: {self.widget_type}>'

# VPN Integration Models
class VpnConnection(db.Model):
    """VPN connection configuration for accessing remote Node-RED devices"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # VPN connection name
    vpn_type = db.Column(db.String(20), nullable=False)  # openvpn, wireguard, etc.
    config_file_path = db.Column(db.String(500), nullable=True)  # Path to VPN config file
    server_host = db.Column(db.String(255), nullable=True)  # VPN server host
    server_port = db.Column(db.Integer, nullable=True)  # VPN server port
    username = db.Column(db.String(100), nullable=True)  # VPN username
    password = db.Column(db.String(255), nullable=True)  # VPN password (encrypted)
    private_key_path = db.Column(db.String(500), nullable=True)  # Private key path
    certificate_path = db.Column(db.String(500), nullable=True)  # Certificate path
    ca_cert_path = db.Column(db.String(500), nullable=True)  # CA certificate path
    additional_config = db.Column(db.JSON, nullable=True)  # Additional VPN-specific config
    is_active = db.Column(db.Boolean, default=True)
    is_connected = db.Column(db.Boolean, default=False)  # Current connection status
    last_connected = db.Column(db.DateTime, nullable=True)
    connection_logs = db.Column(db.Text, nullable=True)  # Connection attempt logs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    node_red_connections = db.relationship('NodeRedConnection', backref='vpn_connection', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<VpnConnection {self.name}: {self.vpn_type}>'

# Update NodeRedConnection model to include VPN relationship
# Add foreign key to link NodeRedConnection to VPN
class NodeRedConnectionVpn(db.Model):
    """Junction table for NodeRED connections that require VPN"""
    __tablename__ = 'node_red_connection_vpn'
    id = db.Column(db.Integer, primary_key=True)
    node_red_connection_id = db.Column(db.Integer, db.ForeignKey('node_red_connection.id'), nullable=False)
    vpn_connection_id = db.Column(db.Integer, db.ForeignKey('vpn_connection.id'), nullable=False)
    auto_connect_vpn = db.Column(db.Boolean, default=True)  # Auto-connect VPN before Node-RED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<NodeRedConnectionVpn NodeRED:{self.node_red_connection_id} VPN:{self.vpn_connection_id}>'

# Unit database model to manage field units with status tracking
class Unit(db.Model):
    """Model for field units"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    device_name = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    last_online = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='offline')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Unit {self.name}>'
    
    def get_last_online_display(self):
        """Get formatted last online time"""
        if not self.last_online:
            return 'Never'
        
        now = datetime.utcnow()
        diff = now - self.last_online
        
        if diff.total_seconds() < 300:  # 5 minutes
            return 'Now'
        elif diff.days >= 30:
            return f'{diff.days // 30} month{"s" if diff.days // 30 != 1 else ""} ago'
        elif diff.days >= 1:
            return f'{diff.days} day{"s" if diff.days != 1 else ""} ago'
        elif diff.total_seconds() >= 3600:
            hours = int(diff.total_seconds() // 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        else:
            minutes = int(diff.total_seconds() // 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    
    def get_status_class(self):
        """Get CSS class for status badge"""
        if self.status == 'online':
            return 'bg-success'
        elif self.status == 'offline':
            return 'bg-secondary'
        elif self.status == 'warning':
            return 'bg-warning'
        else:
            return 'bg-danger'
