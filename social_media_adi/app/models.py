from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Friend relationship model
class Friend(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends')
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_of')
    created = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ('user', 'friend')
    def __str__(self):
        return f"{self.user.username} ↔ {self.friend.username}"

# Friend request model
class FriendRequest(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(max_length=10, choices=[('pending','Pending'),('accepted','Accepted'),('rejected','Rejected')], default='pending')
    created = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ('from_user', 'to_user')
    def __str__(self):
        return f"{self.from_user.username} → {self.to_user.username} [{self.status}]"
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Profile model to track score and profile picture
class Profile(models.Model):
    pic = models.FilePathField(path='uploads/', blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    text = models.CharField(max_length=100, null=True, blank=True)
    score = models.FloatField(default=0.0)
    last_seen = models.DateTimeField(null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    last_toxic_comment = models.DateTimeField(null=True, blank=True)  # Timestamp of most recent toxic comment
    ban_until = models.DateTimeField(null=True, blank=True)           # When current ban expires
    ban_level = models.IntegerField(default=1)                        # Ban multiplier: 1=4h, 2=8h, 3=12h...
    last_ban_applied = models.DateTimeField(null=True, blank=True)    # When the last ban was issued (for escalation tracking)

    def __str__(self):
        return self.pic if self.pic else f"Profile of {self.user.username if self.user else 'Deleted User'}"

# Comments reported manually by users (feedback + comment ref)
class ReportedComments(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.ForeignKey('Comment', on_delete=models.DO_NOTHING)
    feedback = models.CharField(max_length=300)

    def __str__(self):
        return f"Reported by {self.user.username if self.user else 'Unknown'}: {self.comment.text[:30]}"

# Main post model (has image, likes, and many comments)
# Main post model (has image, likes, and many comments)
class Posts(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    image_path = models.FilePathField(path='uploads/')
    text = models.CharField(max_length=500, blank=True)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    comments = models.ManyToManyField('Comment', blank=True)
    like_count = models.IntegerField(default=0)
    is_story = models.BooleanField(default=False)
    is_reel = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    created = models.DateTimeField(default=timezone.now)

    @property
    def is_video_file(self):
        if not self.image_path: return False
        return self.image_path.lower().endswith(('.mp4', '.mov', '.webm', '.ogg'))

    def __str__(self):
        return f"{'Story' if self.is_story else 'Post'} {self.id} by {self.user.username if self.user else 'Deleted User'}"

# Comment model (includes score)
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    post = models.ForeignKey(Posts, on_delete=models.CASCADE, null=True, blank=True, related_name='post_comments')
    text = models.CharField(max_length=300)
    score = models.FloatField(default=0.0)

    def __str__(self):
        return f"Comment {self.id} by {self.user.username if self.user else 'Deleted User'}"

# Auto-generated comment reports from ML
class CommentReport(models.Model):
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, related_name='reports')
    commenter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='commenter')
    post = models.ForeignKey('Posts', on_delete=models.CASCADE, related_name='comment_reports')
    post_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='post_owner')
    comment_text = models.TextField()
    score = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Report: {self.commenter.username if self.commenter else 'Unknown'} on Post {self.post.id}"

    # Message model for chat functionality
class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    text = models.TextField()
    score = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    def __str__(self):
         return f"From {self.sender.username} to {self.receiver.username}: {self.text[:30]}"
