# 🚀 Advanced Telegram Support System with Web Dashboard

A comprehensive support ticket system that combines a Telegram bot with a full-featured web dashboard, on-call scheduling, and intelligent escalation management.

## ✨ Features

### 🤖 Enhanced Telegram Bot
- **Smart Support Requests**: Users type `@support` followed by their message
- **Automatic On-Call Notification**: Instantly notifies the current on-call tech
- **Intelligent Escalation**: Auto-escalates to backup techs if no response within 15 minutes
- **Real-time Status**: `/status` command shows system health and current on-call person
- **Web Integration**: All messages are logged in the web dashboard

### 🌐 Web Dashboard
- **Tech Team Authentication**: Secure login system for tech team members
- **Message Management**: View, respond to, and track all support requests
- **Real-time Updates**: Dashboard refreshes automatically for new messages
- **Response Tracking**: See which messages have been sent via Telegram
- **Priority Management**: Set and manage message priorities
- **Assignment System**: Assign messages to specific team members

### 📅 On-Call Scheduling System
- **Weekly Schedule Management**: Admins can set up recurring weekly schedules
- **Primary/Backup System**: Define primary and backup on-call personnel
- **Time-based Routing**: Automatically determines who's on-call based on current time
- **Escalation Chain**: Smart escalation through backup team members
- **Schedule Visualization**: Clear weekly overview of on-call assignments

### 🔔 Intelligent Escalation
- **Automatic Escalation**: No response in 15 minutes triggers escalation
- **Multi-level Escalation**: Continues through backup team members
- **Escalation Tracking**: Monitors and logs all escalation attempts
- **Timeout Configuration**: Customizable escalation timeouts
- **Status Monitoring**: Automatically stops escalation when message is handled

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │  Web Dashboard  │    │   Database      │
│                 │    │                 │    │                 │
│ • Message       │◄──►│ • Authentication│◄──►│ • Users         │
│   Processing    │    │ • Message Mgmt  │    │ • Messages      │
│ • Escalation    │    │ • Scheduling    │    │ • Schedules     │
│ • Notifications │    │ • User Mgmt     │    │ • Responses     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to project
cd /home/ryan/CascadeProjects/windsurf-project

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r web_requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
BOT_TOKEN=your_bot_token_from_botfather
SUPPORT_GROUP_ID=your_support_group_chat_id
WEB_DASHBOARD_URL=http://localhost:5000
SECRET_KEY=your-secret-key-change-this
ESCALATION_TIMEOUT=900
```

### 3. Start the Web Dashboard

```bash
# Start the Flask web application
python app.py
```

The web dashboard will be available at `http://localhost:5000`

**Default Admin Login:**
- Username: `admin`
- Password: `admin123`

### 4. Start the Telegram Bot

```bash
# In a new terminal, activate venv and start bot
source venv/bin/activate
python bot.py
```

## 📋 Usage Guide

### For End Users (Telegram)

1. **Send Support Request:**
   ```
   @support I need help with my account
   ```

2. **Check System Status:**
   ```
   /status
   ```

3. **Get Help:**
   ```
   /help
   ```

### For Tech Team (Web Dashboard)

1. **Login**: Visit `http://localhost:5000` and login with your credentials

2. **View Messages**: Navigate to Messages to see all support requests

3. **Respond to Messages**: Click on a message to view details and respond

4. **Manage Schedule** (Admin only): Set up on-call schedules in the Schedule section

5. **Manage Users** (Admin only): Add team members in the Users section

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token from BotFather | Required |
| `SUPPORT_GROUP_ID` | Telegram group ID for support team | Required |
| `WEB_DASHBOARD_URL` | URL of the web dashboard | `http://localhost:5000` |
| `SECRET_KEY` | Flask secret key for sessions | Required |
| `ESCALATION_TIMEOUT` | Escalation timeout in seconds | `900` (15 minutes) |

### Database Schema

The system uses SQLite with the following main tables:
- **Users**: Tech team members and authentication
- **SupportMessage**: Support requests from Telegram
- **SupportResponse**: Responses to support messages
- **ScheduleSlot**: On-call schedule definitions
- **Notification**: Escalation tracking
- **SystemConfig**: System configuration settings

## 📊 Web Dashboard Features

### Dashboard Overview
- Real-time statistics (total, open, in-progress, resolved messages)
- Current on-call person display
- Recent messages list
- Quick action buttons

### Message Management
- Filter messages by status (all, open, in-progress, resolved)
- Detailed message view with user information
- Response system with Telegram integration
- Status updates and assignment

### Schedule Management (Admin)
- Add/remove schedule slots
- Set primary and backup on-call personnel
- Weekly overview visualization
- Time-based schedule management

### User Management (Admin)
- Add/remove team members
- Set admin permissions
- Telegram integration setup
- User status management

## 🔔 Escalation System

### How It Works

1. **Support Request Received**: User sends `@support` message
2. **Immediate Notification**: Current on-call tech is notified via Telegram
3. **Escalation Timer**: 15-minute timer starts
4. **Auto-Escalation**: If no response, backup tech is notified
5. **Continued Escalation**: Process continues through all backup personnel
6. **Resolution Tracking**: Escalation stops when message is marked as handled

### Escalation Levels

- **Level 1**: Primary on-call person
- **Level 2**: First backup person
- **Level 3**: Second backup person
- **Level N**: Continue through all available backup personnel

## 🛠️ Development

### Project Structure

```
.
├── bot.py                 # Enhanced Telegram bot with escalation
├── app.py                 # Flask web application
├── models.py              # Database models
├── requirements.txt       # Bot dependencies
├── web_requirements.txt   # Web dashboard dependencies
├── .env                   # Environment configuration
├── .env.example          # Environment template
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── messages.html
│   ├── message_detail.html
│   ├── schedule.html
│   └── users.html
└── static/               # CSS and JavaScript
    ├── css/style.css
    └── js/app.js
```

### API Endpoints

The web dashboard provides several API endpoints for bot integration:

- `POST /api/support_message` - Create new support message
- `GET /api/current_oncall` - Get current on-call person
- `POST /api/escalate/{message_id}` - Escalate message
- `GET /api/message/{message_id}/status` - Check message status

## 🔒 Security

- **Password Hashing**: Uses bcrypt for secure password storage
- **Session Management**: Flask-Login for secure session handling
- **Environment Variables**: Sensitive data stored in environment variables
- **Input Validation**: WTForms validation on all user inputs
- **CSRF Protection**: Flask-WTF CSRF protection on forms

## 📈 Monitoring

### Logging

The system provides comprehensive logging:
- Bot activities and errors
- Web dashboard access and actions
- Escalation tracking
- API calls and responses

### Health Checks

- `/status` command in Telegram shows system health
- Web dashboard shows real-time statistics
- Escalation system monitors message handling

## 🚨 Troubleshooting

### Common Issues

1. **Bot Not Responding**
   - Check `BOT_TOKEN` in `.env`
   - Verify bot is started with `/start` command
   - Check bot logs for errors

2. **Web Dashboard Not Accessible**
   - Ensure Flask app is running on port 5000
   - Check `WEB_DASHBOARD_URL` configuration
   - Verify firewall settings

3. **Escalation Not Working**
   - Check Telegram User IDs in user management
   - Verify on-call schedules are configured
   - Check escalation timeout settings

4. **Messages Not Forwarding**
   - Verify `SUPPORT_GROUP_ID` is correct
   - Ensure bot is admin in support group
   - Check bot permissions

### Logs Location

- Bot logs: Console output when running `python bot.py`
- Web logs: Console output when running `python app.py`
- Database: `support_system.db` file

## 🔄 Backup and Recovery

### Database Backup

```bash
# Backup SQLite database
cp support_system.db support_system_backup_$(date +%Y%m%d).db
```

### Configuration Backup

```bash
# Backup configuration
cp .env .env.backup
```

## 🎯 Future Enhancements

- **Mobile App**: React Native mobile app for tech team
- **Analytics Dashboard**: Advanced reporting and analytics
- **Integration APIs**: Slack, Discord, Microsoft Teams integration
- **AI-Powered Routing**: Machine learning for intelligent message routing
- **Multi-Language Support**: Internationalization support
- **Voice Messages**: Support for voice message handling
- **File Attachments**: Handle file and image attachments
- **SLA Tracking**: Service level agreement monitoring
- **Customer Satisfaction**: Post-resolution feedback system

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For technical support or questions:
- Check the troubleshooting section above
- Review the logs for error messages
- Open an issue in the project repository

---

**Built with ❤️ for efficient customer support management**
