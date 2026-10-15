from app.core.config import settings
print(type(settings).__name__)
print('environment =', repr(settings.environment))
print('is_frozen?', getattr(settings, '__pydantic_config__', None))
