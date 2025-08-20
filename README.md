# Telegram Support Bot

A Python-based Telegram bot that forwards support requests from any chat to a designated support group. When users type `@support` followed by their message, it gets automatically forwarded to your support team.

## Features

- **Support Request Forwarding**: Messages starting with `@support` are automatically forwarded to a designated support group
- **User Information**: Forwarded messages include user details (name, username, user ID, chat info)
- **Confirmation Messages**: Users receive confirmation when their support request is forwarded
- **Error Handling**: Graceful error handling with user-friendly messages
- **Logging**: Comprehensive logging for monitoring and debugging

## Setup Instructions

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the instructions
3. Choose a name and username for your bot
4. Save the bot token you receive

### 2. Set Up the Support Group

1. Create a Telegram group for your support team
2. Add your bot to the group as an administrator
3. Get the group's chat ID:
   - Send a message in the group
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Look for the "chat" object and copy the "id" value (it will be negative for groups)

### 3. Install Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your configuration:
```env
BOT_TOKEN=your_bot_token_from_botfather
SUPPORT_GROUP_ID=-1001234567890
```

### 5. Run the Bot

```bash
python bot.py
```

## Usage

### For End Users

To send a support request, users simply type:
```
@support I need help with my account
```

The bot will:
1. Extract the message after `@support`
2. Forward it to the support group with user information
3. Send a confirmation message to the user

### Available Commands

- `/start` - Welcome message and usage instructions
- `/help` - Show help information and usage examples

### Example Support Request

When a user sends:
```
@support My payment failed but money was deducted
```

The support group receives:
```
🆘 Support Request

From: John Doe (@johndoe)
User ID: 123456789
Chat: Customer Support Chat (ID: -1001234567890)

Message:
My payment failed but money was deducted
```

## Configuration

### Environment Variables

- `BOT_TOKEN`: Your Telegram bot token from BotFather (required)
- `SUPPORT_GROUP_ID`: The chat ID of your support group (required)

### Security Notes

- Never share your bot token publicly
- Keep the `.env` file in your `.gitignore`
- Only add trusted administrators to your support group
- The bot needs to be an administrator in the support group to send messages

## Troubleshooting

### Common Issues

1. **Bot not responding**
   - Check if `BOT_TOKEN` is correctly set in `.env`
   - Ensure the bot is started with `/start` command

2. **Support messages not forwarding**
   - Verify `SUPPORT_GROUP_ID` is correct (should be negative for groups)
   - Ensure the bot is added to the support group as an administrator
   - Check the bot logs for error messages

3. **Permission errors**
   - Make sure the bot has permission to send messages in the support group
   - Verify the bot is an administrator in the support group

### Logs

The bot provides detailed logging. Check the console output for:
- Successful message forwards
- Configuration errors
- API errors

## Development

### Project Structure

```
.
├── bot.py              # Main bot script
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .env              # Your environment variables (create this)
└── README.md         # This file
```

### Adding Features

To add new functionality:
1. Create new handler functions
2. Register them in the `main()` function
3. Update the help command with new features

## License

This project is open source and available under the MIT License.
