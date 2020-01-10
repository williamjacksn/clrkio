import os


class Settings:
    church_username: str
    church_password: str
    church_tools_api_key: str
    church_tools_basic_auth_username: str
    church_tools_basic_auth_password: str
    db: str
    log_format: str
    log_level: str
    secret_key: str

    def __init__(self):
        self.church_username = os.getenv('CHURCH_USERNAME')
        self.church_password = os.getenv('CHURCH_PASSWORD')
        self.church_tools_api_key = os.getenv('CHURCH_TOOLS_API_KEY')
        self.church_tools_basic_auth_username = os.getenv('CHURCH_TOOLS_BASIC_AUTH_USERNAME')
        self.church_tools_basic_auth_password = os.getenv('CHURCH_TOOLS_BASIC_AUTH_PASSWORD')
        self.db = os.getenv('DB')
        self.log_format = os.getenv('LOG_FORMAT', '%(levelname)s [%(name)s] %(message)s')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.secret_key = os.getenv('SECRET_KEY')
