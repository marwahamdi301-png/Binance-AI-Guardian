# ═══════════════════════════════════════════════════════════════════
#                  BAYA EMPIRE - الإشعارات
#                      Telegram + Discord Notifications
# ═══════════════════════════════════════════════════════════════════

import requests
from datetime import datetime

class NotificationService:
    """نظام الإشعارات - Telegram و Discord"""

    def __init__(self, telegram_token=None, telegram_chat_id=None, discord_webhook=None):
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook = discord_webhook

    def send_telegram(self, message):
        """إرسال رسالة عبر Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except:
            return False

    def send_trade_notification(self, symbol, side, price, amount, profit=None):
        """إشعار صفقة جديدة"""
        profit_text = f" | 💰 الربح: ${profit:.2f}" if profit else ""
        
        message = f"""
🎯 <b>صفقة جديدة</b>

📊 الرمز: {symbol}
📈 الاتجاه: {side}
💵 السعر: ${price:,.2f}
📦 الكمية: {amount}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{profit_text}
        """

        return self.send_telegram(message)

    def send_alert(self, title, message):
        """إشعار تنبيه"""
        msg = f"⚠️ <b>{title}</b>\n\n{message}"
        return self.send_telegram(msg)

if __name__ == "__main__":
    notifier = NotificationService(
        telegram_token="YOUR_TOKEN",
        telegram_chat_id="YOUR_CHAT_ID"
    )
    notifier.send_trade_notification("BTCUSDT", "LONG", 45000, 0.1)
