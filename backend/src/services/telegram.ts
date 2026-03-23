import TelegramBot from 'node-telegram-bot-api';
import { config } from '../config';

let bot: TelegramBot | null = null;

function getBot(): TelegramBot | null {
  if (!config.telegram.botToken || config.telegram.botToken === 'xxxxx') {
    return null;
  }
  if (!bot) {
    bot = new TelegramBot(config.telegram.botToken);
  }
  return bot;
}

export async function sendAdminNotification(message: string): Promise<void> {
  const telegramBot = getBot();
  if (!telegramBot || !config.telegram.adminChatId) {
    console.log('[Telegram] Bot not configured, skipping notification:', message);
    return;
  }

  try {
    await telegramBot.sendMessage(config.telegram.adminChatId, message, {
      parse_mode: 'Markdown',
    });
  } catch (err) {
    console.error('[Telegram] Failed to send notification:', err);
  }
}

export async function notifyExplanationRequested(
  internName: string,
  findingFile: string,
  projectName: string,
): Promise<void> {
  const message = `📞 Explanation requested by *${internName}* for finding in \`${findingFile}\` in project *${projectName}*`;
  await sendAdminNotification(message);
}
