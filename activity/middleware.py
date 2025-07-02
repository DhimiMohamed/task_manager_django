# task_manager\activity\middleware.py
from threading import local
from django.utils.deprecation import MiddlewareMixin

_active = local()

class ActivityLogMiddleware(MiddlewareMixin):
    """Stores the current request/user for signal handlers."""
    
    def __call__(self, request):
        _active.request = request
        try:
            return super().__call__(request)
        finally:
            delattr(_active, 'request')

def get_current_user():
    """Get the user from the current request (for signals)."""
    request = getattr(_active, 'request', None)
    
    # First try to get user from request
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    
    # Then try to get from thread local storage if available
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = getattr(_active, 'user', None)
    if user and isinstance(user, User):
        return user
    
    return None