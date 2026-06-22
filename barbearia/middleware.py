from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class ForcePasswordChangeMiddleware:
    """
    Middleware que força os usuários a alterarem sua senha se a
    flag must_change_password estiver definida em seu perfil.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                allowed_paths = [
                    reverse('logout'),
                    reverse('alterar_senha'),
                ]
            except NoReverseMatch:
                allowed_paths = []

            path = request.path

            # Permite arquivos estáticos e verifica os caminhos permitidos
            if (
                path not in allowed_paths
                and not path.startswith('/static/')
                and not path.startswith('/media/')
            ):
                try:
                    profile = request.user.profile
                    if profile.must_change_password:
                        return redirect('alterar_senha')
                except Exception:
                    pass

        response = self.get_response(request)
        return response
