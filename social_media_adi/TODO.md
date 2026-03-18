# Friends Functionality Fix - TODO

## Steps

- [x] Analyze project files and identify all bugs
- [x] Fix `views.py` - send_friend_request (handle rejected requests with get_or_create + reset)
- [x] Fix `views.py` - reject_friend_request (delete request instead of status='rejected')
- [x] Fix `views.py` - remove_friend (redirect to viewed user's profile)
- [x] Fix `views.py` - accept_friend_request (redirect to referrer via ?next or HTTP_REFERER)
- [x] Add `views.py` - notifications view
- [x] Fix `urls.py` - add notifications URL
- [x] Fix `profile.html` - add incoming requests section on own profile
- [x] Fix `home.html` - fix Follow button in suggestions (now links to send_friend_request)
- [x] Fix `base.html` - connect notification bell + add red badge via context processor
- [x] Create `notifications.html` - Django-backed notifications page
- [x] Create `app/context_processors.py` - pending_friend_requests count injected globally
- [x] Fix `settings.py` - register context processor

## All Done ✅
