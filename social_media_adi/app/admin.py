from django.contrib import admin
from .models import Posts, Comment, ReportedComments, Profile, CommentReport

@admin.register(Posts)
class PostsAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'text']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'text', 'score']

@admin.register(ReportedComments)
class ReportedCommentsAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'comment', 'feedback']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'score']

@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'comment', 'commenter', 'post', 'score', 'timestamp']

    # Override single delete
    def delete_model(self, request, obj):
        comment = obj.comment

        # Remove comment from post
        if comment and comment.post:
            comment.post.comments.remove(comment)

        # Adjust profile score
        if comment and comment.user:
            try:
                profile = Profile.objects.get(user=comment.user)
                profile.score = max(profile.score - comment.score, 0)
                profile.save()
            except Profile.DoesNotExist:
                pass

        # Delete the comment itself
        if comment:
            comment.delete()

        # Delete the report
        super().delete_model(request, obj)

    # Override bulk delete
    def delete_queryset(self, request, queryset):
        for obj in queryset:
            comment = obj.comment

            if comment and comment.post:
                comment.post.comments.remove(comment)

            if comment and comment.user:
                try:
                    profile = Profile.objects.get(user=comment.user)
                    profile.score = max(profile.score - comment.score, 0)
                    profile.save()
                except Profile.DoesNotExist:
                    pass

            if comment:
                comment.delete()

        # Delete the reports
        super().delete_queryset(request, queryset)
