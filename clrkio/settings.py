import os

from typing import Dict


def as_bool(value: str) -> bool:
    true_values = ('true', '1', 'yes', 'on')
    return value.lower() in true_values


class Settings:
    auto_sync: bool
    bootstrap_admin: str
    church_username: str
    church_password: str
    church_tools_client_id: str
    church_tools_client_secret: str
    db: str
    debug_layout: bool
    log_format: str
    log_level: str
    mailgun_api_key: str
    mailgun_domain: str
    mailgun_sender: str
    openid_client_id: str
    openid_client_secret: str
    openid_discovery_document: str
    other_log_levels: Dict[str, str] = {}
    permanent_sessions: bool
    port: int
    reset_database: bool
    scheme: str
    secret_key: str
    server_name: str
    support_email: str
    version: str
    web_server_threads: int

    def __init__(self):
        self.auto_sync = as_bool(os.getenv('AUTO_SYNC', 'False'))
        self.bootstrap_admin = os.getenv('BOOTSTRAP_ADMIN')
        self.church_username = os.getenv('CHURCH_USERNAME')
        self.church_password = os.getenv('CHURCH_PASSWORD')
        self.church_tools_client_id = os.getenv('CHURCH_TOOLS_CLIENT_ID')
        self.church_tools_client_secret = os.getenv('CHURCH_TOOLS_CLIENT_SECRET')
        self.debug_layout = as_bool(os.getenv('DEBUG_LAYOUT', 'False'))
        self.db = os.getenv('DB')
        self.log_format = os.getenv('LOG_FORMAT', '%(levelname)s [%(name)s] %(message)s')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.mailgun_api_key = os.getenv('MAILGUN_API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        self.mailgun_sender = os.getenv('MAILGUN_SENDER')
        self.openid_client_id = os.getenv('OPENID_CLIENT_ID')
        self.openid_client_secret = os.getenv('OPENID_CLIENT_SECRET')
        self.openid_discovery_document = os.getenv('OPENID_DISCOVERY_DOCUMENT')
        self.permanent_sessions = as_bool(os.getenv('PERMANENT_SESSIONS', 'False'))
        self.port = int(os.getenv('PORT', '8080'))
        self.reset_database = as_bool(os.getenv('RESET_DATABASE', 'False'))
        self.scheme = os.getenv('SCHEME', 'http')
        self.secret_key = os.getenv('SECRET_KEY')
        self.server_name = os.getenv('SERVER_NAME', f'localhost:{self.port}')
        self.support_email = os.getenv('SUPPORT_EMAIL', 'none')
        self.version = os.getenv('APP_VERSION', 'unknown')
        self.web_server_threads = int(os.getenv('WEB_SERVER_THREADS', '4'))

        for log_spec in os.getenv('OTHER_LOG_LEVELS', '').split():
            logger, level = log_spec.split(':', maxsplit=1)
            self.other_log_levels[logger] = level
