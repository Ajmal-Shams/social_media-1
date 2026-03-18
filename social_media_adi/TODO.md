# Bug Fix TODO List

## Fix 1 — Reels: count increases in posts but doesn't appear in reels section
- [x] views.py → updated `profile()` to separate regular_posts, reels_posts, pass both + counts
- [x] profile.html → fixed post count (posts_count), added reel count badge on Reels tab, made tabs functional with JS (switchTab)

## Fix 2 — Unable to view stories
- [x] home.html → added fullscreen story viewer overlay with progress bar, auto-close after 5s, video/image detection, close on backdrop click

## Fix 3 — Reels black screen
- [x] reels.html → removed hardcoded `type="video/mp4"`, switched to `src` attribute directly on `<video>` (browser auto-detects MIME type), added mute/unmute toggle button

## Fix 4 — Edit Profile not working
- [x] views.py → added `edit_profile()` view (updates first_name, last_name, bio)
- [x] urls.py → added `path('edit-profile/', edit_profile, name='edit_profile')`
- [x] profile.html → added Edit Profile modal (first name, last name, bio, profile picture), wired "Edit Profile" button to open modal

## Fix 5 — Explore (compass) not working
- [x] views.py → added `explore()` view (fetches all non-story, non-reel posts)
- [x] urls.py → added `path('explore/', explore, name='explore')`
- [x] explore.html → rewritten as proper Django template extending base.html with masonry grid, post detail modals, like functionality
- [x] base.html → fixed compass href from `#` to `{% url 'explore' %}` with active state

## Fix 6 — Flagged messages still reach receiver
- [x] views.py → `send_message()`: moved toxicity check BEFORE `Message.objects.create()`. If `score > 0.5`, message is blocked (not saved), profile score is penalized, `request.session['msg_flagged'] = True` is set, and user is redirected without delivering the message.
- [x] views.py → `chat_detail()`: pops `msg_flagged` session flag and passes it to template.
- [x] chat_detail.html → added dismissible red alert banner shown when `msg_flagged` is True: "Message Blocked: Your message was flagged as potentially harmful and was not sent."

## Fix 7 — New messages not appearing at top in chat list
- [x] views.py → `chat_list()`: fetches latest message timestamp per user conversation, sorts users by most recent message descending (users with no messages go to bottom using epoch fallback `dt(1970,1,1,tzinfo=timezone.utc)`).

## Fix 8 — Likes not working
- [x] views.py → `like_post()`: changed `@login_required` to `@login_required(login_url='login')` to ensure correct redirect URL.
- [x] home.html → `likePost()`: removed unnecessary `Content-Type: application/json` header, added `r.ok` check before JSON parse, added `.catch()` error handler for silent failure debugging.

## Fix 9 — Profile Reels thumbnails gray/blank
- [x] profile.html → changed `preload="none"` → `preload="metadata"` on reels grid videos
- [x] base.html → added CSS for `.profile-grid` (responsive grid), `.grid-item` (1:1 aspect ratio), `.item-overlay`, video styling

## All fixes complete ✅

