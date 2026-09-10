# config.py
import os

# Development configuration
class DevelopmentConfig:
    DEBUG = True
    SECRET_KEY = 'a7K9mP2xL5nQ8wR3tY6uJ1vB4cF7hD0gS9eA2zX5kN8mQ3wR6tY1uJ4vB7cF0hD9gS2eA5zX8kN1mQ4wR7tY0uJ3vB6cF9hD2gS5eA8zX1kN4mQ7wR0tY3uJ6vB9cF2hD5gS8eA1zX4kN7mQ0wR3tY6uJ9vB2cF5hD8gS1eA4zX7kN0mQ3wR6tY9uJ2vB5cF8hD1gS4eA7zX0kN3mQ6wR9tY2uJ5vB8cF1hD4gS7eA0zX3kN6mQ9wR2tY5uJ8vB1cF4hD7gS0eA3zX6kN9mQ2wR5tY8uJ1vB4cF7hD0gS3eA6zX9kN2mQ5wR8tY1uJ4vB7cF0hD3gS6eA9zX2'
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