from django.utils import timezone
from django.contrib.auth.models import User
from .models import Profile

class UpdateLastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = Profile.objects.get(user=request.user)
                profile.last_seen = timezone.now()
                profile.save(update_fields=["last_seen"])
            except Profile.DoesNotExist:
                pass
        response = self.get_response(request)
        return response
