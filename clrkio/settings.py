import os


class Settings:
    church_password: str
    church_username: str
    db: str
    log_format: str
    log_level: str
    secret_key: str

    def __init__(self):
        self.church_password = os.getenv('CHURCH_PASSWORD')
        self.church_username = os.getenv('CHURCH_USERNAME')
        self.db = os.getenv('DB')
        self.log_format = os.getenv('LOG_FORMAT', '%(levelname)s [%(name)s] %(message)s')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.secret_key = os.getenv('SECRET_KEY')
