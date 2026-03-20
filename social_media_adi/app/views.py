WITH_ML = True
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
import os
from django.views.decorators.csrf import csrf_protect
import pandas as pd
import numpy as np
import re
from .models import Comment, Profile, ReportedComments, Posts, Friend, Message, FriendRequest, CommentReport
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt

try:
    if WITH_ML:
        import tensorflow as tf
        from tensorflow.keras.preprocessing.text import Tokenizer
        from tensorflow.keras.preprocessing.sequence import pad_sequences
        import pickle
        
        # Load model and tokenizer
        try:
            loaded_model = tf.keras.models.load_model('sentiment_model.h5')
            with open('tokenizer.pickle', 'rb') as handle:
                tokenizer = pickle.load(handle)
        except Exception as e:
            print(f"Error loading ML models: {e}")
            WITH_ML = False
except ImportError as e:
    print(f"ML Import error (likely protobuf): {e}")
    WITH_ML = False
except Exception as e:
    print(f"General error during ML initialization: {e}")
    WITH_ML = False

def get_toxicity_score(text):
    if not WITH_ML or not text:
        return 0.0
    try:
        twt = tokenizer.texts_to_sequences([text])
        twt = pad_sequences(twt, maxlen=100, dtype='int32', value=0)
        raw_score = loaded_model.predict(twt, batch_size=1, verbose=0)[0][0]
        return float(max(raw_score, 0))
    except:
        return 0.0

@login_required(login_url='login')
def home(request):
    # Clear safety alerts after they've been potentially shown
    toxic_blocked = request.session.pop('toxic_blocked', False)
    issues = request.session.pop('issues', False)
    
    # Only show regular posts in the main feed (exclude reels)
    db = Posts.objects.filter(is_story=False, is_reel=False).order_by("-id")
    
    # Get user's own active story (last 24 hours)
    last_24h = timezone.now() - timezone.timedelta(hours=24)
    own_story = Posts.objects.filter(user=request.user, is_story=True, created__gte=last_24h).order_by('-created').first()

    # Get stories from friends (last 24 hours)
    friends = Friend.objects.filter(user=request.user)
    friends_list = [f.friend for f in friends]
    
    last_24h = timezone.now() - timezone.timedelta(hours=24)
    stories_all = Posts.objects.filter(
        user__in=friends_list, 
        is_story=True, 
        created__gte=last_24h
    ).select_related('user').order_by('-created')
    
    # Portable distinct by user
    stories = []
    seen_users = set()
    for s in stories_all:
        if s.user_id not in seen_users:
            stories.append(s)
            seen_users.add(s.user_id)
    
    # Suggest users to follow
    suggestions = User.objects.exclude(id=request.user.id).exclude(
        id__in=[f.friend.id for f in friends]
    )[:5]
    
    # Auto-reduce score if user has been good for 4+ hours since last toxic comment
    try:
        user_profile = Profile.objects.get(user=request.user)
        if user_profile.last_toxic_comment and user_profile.score > 0:
            hours_since = (timezone.now() - user_profile.last_toxic_comment).total_seconds() / 3600
            # Reduce 1 point per complete 4-hour period of good behavior
            reduction_steps = int(hours_since // 4)
            if reduction_steps > 0:
                user_profile.score = max(0.0, user_profile.score - reduction_steps)
                # Advance last_toxic_comment by the windows consumed so we don't double-reduce
                user_profile.last_toxic_comment += timezone.timedelta(hours=reduction_steps * 4)
                if user_profile.score <= 0:
                    user_profile.last_toxic_comment = None  # Clean slate
                user_profile.save()
    except Profile.DoesNotExist:
        pass

    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count() if request.user.is_authenticated else 0

    # Pass ban status to templates
    ban_until = None
    ban_level = 1
    ban_hours = 4
    try:
        user_profile = Profile.objects.get(user=request.user)
        if user_profile.ban_until and user_profile.ban_until > timezone.now():
            ban_until = user_profile.ban_until.isoformat()
            ban_level = user_profile.ban_level
            ban_hours = ban_level * 4
    except Profile.DoesNotExist:
        pass

    return render(request, "home.html", {
        "db": db,
        "own_story": own_story,
        "stories": stories,
        "suggestions": suggestions,
        "issues": issues,
        "toxic_blocked": toxic_blocked,
        "unread_messages_count": unread_messages_count,
        "ban_until": ban_until,
        "ban_level": ban_level,
        "ban_hours": ban_hours,
        "ban_steps": [i*4 for i in range(1, 8)],
    })



def report_comment(request, id):
    user = ""
    comment = ""
    db = Comment.objects.get(id=id)
    user = db.user
    comment = db.text
    if request.method == 'POST':
        feedback = request.POST['feedback']
        dbf = ReportedComments(user=user, comment=db, feedback=feedback)
        dbf.save()
        return redirect('home')
    return render(request, "report.html", {'user1': user, 'comment': comment})

from .models import Comment, CommentReport, Posts, Profile, Message
from django.db.models import Q
from django.contrib.auth.decorators import login_required

# Chat views
@login_required(login_url='login')
def chat_list(request):
    from datetime import datetime as dt
    # List all users except self
    users = list(User.objects.exclude(id=request.user.id))
    user_profiles = {u.id: Profile.objects.filter(user=u).first() for u in users}
    # Unread message count per user
    unread_counts = {u.id: Message.objects.filter(sender=u, receiver=request.user, is_read=False).count() for u in users}

    # Get latest message timestamp for each user (used for sorting conversations)
    user_last_msg = {}
    for u in users:
        last_msg = Message.objects.filter(
            Q(sender=request.user, receiver=u) | Q(sender=u, receiver=request.user)
        ).order_by('-timestamp').first()
        user_last_msg[u.id] = last_msg.timestamp if last_msg else None

    # Sort: most recently messaged users appear first; users with no messages go to the bottom
    users_sorted = sorted(
        users,
        key=lambda u: user_last_msg.get(u.id) or dt(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True
    )

    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count()
    return render(request, "chat_list.html", {
        "users": users_sorted,
        "user_profiles": user_profiles,
        "unread_counts": unread_counts,
        "unread_messages_count": unread_messages_count
    })

@login_required(login_url='login')
def chat_detail(request, user_id):
    # Show chat between request.user and user_id
    friend = User.objects.get(id=user_id)
    friend_profile = Profile.objects.filter(user=friend).first()
    messages = Message.objects.filter(
        (Q(sender=request.user, receiver=friend) | Q(sender=friend, receiver=request.user))
    ).order_by('timestamp')
    # Mark all received messages as read
    Message.objects.filter(sender=friend, receiver=request.user, is_read=False).update(is_read=True)
    # Pop the flagged-message session flag (set by send_message when a toxic message is blocked)
    msg_flagged = request.session.pop('msg_flagged', False)
    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count()
    return render(request, "chat_detail.html", {
        "friend": friend,
        "friend_profile": friend_profile,
        "messages": messages,
        "msg_flagged": msg_flagged,
        "unread_messages_count": unread_messages_count
    })

@login_required(login_url='login')
def send_message(request, user_id):
    if request.method == "POST":
        from django.utils import timezone
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        friend = User.objects.get(id=user_id)
        text = request.POST.get("text", "").strip()
        if text:
            profile, _ = Profile.objects.get_or_create(user=request.user)

            # --- Check existing ban first ---
            if profile.ban_until and profile.ban_until > timezone.now():
                secs_left = int((profile.ban_until - timezone.now()).total_seconds())
                if is_ajax:
                    return JsonResponse({"success": False, "error": "banned", "ban_seconds": secs_left})
                request.session['msg_flagged'] = True
                return redirect('chat-detail', user_id=user_id)

            score = get_toxicity_score(text)

            if score > 0.5:
                # Block the message — do NOT deliver it to the receiver
                profile.score += score
                profile.last_toxic_comment = timezone.now()

                # Apply progressive ban if threshold crossed
                if profile.score > 20:
                    now = timezone.now()
                    if profile.last_ban_applied and (now - profile.last_ban_applied).days < 4:
                        profile.ban_level += 1
                    ban_hours = profile.ban_level * 4
                    profile.ban_until = now + timezone.timedelta(hours=ban_hours)
                    profile.last_ban_applied = now
                    profile.score = 0.0
                    profile.save()
                    if is_ajax:
                        return JsonResponse({"success": False, "error": "banned",
                                             "ban_seconds": ban_hours * 3600,
                                             "ban_hours": ban_hours})
                    request.session['msg_flagged'] = True
                    return redirect('chat-detail', user_id=user_id)

                profile.save()
                if is_ajax:
                    return JsonResponse({"success": False, "error": "toxic_blocked"})
                request.session['msg_flagged'] = True
                return redirect('chat-detail', user_id=user_id)

            # Only create message if it passes the toxicity check
            Message.objects.create(sender=request.user, receiver=friend, text=text, score=score)
            if is_ajax:
                return JsonResponse({"success": True, "text": text})
        if is_ajax:
            return JsonResponse({"success": False, "error": "empty"})
        return redirect('chat-detail', user_id=user_id)
from django.utils import timezone

def add_comment(request, id):
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        import json
        if is_ajax and request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                comment_text = data.get('comment', '').strip()
            except json.JSONDecodeError:
                comment_text = ''
        else:
            comment_text = request.POST.get('comment', '').strip()
            
        if not comment_text:
            if is_ajax: return JsonResponse({"success": False, "error": "Empty comment"})
            return redirect('home')  # Or show error if empty comment

        if request.user.is_anonymous:
            if is_ajax: return JsonResponse({"success": False, "error": "Not authenticated"})
            return redirect('login')

        profile, created = Profile.objects.get_or_create(user=request.user)

        # --- Progressive ban check ---
        if profile.ban_until and profile.ban_until > timezone.now():
            secs_left = int((profile.ban_until - timezone.now()).total_seconds())
            if is_ajax:
                return JsonResponse({"success": False, "error": "banned", "ban_seconds": secs_left})
            return redirect('home')

        sentiment_score = get_toxicity_score(comment_text)

        # Get the post
        try:
            post_instance = Posts.objects.get(id=id)
        except Posts.DoesNotExist:
            if is_ajax: return JsonResponse({"success": False, "error": "Post not found"})
            return redirect('home')

        # If toxic comment, increase profile score and issue progressive ban if threshold reached
        if sentiment_score > 0.5:
            request.session['notification'] = True
            profile.score += sentiment_score
            profile.last_toxic_comment = timezone.now()

            # Issue a ban only when the threshold is reached
            if profile.score > 20:
                now = timezone.now()
                # Escalate ban_level if last ban was within 4 days
                if profile.last_ban_applied and (now - profile.last_ban_applied).days < 4:
                    profile.ban_level += 1  # each repeat offence within 4 days escalates
                # else ban_level stays same (or resets – here we keep escalation cumulative)
                ban_hours = profile.ban_level * 4
                profile.ban_until = now + timezone.timedelta(hours=ban_hours)
                profile.last_ban_applied = now
                profile.score = 0.0  # reset score on ban so next offence starts fresh
                profile.save()
                if is_ajax:
                    return JsonResponse({"success": False, "error": "banned",
                                         "ban_seconds": ban_hours * 3600,
                                         "ban_hours": ban_hours})
                return redirect('home')

            profile.save()
            if is_ajax:
                return JsonResponse({"success": False, "error": "toxic_blocked"})
            return redirect('home')

        # Save the comment
        comment = Comment.objects.create(
            user=request.user,
            text=comment_text,
            score=sentiment_score,
            post=post_instance
        )
        post_instance.comments.add(comment)
        post_instance.save()

        if is_ajax:
            return JsonResponse({
                "success": True,
                "comment": {
                    "id": comment.id,
                    "text": comment.text,
                    "username": comment.user.username,
                    "flagged": False
                }
            })

        return redirect('home')

    return render(request, "home.html", {})


@login_required(login_url='login')
@csrf_protect
def create(request):
    if request.method == "POST":
        user = request.user
        image = request.FILES.get('img')
        text = request.POST.get('caption', '')
        is_story = request.POST.get('is_story') == 'on'
        is_reel = request.POST.get('is_reel') == 'on'
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # Safety Check
        score = get_toxicity_score(text)
        
        # Always allow post but track toxicity score
        # Increase profile score if toxic
        if score > 0.5:
            profile = Profile.objects.get(user=request.user)
            profile.score += score
            profile.save()
            # Hard block toxic posts as per user request "cannot post"
            request.session['toxic_blocked'] = True
            if is_ajax:
                return JsonResponse({"success": False, "error": "toxic_blocked"})
            return redirect('home')

        if image:
            # Ensure uploads directory exists
            os.makedirs(os.path.join(os.getcwd(), 'uploads'), exist_ok=True)
            
            file_path = os.path.join(os.getcwd(), 'uploads', image.name)
            with open(file_path, 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)
            
            db = Posts(
                user=user, 
                image_path="uploads/" + image.name, 
                text=text,
                is_story=is_story,
                is_reel=is_reel,
                score=score
            )
            db.save()
            
            # Processing tags
            tags_json = request.POST.get('tags', '[]')
            import json
            from .models import PostTag
            tag_data = []
            try:
                tags = json.loads(tags_json)
                for t in tags:
                    tagged_user_id = t.get('user_id')
                    x = t.get('x')
                    y = t.get('y')
                    if tagged_user_id and x is not None and y is not None:
                        pt, _ = PostTag.objects.get_or_create(post=db, user_id=tagged_user_id, defaults={'x_coordinate': x, 'y_coordinate': y})
                        tag_data.append({
                            'username': pt.user.username,
                            'x': pt.x_coordinate,
                            'y': pt.y_coordinate,
                            'profile_url': f"/profile/{pt.user.username}/"
                        })
            except Exception as e:
                print("Error parsing tags:", e)
            
            if is_ajax:
                return JsonResponse({
                    "success": True,
                    "post": {
                        "id": db.id,
                        "username": user.username,
                        "user_initial": user.username[0].upper(),
                        "image_path": db.image_path,
                        "text": db.text,
                        "like_count": 0,
                        "comment_count": 0,
                        "is_reel": is_reel,
                        "is_story": is_story,
                        "is_video_file": db.is_video_file,
                        "tags": tag_data
                    }
                })
            return redirect('home')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": False, "error": "Invalid request"})
    return redirect('home')

from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Profile, Comment, Posts
from django.contrib.auth.models import User

@login_required(login_url='login')
def delete_post(request, post_id):
    post = Posts.objects.get(id=post_id, user=request.user)
    # Reduce profile score if the post was toxic
    if post.score > 0.5:
        profile = Profile.objects.get(user=request.user)
        profile.score = max(0, profile.score - post.score)
        profile.save()
    post.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True})
    return redirect('home')

@login_required(login_url='login')
def edit_post(request, post_id):
    if request.method == "POST":
        post = Posts.objects.get(id=post_id, user=request.user)
        text = request.POST.get('caption', '')
        
        # Safety Check
        score = get_toxicity_score(text)
        if score > 0.5:
            request.session['issues'] = True
            return redirect('home')
            
        post.text = text
        post.save()
    return redirect('home')

@login_required(login_url='login')
def delete_comment(request, comment_id):
    try:
        comment = Comment.objects.get(id=comment_id, user=request.user)
        # Also clean up profile score if it was flagged
        if comment.score > 0.5:
            profile = Profile.objects.get(user=request.user)
            profile.score = max(0, profile.score - comment.score)
            profile.save()
        comment.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": True})
    except Comment.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "error": "Not found"})
        pass
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@csrf_exempt
def app_login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            try:
                profile = Profile.objects.get(user=user)

                if profile.pic:
                    request.session['profile'] = str(profile.pic)
                else:
                    request.session['profile'] = ""
                return redirect('profile')
            except Profile.DoesNotExist:
                return HttpResponse("Profile does not exist for this user.")
        else:
            return render(request, "login.html", {
                "error": "Invalid username or password"
            })
    return render(request, "login.html")


def signup(request):
    error_message = None
    if request.method == "POST":
        email = request.POST['email']
        username = request.POST['username']
        password = request.POST['password']
        dob_str = request.POST.get('dob')
        from datetime import datetime, date
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 16:
                error_message = "You must be at least 16 years old to sign up."
            else:
                user = User.objects.create_user(username, email, password)
                user.save()
                db = Profile(user=user, dob=dob)
                db.save()
                return redirect('login')
        except ValueError:
            error_message = "Please enter a valid date of birth."
        except Exception as e:
            from django.db import IntegrityError
            if isinstance(e, IntegrityError):
                error_message = "Username already exists. Please choose a different username."
            else:
                error_message = "An error occurred during signup. Please try again."
    return render(request, "sign_up.html", {"error_message": error_message})

@login_required(login_url='login')
def profile(request, username=None):
    if username is None:
        viewed_user = request.user
    else:
        viewed_user = User.objects.get(username=username)
        
    try:
        profile_obj = Profile.objects.get(user=viewed_user)
    except Profile.DoesNotExist:
        profile_obj = Profile.objects.create(user=viewed_user)
        
    # Separate regular posts, reels, and stories
    all_posts = Posts.objects.filter(user=viewed_user).order_by('-id')
    regular_posts = all_posts.filter(is_story=False, is_reel=False)
    reels_posts = all_posts.filter(is_reel=True)
    
    # Calculate counts
    followers_count = Friend.objects.filter(friend=viewed_user).count()
    following_count = Friend.objects.filter(user=viewed_user).count()
    
    # Check relationship status
    is_self = (viewed_user == request.user)
    is_friend = Friend.objects.filter(user=request.user, friend=viewed_user).exists()
    sent_request = FriendRequest.objects.filter(from_user=request.user, to_user=viewed_user, status='pending').exists()
    received_request = FriendRequest.objects.filter(from_user=viewed_user, to_user=request.user, status='pending').first()
    
    # Incoming requests (only shown on self profile)
    incoming_requests = []
    if is_self:
        incoming_requests = FriendRequest.objects.filter(to_user=request.user, status='pending')

    # Tagged posts
    tagged_posts = Posts.objects.filter(tags__user=viewed_user).distinct().order_by('-id')

    return render(request, "profile.html", {
        "viewed_user": viewed_user,
        "profile": profile_obj,
        'db': regular_posts,
        'reels_db': reels_posts,
        'tagged_posts': tagged_posts,
        'posts_count': regular_posts.count(),
        'reels_count': reels_posts.count(),
        'tagged_count': tagged_posts.count(),
        'followers_count': followers_count,
        'following_count': following_count,
        'is_self': is_self,
        'is_friend': is_friend,
        'sent_request': sent_request,
        'received_request': received_request,
        'incoming_requests': incoming_requests
    })


@login_required(login_url='login')
def edit_profile(request):
    """Allow user to edit their bio, username, first name, and last name via AJAX."""
    if request.method == "POST":
        bio = request.POST.get('bio', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()

        user = request.user
        
        # Check if username is being changed and if it's already taken
        if username and username != user.username:
            if User.objects.filter(username=username).exclude(id=user.id).exists():
                return JsonResponse({"success": False, "error": "Username already exists."})
            user.username = username

        # Update user name fields
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # Update profile bio
        profile_obj, _ = Profile.objects.get_or_create(user=user)
        profile_obj.text = bio
        profile_obj.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "bio": profile_obj.text
            })
            
    return redirect('profile')

def app_logout(request):
    logout(request)
    return redirect('login')


def remove_comments(request):
    # Get the current user's profile and score
    profile = Profile.objects.get(user=request.user)
    score = profile.score

    # Fetch only toxic comments made by this user (score > 0.5)
    toxic_comments = Comment.objects.filter(user=request.user, score__gt=0.5)

    # Render the force-remove UI
    return render(request, "comments.html", {
        'db': toxic_comments,
        'score': score,
    })


def delete_comments_profile(request):
    return render(request, 'comments.html')

    


def force_remove_comments(request):
    db = Comment.objects.filter(user=request.user, score__gt=0.5).select_related('user', 'post')
    profile = Profile.objects.get(user=request.user)  # fetch profile and score
    return render(request, "force_remove_comments.html", {
        'db': db,
        'profile_score': round(profile.score, 2)  # optional: round for cleaner display
    })

def remove_comments_id(request, id):
    try:
        profile = Profile.objects.get(user=request.user)
        db = Comment.objects.get(id=id, user=request.user)

        score = db.score
        if score > 0.5:
            profile.score -= score
            profile.save()

        db.delete()
        request.session['notification'] = False

        # Check if user has any remaining flagged comments
        remaining_comments = Comment.objects.filter(user=request.user, score__gt=0.5)
        if not remaining_comments.exists():
            return redirect('home')

        return redirect('comments')  # Still has flagged comments

    except Comment.DoesNotExist:
        return redirect('home')


def force_remove_comments_id(request, id):
    try:
        profile = Profile.objects.get(user=request.user)
        db = Comment.objects.get(id=id, user=request.user)

        score = db.score
        if score > 0.5:
            profile.score -= score
            profile.save()

        db.delete()
        request.session['notification'] = False

        # Check if there are any remaining flagged comments
        remaining_comments = Comment.objects.filter(user=request.user, score__gt=0.5)
        if not remaining_comments.exists():
            return redirect('login')  # Redirect if all toxic comments are removed

        return redirect('force-comments')  # Redirect back to force comment review page

    except Comment.DoesNotExist:
        return redirect('login')


def profile_upload(request):
    if request.method == "POST":
        image = request.FILES['img']
        # Ensure profile directory exists
        os.makedirs(os.path.join(os.getcwd(), 'profile'), exist_ok=True)
        
        file_path = os.path.join(os.getcwd(), 'profile', image.name)
        with open(file_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)
        db = Profile.objects.get(user=request.user)
        db.pic = "profile/" + image.name
        db.save()
        request.session['profile'] = "profile/" + image.name
        return redirect('profile')
    return redirect('profile')

def fetch_commants_api(request, id):
    try:
        post = Posts.objects.get(id=id)
    except Posts.DoesNotExist:
        return JsonResponse({"error": "Post not found"}, status=404)

    # Handle deleted post owner
    data = {
        "post": post.image_path,
        "name": post.user.username if post.user else "Deleted User",
    }

    # Fetch comments
    comments = post.comments.all()
    response_list = []
    for c in comments:
        response_list.append({
            "comment": c.text,
            "user": c.user.username if c.user else "Deleted User",
            "score": c.score,
            "id": c.id
        })

    data["comments"] = response_list
    return JsonResponse(data=data, safe=False)

def legal_page(request):
    return render(request, 'legal/legal.html')


from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Posts

@require_POST
@login_required(login_url='login')
def like_post(request, post_id):
    try:
        post = Posts.objects.get(id=post_id)
        user = request.user

        if user in post.likes.all():
            post.likes.remove(user)
            post.like_count = max(post.like_count - 1, 0)  # Prevent negative likes
            liked = False
        else:
            post.likes.add(user)
            post.like_count += 1
            liked = True

        post.save(update_fields=["like_count"])

        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes': post.like_count
        })

    except Posts.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Post not found'}, status=404)

@login_required(login_url='login')
def search_users(request):
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        results = User.objects.filter(username__icontains=query).exclude(id=request.user.id)
    return render(request, "search_results.html", {"results": results, "query": query})

@login_required(login_url='login')
def search_users_api(request):
    query = request.GET.get('q', '').strip()
    if query:
        users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:10]
        results = [{"id": u.id, "username": u.username, "avatar": f"https://ui-avatars.com/api/?name={u.username}&background=random"} for u in users]
        return JsonResponse({"success": True, "users": results})
    return JsonResponse({"success": True, "users": []})

@login_required(login_url='login')
def send_friend_request(request, user_id):
    to_user = User.objects.get(id=user_id)
    # Use update_or_create so that previously rejected requests are reset to 'pending'
    obj, created = FriendRequest.objects.get_or_create(
        from_user=request.user,
        to_user=to_user,
        defaults={'status': 'pending'}
    )
    if not created and obj.status != 'pending':
        # Reset a rejected/accepted request back to pending
        obj.status = 'pending'
        obj.save()
        
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "status": "pending"})
        
    # Support redirect back to wherever the request came from (home suggestions, search, etc.)
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('view_profile', username=to_user.username)

@login_required(login_url='login')
def accept_friend_request(request, request_id):
    try:
        friend_request = FriendRequest.objects.get(id=request_id, to_user=request.user)
    except FriendRequest.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "error": "Not found"})
        return redirect('profile')
    Friend.objects.get_or_create(user=friend_request.from_user, friend=friend_request.to_user)
    Friend.objects.get_or_create(user=friend_request.to_user, friend=friend_request.from_user)
    friend_request.status = 'accepted'
    friend_request.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "status": "accepted"})
        
    # Redirect back to referrer (notifications page, profile page, etc.)
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('profile')

@login_required(login_url='login')
def reject_friend_request(request, request_id):
    try:
        friend_request = FriendRequest.objects.get(id=request_id, to_user=request.user)
    except FriendRequest.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "error": "Not found"})
        return redirect('profile')
    # DELETE the request entirely so the sender can re-send in the future
    friend_request.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "status": "rejected"})
        
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('profile')

@login_required(login_url='login')
def remove_friend(request, user_id):
    friend_user = User.objects.get(id=user_id)
    Friend.objects.filter(user=request.user, friend=friend_user).delete()
    Friend.objects.filter(user=friend_user, friend=request.user).delete()
    # Also delete any friend requests between them so they can follow again
    FriendRequest.objects.filter(
        Q(from_user=request.user, to_user=friend_user) | Q(from_user=friend_user, to_user=request.user)
    ).delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "status": "removed"})
        
    # Redirect back to the viewed user's profile, not own profile
    return redirect('view_profile', username=friend_user.username)

@login_required(login_url='login')
def notifications(request):
    """Show all pending incoming friend requests for the logged-in user."""
    pending_requests = FriendRequest.objects.filter(
        to_user=request.user, status='pending'
    ).select_related('from_user').order_by('-created')
    return render(request, 'notifications.html', {
        'pending_requests': pending_requests,
        'pending_count': pending_requests.count(),
    })

@login_required(login_url='login')
def reels(request):
    # Fetch only Reels
    all_reels = Posts.objects.filter(is_reel=True).order_by('-created')
    return render(request, "reels.html", {"reels": all_reels})


@login_required(login_url='login')
def explore(request):
    """
    Explore page: shows all public regular posts (non-story, non-reel) from all users,
    ordered by newest first. Used for content discovery — similar to Instagram's Explore tab.
    """
    explore_posts = Posts.objects.filter(
        is_story=False, is_reel=False
    ).select_related('user').order_by('-created')
    return render(request, "explore.html", {"explore_posts": explore_posts})


@login_required(login_url='login')
def settings_page(request):
    """Universal Settings: adjust safety scores for any user. Superusers can manage all; regular users see only themselves."""
    is_admin = request.user.is_superuser

    message = None
    if request.method == 'POST':
        target_user_id = request.POST.get('user_id')
        action = request.POST.get('action')          # 'increase', 'decrease', 'reset', 'set'
        amount = float(request.POST.get('amount', 1.0))

        try:
            target_user = User.objects.get(id=target_user_id)
            # Non-admins can only edit their own score
            if not is_admin and target_user != request.user:
                return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

            profile_obj, _ = Profile.objects.get_or_create(user=target_user)

            if action == 'increase':
                profile_obj.score += amount
            elif action == 'decrease':
                profile_obj.score = max(0.0, profile_obj.score - amount)
            elif action == 'reset':
                profile_obj.score = 0.0
            elif action == 'set':
                profile_obj.score = max(0.0, amount)
            elif action == 'remove_ban':
                profile_obj.ban_until = None
                profile_obj.ban_level = 1  # Reset escalation for testing
                profile_obj.score = 0.0

            profile_obj.save()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'score': round(profile_obj.score, 2),
                                     'username': target_user.username, 'action': action})

            message = f"Score updated for {target_user.username}."
        except User.DoesNotExist:
            message = "User not found."

    # Build user list
    if is_admin:
        users = User.objects.all().order_by('username')
    else:
        users = [request.user]

    user_data = []
    for u in users:
        p = Profile.objects.filter(user=u).first()
        is_banned = bool(p and p.ban_until and p.ban_until > timezone.now())
        user_data.append({
            'id': u.id,
            'username': u.username,
            'score': round(p.score, 2) if p else 0.0,
            'is_superuser': u.is_superuser,
            'banned': is_banned,
            'ban_until_display': (p.ban_until.strftime('%b %d, %H:%M') if is_banned else ''),
            'ban_level': p.ban_level if p else 1,
        })

    return render(request, 'settings.html', {
        'user_data': user_data,
        'is_admin': is_admin,
        'message': message,
    })


@login_required(login_url='login')
def ban_status_api(request):
    """Lightweight API: returns the logged-in user's ban status as JSON.
    Called by base.html JS on every page load to enforce the ban overlay universally."""
    try:
        profile = Profile.objects.get(user=request.user)
        if profile.ban_until and profile.ban_until > timezone.now():
            return JsonResponse({
                'banned': True,
                'ban_until': profile.ban_until.isoformat(),
                'ban_level': profile.ban_level,
                'ban_hours': profile.ban_level * 4,
                'ban_steps': [i * 4 for i in range(1, 8)],
            })
    except Profile.DoesNotExist:
        pass
    return JsonResponse({'banned': False})
