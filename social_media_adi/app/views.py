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
    
    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count() if request.user.is_authenticated else 0
    return render(request, "home.html", {
        "db": db,
        "stories": stories,
        "suggestions": suggestions,
        "issues": issues,
        "toxic_blocked": toxic_blocked,
        "unread_messages_count": unread_messages_count
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
    # List all friends (users except self)
    users = User.objects.exclude(id=request.user.id)
    user_profiles = {u.id: Profile.objects.filter(user=u).first() for u in users}
    # Unread message count per user
    unread_counts = {u.id: Message.objects.filter(sender=u, receiver=request.user, is_read=False).count() for u in users}
    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count() if request.user.is_authenticated else 0
    return render(request, "chat_list.html", {"users": users, "user_profiles": user_profiles, "unread_counts": unread_counts, "unread_messages_count": unread_messages_count})

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
    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count() if request.user.is_authenticated else 0
    return render(request, "chat_detail.html", {"friend": friend, "friend_profile": friend_profile, "messages": messages, "unread_messages_count": unread_messages_count})

@login_required(login_url='login')
def send_message(request, user_id):
    if request.method == "POST":
        friend = User.objects.get(id=user_id)
        text = request.POST.get("text", "").strip()
        if text:
            score = get_toxicity_score(text)
            Message.objects.create(sender=request.user, receiver=friend, text=text, score=score)
            
            if score > 0.5:
                profile = Profile.objects.get(user=request.user)
                profile.score += score
                profile.save()
                # We could add a notification here as well
        return redirect('chat-detail', user_id=user_id)
from django.utils import timezone

def add_comment(request, id):
    if request.method == 'POST':
        comment_text = request.POST.get('comment', '').strip()
        if not comment_text:
            return redirect('home')  # Or show error if empty comment

        if request.user.is_anonymous:
            return redirect('login')

        profile, created = Profile.objects.get_or_create(user=request.user)

        if profile.score > 5:
            print("User is blocked due to high score")
            request.session['issues'] = True
            return redirect('home')

        sentiment_score = get_toxicity_score(comment_text)
        if sentiment_score > 0.5:
            request.session['notification'] = True

        # Get the post
        post_instance = Posts.objects.get(id=id)

        # Save the comment
        comment = Comment.objects.create(
            user=request.user,
            text=comment_text,
            score=sentiment_score,
            post=post_instance
        )
        post_instance.comments.add(comment)
        post_instance.save()

        # If toxic comment, increase profile score and create report
        if sentiment_score > 0.5:
            profile.score += sentiment_score
            profile.save()

            CommentReport.objects.create(
                comment=comment,
                commenter=request.user,
                post=post_instance,
                post_owner=post_instance.user,
                comment_text=comment_text,
                score=sentiment_score,
                timestamp=timezone.now()
            )

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
            return redirect('home')
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
    except Comment.DoesNotExist:
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

                if profile.score > 5:
                    warning_message = f"⚠️ Hi {user.username}, your profile score is {profile.score:.2f}. Please remove flagged comments before proceeding."

                    return render(request, "login.html", {
                        "warning": warning_message
                    })

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
        
    posts = Posts.objects.filter(user=viewed_user).order_by('-id')
    
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

    return render(request, "profile.html", {
        "viewed_user": viewed_user,
        "profile": profile_obj, 
        'db': posts,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_self': is_self,
        'is_friend': is_friend,
        'sent_request': sent_request,
        'received_request': received_request,
        'incoming_requests': incoming_requests
    })

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
@login_required
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
        return redirect('profile')
    Friend.objects.get_or_create(user=friend_request.from_user, friend=friend_request.to_user)
    Friend.objects.get_or_create(user=friend_request.to_user, friend=friend_request.from_user)
    friend_request.status = 'accepted'
    friend_request.save()
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
        return redirect('profile')
    # DELETE the request entirely so the sender can re-send in the future
    friend_request.delete()
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
