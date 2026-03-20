from django.contrib import admin
import pandas as pd
from django.http import HttpResponse
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
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

def get_profile_dataframe(queryset):
    data = []
    for profile in queryset:
        data.append({
            'User ID': profile.user.id if profile.user else 'N/A',
            'Username': profile.user.username if profile.user else 'Deleted User',
            'Email': profile.user.email if profile.user else 'N/A',
            'First Name': profile.user.first_name if profile.user else 'N/A',
            'Last Name': profile.user.last_name if profile.user else 'N/A',
            'Score': round(profile.score, 2),
            'Ban Lvl': profile.ban_level,
            'Ban Until': profile.ban_until.strftime("%Y-%m-%d %H:%M") if profile.ban_until else 'None',
            'Last Active': profile.last_seen.strftime("%Y-%m-%d %H:%M") if profile.last_seen else 'Never',
            'DOB': profile.dob.strftime("%Y-%m-%d") if profile.dob else 'N/A',
        })
    return pd.DataFrame(data)

@admin.action(description="Download Selected as CSV")
def export_as_csv(modeladmin, request, queryset):
    df = get_profile_dataframe(queryset)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="user_reports.csv"'
    df.to_csv(response, index=False)
    return response

@admin.action(description="Download Selected as Excel")
def export_as_excel(modeladmin, request, queryset):
    df = get_profile_dataframe(queryset)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="user_reports.xlsx"'
    df.to_excel(response, index=False)
    return response

@admin.action(description="Download Selected as PDF")
def export_as_pdf(modeladmin, request, queryset):
    df = get_profile_dataframe(queryset)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="user_reports.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
    elements = []

    styles = getSampleStyleSheet()
    title = Paragraph("CircleUp User Safety Report", styles['Title'])
    elements.append(title)

    # Convert DataFrame to list of lists (headers + rows), making sure everything is a string
    data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    return response

@admin.action(description="Lift Ban for Selected Users")
def lift_user_ban(modeladmin, request, queryset):
    # Reset ban fields and reset safety score
    queryset.update(ban_until=None, ban_level=1, score=0.0)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'score', 'ban_until', 'ban_level']
    search_fields = ['user__username']
    list_filter = ['ban_level']
    actions = [export_as_csv, export_as_excel, export_as_pdf, lift_user_ban]

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
