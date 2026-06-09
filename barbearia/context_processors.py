def notifications_processor(request):
    """
    Context processor to make unread notifications globally available
    in all templates for authenticated users.
    """
    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False)
        return {
            "unread_notifications": unread,
            "unread_notifications_count": unread.count(),
        }
    return {
        "unread_notifications": [],
        "unread_notifications_count": 0,
    }
