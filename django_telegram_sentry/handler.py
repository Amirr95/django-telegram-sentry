from django.conf import settings

import requests
import logging
import traceback
import html
import time

class TelegramHandler(logging.Handler):
    def __init__(self, token: str=None, receiver_list: list[str]=None, proxies=None):
        super().__init__()

        if not token:
            raise ValueError("A Telegram bot token must be provided")

        if not receiver_list:
            raise ValueError("receiver_list must be specified as non-empty list of chat IDs")
        
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.receiver_list = receiver_list
        self.proxies = proxies
        
        # Initialize a logger specifically for logging errors related to the Telegram handler
        # This is to avoid a situation where the handler creates logs for itself
        self.error_logger = logging.getLogger('telegram_error_logger')
        file_handler = logging.FileHandler('telegram_errors.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.error_logger.addHandler(file_handler)
        self.error_logger.setLevel(logging.ERROR)

        
    def emit(self, record):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(record.created))
        try:
            request = record.request
            subject = "%s (%s IP): %s" % (
                record.levelname,
                (
                    "internal"
                    if request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS
                    else "EXTERNAL"
                ),
                record.getMessage(),
            )
        except Exception:
            subject = "%s: %s" % (record.levelname, record.getMessage())
            request = None
        subject = self.format_subject(subject)

        if record.exc_info:
            tb_list = traceback.format_exception(*record.exc_info)
            tb_string = "".join(tb_list)
            try:
                message = (
                    f"{timestamp} An exception was raised while handling a request\n"
                    f"<pre>{html.escape(subject)}</pre>"
                    f"request: {html.escape(request)}"
                    f"path: {html.escape(request.path)}"
                    f"method: {html.escape(request.method)}"
                    f"body: {html.escape(request.body.decode('utf-8'))}"
                    f"<pre>{html.escape(tb_string)}</pre>"
                ) 
            except AttributeError:
                message = (
                    f"{timestamp} An exception was raised while handling a request\n"
                    f"<pre>{html.escape(subject)}</pre>"
                    f"<pre>{html.escape(tb_string)}</pre>"
                )
            self.send_message(message)
        else:
            message = (
                f"<pre>{timestamp} {record.levelname} {record.module} {record.filename} {record.funcName} -  {html.escape(record.getMessage())}</pre>\n"
                # f"<pre>{html.escape(record.levelname)}: {html.escape(record.getMessage())}</pre>"
            )
            self.send_message(message)

            
    def send_message(self, message):
        with requests.session() as session:
            for receiver in self.receiver_list:
                try:
                    response = session.post(
                            self.url,
                            data={
                                "chat_id": receiver,
                                "text": message,
                                "parse_mode": "html"
                            },
                            timeout=3,
                            proxies= self.proxies
                        )
                    response.raise_for_status()
                except requests.exceptions.HTTPError:
                    self.error_logger.error(f"HTTP error occurred while calling Telegram's API: {response.text}")
                except Exception as e:
                    self.error_logger.error(f"Error sending log message to Telegram: {e}")

    def format_subject(self, subject):
        """
        Escape CR and LF characters.
        """
        return subject.replace("\n", "\\n").replace("\r", "\\r")

