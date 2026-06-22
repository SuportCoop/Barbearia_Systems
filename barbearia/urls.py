from django.urls import path
from django.views.generic import TemplateView

from .views import (
    AssignPlanView,
    BarbeiroDashboardView,
    BookingCancelView,
    BookingCreateView,
    BarberAvailabilityView,
    BarberBookingCreateView,
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
    BarberScheduleUpdateView,
    ClienteDashboardView,
    MarkBookingCompleteView,
    MarkNotificationReadView,
    PlanCreateView,
    PlanUpdateView,
    SeedDatabaseView,
    UserLoginView,
    UserLogoutView,
    UserRegisterView,
    CustomPasswordChangeView,
    ProductReserveView,
    CompleteProductReservationView,
    CancelProductReservationView,
    DeveloperBarbershopCreateView,
    DeveloperBarbershopUpdateView,
    DeveloperBarbershopDeleteView,
)

urlpatterns = [
    # Auth
    path("", UserLoginView.as_view(), name="login"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", UserRegisterView.as_view(), name="register"),
    path("alterar-senha/", CustomPasswordChangeView.as_view(), name="alterar_senha"),
    path("dashboard/", DashboardRedirectView.as_view(), name="dashboard_redirect"),

    # Portal do Cliente
    path("cliente/dashboard/", ClienteDashboardView.as_view(), name="cliente_dashboard"),
    path("cliente/agendar/", BookingCreateView.as_view(), name="agendar"),
    path("cliente/agendamento/<int:pk>/cancelar/", BookingCancelView.as_view(), name="cancelar_agendamento"),
    path("cliente/notificacoes/ler/", MarkNotificationReadView.as_view(), name="marcar_notificacoes_lidas"),
    path("cliente/produto/<int:pk>/reservar/", ProductReserveView.as_view(), name="reservar_produto"),
    path("cliente/reserva/<int:pk>/cancelar/", CancelProductReservationView.as_view(), name="cliente_cancelar_reserva"),

    # Portal do Barbeiro
    path("barbeiro/dashboard/", BarbeiroDashboardView.as_view(), name="barbeiro_dashboard"),
    path("barbeiro/agendar/", BarberBookingCreateView.as_view(), name="barbeiro_agendar"),
    path("barbeiro/agendar/<int:client_id>/", BarberBookingCreateView.as_view(), name="barbeiro_agendar_cliente"),
    path("barbeiro/plano/novo/", PlanCreateView.as_view(), name="criar_plano"),
    path("barbeiro/plano/<int:pk>/editar/", PlanUpdateView.as_view(), name="editar_plano"),
    path("barbeiro/usuario/novo/", BarbeiroUserCreateView.as_view(), name="barbeiro_criar_usuario"),
    path("barbeiro/cliente/<int:pk>/plano/", AssignPlanView.as_view(), name="atribuir_plano"),
    path("barbeiro/cliente/<int:pk>/editar/", BarberClientProfileUpdateView.as_view(), name="editar_cliente_perfil"),
    path("barbeiro/agendamento/<int:pk>/editar/", BarberBookingUpdateView.as_view(), name="editar_agendamento"),
    path("barbeiro/agendamento/<int:pk>/concluir/", MarkBookingCompleteView.as_view(), name="concluir_agendamento"),
    path("barbeiro/reserva/<int:pk>/concluir/", CompleteProductReservationView.as_view(), name="concluir_reserva"),
    path("barbeiro/reserva/<int:pk>/cancelar/", CancelProductReservationView.as_view(), name="barbeiro_cancelar_reserva"),
    path("barbeiro/configurar-agenda/", BarberScheduleUpdateView.as_view(), name="configurar_agenda"),

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
    path("desenvolvedor/barbearia/nova/", DeveloperBarbershopCreateView.as_view(), name="criar_barbearia"),
    path("desenvolvedor/barbearia/<int:pk>/editar/", DeveloperBarbershopUpdateView.as_view(), name="editar_barbearia"),
    path("desenvolvedor/barbearia/<int:pk>/deletar/", DeveloperBarbershopDeleteView.as_view(), name="deletar_barbearia"),
    path("desenvolvedor/reserva/<int:pk>/cancelar/", CancelProductReservationView.as_view(), name="desenvolvedor_cancelar_reserva"),
    path("desenvolvedor/seed/", SeedDatabaseView.as_view(), name="seed_database"),

    # Configuração PWA servida a partir do escopo raiz
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
    # API
    path("api/horarios-disponiveis/", BarberAvailabilityView.as_view(), name="horarios_disponiveis"),
]
