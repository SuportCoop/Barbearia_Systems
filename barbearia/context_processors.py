def notifications_processor(request):
    """
    Context processor para disponibilizar notificações não lidas globalmente
    em todos os templates para usuários autenticados.
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
