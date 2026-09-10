# config.py
import os

# Development configuration
class DevelopmentConfig:
    DEBUG = True
    SECRET_KEY = 'dev-secret-key-2026'
    DATABASE = 'grades.db'
    HOST = '0.0.0.0'
    PORT = 5000
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True

# Production configuration
class ProductionConfig:
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-production-secret-key-here'
    DATABASE = 'grades.db'
    HOST = '0.0.0.0'
    PORT = 5000
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
    @classmethod
    def init_app(cls, app):
        # Production-specific setup
        pass

# Select configuration based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}