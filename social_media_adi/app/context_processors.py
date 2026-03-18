from .models import FriendRequest


def pending_friend_requests(request):
    """
    Injects the count of pending incoming friend requests into every template context.
    Used to show the notification badge on the nav bell icon.
    """
    if request.user.is_authenticated:
        count = FriendRequest.objects.filter(
            to_user=request.user, status='pending'
        ).count()
    else:
        count = 0
    return {'pending_friend_requests_count': count}
