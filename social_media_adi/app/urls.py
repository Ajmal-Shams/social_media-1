from django.urls import path
from . views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
        path('chats/', chat_list, name='chat-list'),
        path('chats/<int:user_id>/', chat_detail, name='chat-detail'),
        path('chats/<int:user_id>/send/', send_message, name='send-message'),
    path('',home,name="home"),
    path('home/<int:id>',add_comment,name="add_comment"),
    path('legal/',legal_page, name='legal'),
    path('login',app_login,name="login"),
    path('signup',signup,name="signup"),
    path('profile',profile,name="profile"),
    path('set_profile',profile_upload,name="set_profile"),
    path('logout',app_logout,name="logout"),
    path('create',create,name="create"),
    path("fetch_commants_api/<int:id>",fetch_commants_api,name="fetch_commants_api"),
    path("remove-comments",remove_comments,name="comments"),
    path("delete_comments_profile",delete_comments_profile,name="delete_comments_profile"),

    path("force-commenents",force_remove_comments,name="force-comments"),
    path("remove-comments/<int:id>",remove_comments_id,name="remove-comment"),
    path("force-remove-comments/<int:id>",force_remove_comments_id,name="force-remove-comment"),
    path("report-comments/<int:id>",report_comment,name="report-comment"),
    path('like-post/<int:post_id>/', like_post, name='like-post'),
    path('search/', search_users, name='search'),
    path('profile/<str:username>/', profile, name='view_profile'),
    path('friend-request/send/<int:user_id>/', send_friend_request, name='send_friend_request'),
    path('friend-request/accept/<int:request_id>/', accept_friend_request, name='accept_friend_request'),
    path('friend-request/reject/<int:request_id>/', reject_friend_request, name='reject_friend_request'),
    path('friend/remove/<int:user_id>/', remove_friend, name='remove_friend'),
    path('delete-post/<int:post_id>/', delete_post, name='delete_post'),
    path('edit-post/<int:post_id>/', edit_post, name='edit_post'),
    path('delete-comment/<int:comment_id>/', delete_comment, name='delete_comment'),
    path('reels/', reels, name='reels'),
    path('notifications/', notifications, name='notifications'),


]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static('profile/', document_root='profile/')