import TelegramBot from 'node-telegram-bot-api';
import type { Finding, Project, User } from '@prisma/client';
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
  intern: User,
  finding: Finding,
  project: Project,
): Promise<void> {
  const message = `📞 *Explanation Requested*

*Intern:* ${intern.username}
*Project:* ${project.displayName}
*File:* \`${finding.filePath}\`
*Category:* ${finding.category}
*Difficulty:* ${finding.difficulty}

The intern would like a live explanation of this code review finding.`;

  await sendAdminNotification(message);
}
