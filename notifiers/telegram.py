"""
Telegram通知器
"""

import requests
import logging

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Telegram通知器"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        发送消息
        :param message: 消息内容
        :param parse_mode: 解析模式（HTML/Markdown）
        :return: 是否发送成功
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            # 移除 raise_for_status()，改为手动解析结果以获取更多信息
            result = response.json()

            if result.get('ok'):
                logger.debug("Telegram消息发送成功")
                return True
            else:
                error_msg = result.get('description', '未知错误')
                logger.error(f"Telegram发送失败 (400): {error_msg}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram网络请求失败: {e}")
            return False
        except Exception as e:
            logger.error(f"Telegram发送异常: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        测试连接
        :return: 是否连接成功
        """
        return self.send("🧪 测试消息 - 配置成功！")

