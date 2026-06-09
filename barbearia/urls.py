from django.urls import path
from django.views.generic import TemplateView

from .views import (AssignPlanView,
    BarbeiroDashboardView,
    BookingCancelView,
    BookingCreateView,
    DashboardRedirectView,
    DesenvolvedorDashboardView,
    DeveloperProductCreateView,
    DeveloperProductDeleteView,
    DeveloperProductUpdateView,
    DeveloperServiceCreateView,
    DeveloperServiceDeleteView,
    DeveloperServiceUpdateView,
    DeveloperUserCreateView,
    DeveloperUserDeleteView,
    DeveloperUserUpdateView,
    BarbeiroUserCreateView,
    BarberClientProfileUpdateView,
    BarberBookingUpdateView,
    ClienteDashboardView,
    MarkBookingCompleteView,
    MarkNotificationReadView,
    PlanCreateView,
    PlanUpdateView,
    SeedDatabaseView,
    UserLoginView,
    UserLogoutView,
    UserRegisterView,
)

urlpatterns = [
    # Auth
    path("", UserLoginView.as_view(), name="login"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", UserRegisterView.as_view(), name="register"),
    path("dashboard/", DashboardRedirectView.as_view(), name="dashboard_redirect"),

    # Portal do Cliente
    path("cliente/dashboard/", ClienteDashboardView.as_view(), name="cliente_dashboard"),
    path("cliente/agendar/", BookingCreateView.as_view(), name="agendar"),
    path("cliente/agendamento/<int:pk>/cancelar/", BookingCancelView.as_view(), name="cancelar_agendamento"),
    path("cliente/notificacoes/ler/", MarkNotificationReadView.as_view(), name="marcar_notificacoes_lidas"),

    # Portal do Barbeiro
    path("barbeiro/dashboard/", BarbeiroDashboardView.as_view(), name="barbeiro_dashboard"),
    path("barbeiro/plano/novo/", PlanCreateView.as_view(), name="criar_plano"),
    path("barbeiro/plano/<int:pk>/editar/", PlanUpdateView.as_view(), name="editar_plano"),
    path("barbeiro/usuario/novo/", BarbeiroUserCreateView.as_view(), name="barbeiro_criar_usuario"),
    path("barbeiro/cliente/<int:pk>/plano/", AssignPlanView.as_view(), name="atribuir_plano"),
    path("barbeiro/cliente/<int:pk>/editar/", BarberClientProfileUpdateView.as_view(), name="editar_cliente_perfil"),
    path("barbeiro/agendamento/<int:pk>/editar/", BarberBookingUpdateView.as_view(), name="editar_agendamento"),
    path("barbeiro/agendamento/<int:pk>/concluir/", MarkBookingCompleteView.as_view(), name="concluir_agendamento"),

    # Portal do Desenvolvedor
    path("desenvolvedor/dashboard/", DesenvolvedorDashboardView.as_view(), name="desenvolvedor_dashboard"),
    path("desenvolvedor/produto/novo/", DeveloperProductCreateView.as_view(), name="criar_produto"),
    path("desenvolvedor/produto/<int:pk>/editar/", DeveloperProductUpdateView.as_view(), name="editar_produto"),
    path("desenvolvedor/produto/<int:pk>/deletar/", DeveloperProductDeleteView.as_view(), name="deletar_produto"),
    path("desenvolvedor/servico/novo/", DeveloperServiceCreateView.as_view(), name="criar_servico"),
    path("desenvolvedor/servico/<int:pk>/editar/", DeveloperServiceUpdateView.as_view(), name="editar_servico"),
    path("desenvolvedor/servico/<int:pk>/deletar/", DeveloperServiceDeleteView.as_view(), name="deletar_servico"),
    path("desenvolvedor/usuario/novo/", DeveloperUserCreateView.as_view(), name="criar_usuario"),
    path("desenvolvedor/usuario/<int:pk>/editar/", DeveloperUserUpdateView.as_view(), name="editar_usuario"),
    path("desenvolvedor/usuario/<int:pk>/deletar/", DeveloperUserDeleteView.as_view(), name="deletar_usuario"),
    path("desenvolvedor/seed/", SeedDatabaseView.as_view(), name="seed_database"),

    # PWA Configuration served from root scope
    path(
        "manifest.json",
        TemplateView.as_view(template_name="barbearia/manifest.json", content_type="application/json"),
        name="manifest_json"
    ),
    path(
        "sw.js",
        TemplateView.as_view(template_name="barbearia/sw.js", content_type="application/javascript"),
        name="sw_js"
    ),
]
