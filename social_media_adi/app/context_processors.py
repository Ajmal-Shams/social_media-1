from .models import FriendRequest
from .models import PostTag


def pending_friend_requests(request):
    """
    Injects the count of pending incoming friend requests into every template context.
    Used to show the notification badge on the nav bell icon.
    """
    if request.user.is_authenticated:
        friend_count = FriendRequest.objects.filter(
            to_user=request.user, status='pending'
        ).count()
        story_tag_count = PostTag.objects.filter(
            user=request.user,
            post__is_story=True,
            is_read=False,
        ).exclude(post__user=request.user).count()
        count = friend_count + story_tag_count
    else:
        count = 0
    return {'pending_friend_requests_count': count}
