import decimal
from datetime import date
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    RedirectView,
    TemplateView,
    UpdateView,
    View,
)
from django.http import JsonResponse
from datetime import datetime, time as datetime_time, timedelta
from barbearia.forms import AssignPlanForm,BookingForm,BarberBookingForm,ClientRegistrationForm,DeveloperUserForm,BarberClientProfileForm,ProductForm,ServiceForm, SubscriptionPlanForm, BarberClientForm, BarbershopForm, BarberScheduleForm
from .models import (Barbershop, Booking, Notification, Product, Profile, Service, SubscriptionPlan, ProductReservation)


class UserLoginView(LoginView):
    """
    View de login customizada.
    """
    template_name = "barbearia/login.html"

    def get_success_url(self):
        return reverse_lazy("dashboard_redirect")


class UserRegisterView(CreateView):
    """
    View de cadastro para novos clientes.
    """
    form_class = ClientRegistrationForm
    template_name = "barbearia/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Cadastro realizado com sucesso! Faça login para continuar."
        )
        return response


class UserLogoutView(View):
    """
    View de logout que lida com requisições simples de GET/POST.
    """
    def get(self, request, *args, **kwargs):
        from django.contrib.auth import logout
        logout(request)
        messages.success(request, "Você saiu do sistema.")
        return redirect("login")

    def post(self, request, *args, **kwargs):
        from django.contrib.auth import logout
        logout(request)
        messages.success(request, "Você saiu do sistema.")
        return redirect("login")


class DashboardRedirectView(LoginRequiredMixin, RedirectView):
    """
    Redireciona o usuário para o painel específico de sua função.
    """
    pattern_name = "cliente_dashboard"

    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        # Garante que o perfil existe
        profile, created = Profile.objects.get_or_create(user=user)
        if profile.role == "BARBEIRO":
            return reverse_lazy("barbeiro_dashboard")
        elif profile.role == "DESENVOLVEDOR":
            return reverse_lazy("desenvolvedor_dashboard")
        return reverse_lazy("cliente_dashboard")


# ==========================================
# VIEWS DO PORTAL DO CLIENTE
# ==========================================

class ClienteDashboardView(LoginRequiredMixin, TemplateView):
    """
    Painel para clientes visualizarem agendamentos, planos e notificações.
    """
    template_name = "barbearia/cliente_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = Profile.objects.get_or_create(user=user)

        # Força a função CLIENTE se o usuário fizer login sem um perfil definido
        if profile.role not in ["CLIENTE", "BARBEIRO", "DESENVOLVEDOR"]:
            profile.role = "CLIENTE"
            profile.save()

        today = timezone.localdate()

        context["profile"] = profile
        context["upcoming_bookings"] = Booking.objects.filter(
            client=user,
            date__gte=today,
            status="AGENDADO"
        ).order_by("date", "time")
        context["past_bookings"] = Booking.objects.filter(
            client=user
        ).exclude(
            date__gte=today,
            status="AGENDADO"
        ).order_by("-date", "-time")[:5]
        context["notifications"] = Notification.objects.filter(
            client=user
        ).order_by("-created_at")[:10]
        barbershop = profile.barbershop
        if barbershop:
            context["products"] = Product.objects.filter(barbershop=barbershop, stock__gt=0)
        else:
            context["products"] = Product.objects.filter(stock__gt=0)[:4]
        context["product_reservations"] = ProductReservation.objects.filter(
            client=user
        ).select_related("product").order_by("-created_at")
        return context


def get_available_slots(barber, select_date, service_duration=30, exclude_booking_id=None):
    """
    Calcula os horários de 30 minutos disponíveis para um barbeiro em uma data específica,
    considerando agendamentos existentes, a duração do serviço e o horário de trabalho/pausa do barbeiro.
    """
    def parse_time_if_str(t):
        if isinstance(t, str):
            try:
                return datetime.strptime(t, "%H:%M:%S").time()
            except ValueError:
                return datetime.strptime(t, "%H:%M").time()
        return t

    # Recupera o expediente e pausa do barbeiro (com fallback para 08:00 às 20:00)
    try:
        profile = barber.profile
        work_start_time = parse_time_if_str(profile.work_start) or datetime_time(8, 0)
        work_end_time = parse_time_if_str(profile.work_end) or datetime_time(20, 0)
        break_start_time = parse_time_if_str(profile.break_start)
        break_end_time = parse_time_if_str(profile.break_end)
    except Exception:
        work_start_time = datetime_time(8, 0)
        work_end_time = datetime_time(20, 0)
        break_start_time = None
        break_end_time = None

    all_slots = []
    current = datetime.combine(select_date, work_start_time)
    if timezone.is_naive(current):
        current = timezone.make_aware(current)
    end = datetime.combine(select_date, work_end_time)
    if timezone.is_naive(end):
        end = timezone.make_aware(end)
        
    while current < end:
        all_slots.append(current)
        current += timedelta(minutes=30)
        
    # Obtém agendamentos ativos para este barbeiro nesta data
    bookings = Booking.objects.filter(
        barber=barber,
        date=select_date,
        status="AGENDADO"
    )
    if exclude_booking_id:
        bookings = bookings.exclude(id=exclude_booking_id)
        
    # Calcula os intervalos de horários bloqueados/ocupados
    blocked_ranges = []
    for b in bookings:
        b_start = datetime.combine(select_date, b.time)
        if timezone.is_naive(b_start):
            b_start = timezone.make_aware(b_start)
        b_end = b_start + timedelta(minutes=b.service.duration_minutes)
        blocked_ranges.append((b_start, b_end))

    # Adiciona o horário de pausa às faixas bloqueadas
    if break_start_time and break_end_time:
        brk_start = datetime.combine(select_date, break_start_time)
        if timezone.is_naive(brk_start):
            brk_start = timezone.make_aware(brk_start)
        brk_end = datetime.combine(select_date, break_end_time)
        if timezone.is_naive(brk_end):
            brk_end = timezone.make_aware(brk_end)
        blocked_ranges.append((brk_start, brk_end))
        
    # Filtra os slots de tempo
    available_slots = []
    now_local = timezone.localtime(timezone.now())
    
    for slot in all_slots:
        # Se a data for hoje, o horário deve ser no futuro
        if select_date == now_local.date() and slot <= now_local:
            continue
            
        # Verifica sobreposição de horário
        is_blocked = False
        for b_start, b_end in blocked_ranges:
            if b_start <= slot < b_end:
                is_blocked = True
                break
                
        # Verifica se a duração do serviço cabe e não gera sobreposição
        if not is_blocked:
            slot_end = slot + timedelta(minutes=service_duration)
            if slot_end > end:
                is_blocked = True
            else:
                for b_start, b_end in blocked_ranges:
                    if max(slot, b_start) < min(slot_end, b_end):
                        is_blocked = True
                        break
                        
        if not is_blocked:
            available_slots.append(slot.time().strftime("%H:%M"))
            
    return available_slots


class BarberAvailabilityView(View):
    """
    Endpoint AJAX para recuperar horários disponíveis.
    """
    def get(self, request, *args, **kwargs):
        barber_id = request.GET.get("barber_id")
        date_str = request.GET.get("date")
        service_id = request.GET.get("service_id")
        exclude_booking_id = request.GET.get("exclude_booking_id")
        
        if not barber_id or not date_str:
            return JsonResponse({"slots": []})
            
        try:
            barber = User.objects.get(id=barber_id, profile__role="BARBEIRO")
        except User.DoesNotExist:
            return JsonResponse({"slots": []})
            
        try:
            select_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"slots": []})
            
        service_duration = 30
        if service_id:
            try:
                service = Service.objects.get(id=service_id)
                service_duration = service.duration_minutes
            except Service.DoesNotExist:
                pass
                
        try:
            exclude_booking_id = int(exclude_booking_id) if exclude_booking_id else None
        except ValueError:
            exclude_booking_id = None
            
        slots = get_available_slots(
            barber=barber,
            select_date=select_date,
            service_duration=service_duration,
            exclude_booking_id=exclude_booking_id
        )
        return JsonResponse({"slots": slots})


class BarberBookingCreateView(LoginRequiredMixin, CreateView):
    """
    Permite que um barbeiro ou desenvolvedor crie um agendamento em nome de um cliente.
    """
    model = Booking
    form_class = BarberBookingForm
    template_name = "barbearia/agendar.html"
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
        
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["barber_user"] = self.request.user
        return kwargs
        
    def get_initial(self):
        initial = super().get_initial()
        client_id = self.request.GET.get("client_id") or self.kwargs.get("client_id")
        if client_id:
            try:
                initial["client"] = User.objects.get(id=client_id, profile__role="CLIENTE")
            except User.DoesNotExist:
                pass
        if self.request.user.profile.role == "BARBEIRO":
            initial["barber"] = self.request.user
        return initial

    def get_success_url(self):
        if self.request.user.profile.role == "DESENVOLVEDOR":
            return reverse_lazy("desenvolvedor_dashboard")
        return reverse_lazy("barbeiro_dashboard")

    def form_valid(self, form):
        booking = form.save(commit=False)
        
        # Salva a barbearia do perfil do barbeiro
        if booking.barber.profile.barbershop:
            booking.barbershop = booking.barber.profile.barbershop
            
        booking.save()
        
        # Cria as notificações no sistema
        Notification.objects.create(
            client=booking.client,
            message=(
                f"O barbeiro {self.request.user.get_full_name() or self.request.user.username} "
                f"agendou um horário para você no dia {booking.date.strftime('%d/%m/%Y')} "
                f"às {booking.time.strftime('%H:%M')} com {booking.barber.get_full_name() or booking.barber.username}."
            )
        )
        Notification.objects.create(
            client=booking.barber,
            message=(
                f"Você agendou um horário para o cliente {booking.client.get_full_name() or booking.client.username} "
                f"no dia {booking.date.strftime('%d/%m/%Y')} às {booking.time.strftime('%H:%M')}."
            )
        )
        
        messages.success(
            self.request,
            f"Agendamento para {booking.client.get_full_name() or booking.client.username} realizado com sucesso!"
        )
        return super().form_valid(form)


class BookingCreateView(LoginRequiredMixin, CreateView):
    """
    Permite que os clientes realizem um agendamento.
    """
    model = Booking
    form_class = BookingForm
    template_name = "barbearia/agendar.html"
    success_url = reverse_lazy("cliente_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        booking = form.save(commit=False)
        booking.client = self.request.user

        # Validação: Verifica reserva duplicada
        duplicate = Booking.objects.filter(
            barber=booking.barber,
            date=booking.date,
            time=booking.time,
            status="AGENDADO"
        ).exists()

        if duplicate:
            form.add_error(
                None,
                "Este barbeiro já possui um agendamento neste dia e horário."
            )
            return self.form_invalid(form)

        booking.save()

        # Cria notificação no sistema para o Cliente
        Notification.objects.create(
            client=self.request.user,
            message=(
                f"Agendamento confirmado para {booking.date.strftime('%d/%m/%Y')} "
                f"às {booking.time.strftime('%H:%M')} com {booking.barber.get_full_name() or booking.barber.username}."
            )
        )

        # Cria notificação para o Barbeiro
        Notification.objects.create(
            client=booking.barber,
            message=(
                f"O cliente {self.request.user.get_full_name() or self.request.user.username} "
                f"agendou um corte para o dia {booking.date.strftime('%d/%m/%Y')} "
                f"às {booking.time.strftime('%H:%M')}."
            )
        )

        messages.success(self.request, "Corte agendado com sucesso!")
        return super().form_valid(form)


class BookingCancelView(LoginRequiredMixin, View):
    """
    Cancela um agendamento (marca o status como CANCELADO).
    """
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        # Permite cancelamento apenas se for o proprietário ou equipe
        if booking.client != request.user:
            if request.user.profile.role == "BARBEIRO" and booking.barber != request.user:
                raise PermissionDenied
            elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
                raise PermissionDenied

        booking.status = "CANCELADO"
        booking.save()

        # Notifica Cliente e Barbeiro com base em quem realizou o cancelamento
        if request.user == booking.client:
            Notification.objects.create(
                client=booking.barber,
                message=(
                    f"O cliente {request.user.get_full_name() or request.user.username} "
                    f"cancelou o agendamento do dia {booking.date.strftime('%d/%m/%Y')} "
                    f"às {booking.time.strftime('%H:%M')}."
                )
            )
            Notification.objects.create(
                client=booking.client,
                message=(
                    f"Você cancelou seu agendamento do dia {booking.date.strftime('%d/%m/%Y')} "
                    f"às {booking.time.strftime('%H:%M')}."
                )
            )
        else:
            Notification.objects.create(
                client=booking.client,
                message=(
                    f"O barbeiro {request.user.get_full_name() or request.user.username} "
                    f"cancelou seu agendamento do dia {booking.date.strftime('%d/%m/%Y')} "
                    f"às {booking.time.strftime('%H:%M')}."
                )
            )
            Notification.objects.create(
                client=booking.barber,
                message=(
                    f"Você cancelou o agendamento do dia {booking.date.strftime('%d/%m/%Y')} "
                    f"às {booking.time.strftime('%H:%M')} de {booking.client.get_full_name() or booking.client.username}."
                )
            )

        messages.success(request, "Agendamento cancelado com sucesso!")

        # Redireciona de volta para onde foi chamado
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        return redirect("dashboard_redirect")


class MarkNotificationReadView(LoginRequiredMixin, View):
    """
    Marca todas as notificações do usuário como lidas.
    """
    def post(self, request, *args, **kwargs):
        Notification.objects.filter(client=request.user, is_read=False).update(is_read=True)
        return redirect("cliente_dashboard")


# ==========================================
# VIEWS DO PORTAL DO BARBEIRO
# ==========================================

class BarbeiroDashboardView(LoginRequiredMixin, TemplateView):
    """
    Painel de controle exibindo estatísticas e gerenciamento para barbeiros.
    """
    template_name = "barbearia/barbeiro_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        barber = self.request.user
        today = timezone.localdate()

        # Contagem de clientes na carteira
        portfolio_clients = Profile.objects.filter(
            assigned_barber=barber,
            role="CLIENTE"
        )
        context["portfolio_clients"] = portfolio_clients

        # Agendamentos do dia
        today_bookings = Booking.objects.filter(
            barber=barber,
            date=today
        ).order_by("time")
        context["today_bookings"] = today_bookings

        # Clientes atendidos hoje (Concluídos)
        context["served_today_count"] = today_bookings.filter(
            status="CONCLUIDO"
        ).count()

        # Faturamento do Dia (Soma dos serviços concluídos hoje)
        today_completed_bookings = today_bookings.filter(status="CONCLUIDO")
        today_completed_billing = today_completed_bookings.aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")
        context["today_completed_billing"] = today_completed_billing

        # Faturamento (Cálculo mensal)
        first_day_of_month = today.replace(day=1)
        completed_this_month = Booking.objects.filter(
            barber=barber,
            date__gte=first_day_of_month,
            date__lte=today,
            status="CONCLUIDO"
        )
        # Soma os preços dos serviços prestados
        service_billing = completed_this_month.aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")

        # Faturamento das assinaturas ativas
        active_subscribers = portfolio_clients.filter(
            plan_active=True,
            plan__isnull=False
        )
        plan_billing = active_subscribers.aggregate(
            total=Sum("plan__price")
        )["total"] or decimal.Decimal("0.00")

        context["monthly_revenue"] = service_billing + plan_billing
        context["service_billing"] = service_billing
        context["plan_billing"] = plan_billing

        # Contagem de clientes mensalistas (Assinantes ativos na carteira do barbeiro)
        context["mensalistas_count"] = active_subscribers.count()

        # Faturamento da Semana (Serviços concluídos nesta semana a partir de segunda-feira)
        start_of_week = today - timezone.timedelta(days=today.weekday())
        completed_this_week = Booking.objects.filter(
            barber=barber,
            date__gte=start_of_week,
            date__lte=today,
            status="CONCLUIDO"
        )
        context["weekly_revenue"] = completed_this_week.aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")

        # Planos de assinatura criados por este barbeiro ou desenvolvedores
        context["plans"] = SubscriptionPlan.objects.all()

        # Reservas de produtos pendentes para a barbearia do barbeiro
        barbershop = barber.profile.barbershop
        if barbershop:
            context["pending_reservations"] = ProductReservation.objects.filter(
                product__barbershop=barbershop,
                status="PENDENTE"
            ).select_related("client", "product").order_by("-created_at")
        else:
            context["pending_reservations"] = ProductReservation.objects.filter(
                status="PENDENTE"
            ).select_related("client", "product").order_by("-created_at")

        return context


class PlanCreateView(LoginRequiredMixin, CreateView):
    """
    Permite que um barbeiro crie um plano de assinatura.
    """
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    template_name = "barbearia/plano_form.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        plan = form.save(commit=False)
        plan.created_by = self.request.user
        plan.save()
        messages.success(self.request, "Plano de assinatura criado!")
        return super().form_valid(form)


class PlanUpdateView(LoginRequiredMixin, UpdateView):
    """
    Permite que um barbeiro edite um plano de assinatura.
    """
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    template_name = "barbearia/plano_form.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Plano de assinatura atualizado!")
        return super().form_valid(form)


class AssignPlanView(LoginRequiredMixin, UpdateView):
    """
    Permite atribuir um plano e data de vencimento ao perfil de um cliente.
    """
    model = Profile
    form_class = AssignPlanForm
    template_name = "barbearia/atribuir_plano.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def dispatch(self, request, *args, **kwargs):
        profile = self.get_object()
        if request.user.profile.role == "BARBEIRO" and profile.assigned_barber != request.user:
            raise PermissionDenied
        elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        profile = form.save()
        # Adiciona notificação ao cliente sobre a alteração do plano
        if profile.plan:
            status_text = "ativo" if profile.plan_active else "pendente"
            Notification.objects.create(
                client=profile.user,
                message=(
                    f"Seu perfil foi atualizado para o plano '{profile.plan.name}' "
                    f"(Mensalidade: R$ {profile.plan.price}). Status: {status_text}."
                )
            )
        messages.success(self.request, f"Plano de {profile.user.get_full_name() or profile.user.username} atualizado!")
        return super().form_valid(form)


class MarkBookingCompleteView(LoginRequiredMixin, View):
    """
    Marca um agendamento como concluído.
    """
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        if request.user.profile.role == "BARBEIRO" and booking.barber != request.user:
            raise PermissionDenied
        elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied

        booking.status = "CONCLUIDO"
        booking.save()

        # Notifica o cliente
        Notification.objects.create(
            client=booking.client,
            message=(
                f"Seu atendimento do dia {booking.date.strftime('%d/%m/%Y')} "
                f"foi concluído. Obrigado pela preferência!"
            )
        )

        messages.success(request, "Atendimento marcado como concluído!")
        return redirect("dashboard_redirect")

class BarbeiroUserCreateView(LoginRequiredMixin, CreateView):
    """
    Cadastro de novos clientes realizado pelo barbeiro.
    """
    model = User
    form_class = BarberClientForm
    template_name = "barbeiro/usuario_cliente_form.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(commit=True)
        profile = user.profile
        profile.assigned_barber = self.request.user
        if self.request.user.profile.barbershop:
            profile.barbershop = self.request.user.profile.barbershop
        profile.save()
        self.object = user  # Define o objeto para os redirecionamentos do get_success_url
        messages.success(self.request, f"Cliente {user.get_full_name() or user.username} cadastrado com sucesso e vinculado à sua carteira!")
        return redirect(self.get_success_url())

class BarberClientProfileUpdateView(LoginRequiredMixin, UpdateView):
    """
    Permite que um barbeiro edite o perfil de um cliente de sua carteira.
    """
    model = Profile
    form_class = BarberClientProfileForm
    template_name = "barbearia/cliente_perfil_form.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def dispatch(self, request, *args, **kwargs):
        profile = self.get_object()
        if request.user.profile.role == "BARBEIRO" and profile.assigned_barber != request.user:
            raise PermissionDenied
        elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Perfil do cliente atualizado!")
        return super().form_valid(form)


class BarberBookingUpdateView(LoginRequiredMixin, UpdateView):
    """
    Permite que um barbeiro reagende/edite o agendamento de seu cliente.
    """
    model = Booking
    form_class = BookingForm
    template_name = "barbearia/agendar.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.get_object().client
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        booking = self.get_object()
        if request.user.profile.role == "BARBEIRO" and booking.barber != request.user:
            raise PermissionDenied
        elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        booking = form.save(commit=False)
        # Verifica se a data ou horário foi modificado comparando com o estado atual no banco de dados
        old_booking = Booking.objects.get(pk=booking.pk)
        date_changed = old_booking.date != booking.date or old_booking.time != booking.time

        response = super().form_valid(form)

        if date_changed:
            Notification.objects.create(
                client=booking.client,
                message=(
                    f"O barbeiro {self.request.user.get_full_name() or self.request.user.username} "
                    f"reagendou seu corte para o dia {booking.date.strftime('%d/%m/%Y')} "
                    f"às {booking.time.strftime('%H:%M')}."
                )
            )

        messages.success(self.request, "Agendamento atualizado com sucesso!")
        return response


class BarberScheduleUpdateView(LoginRequiredMixin, UpdateView):
    """
    Permite que o barbeiro ou desenvolvedor configure seus horários de trabalho e pausa.
    """
    model = Profile
    form_class = BarberScheduleForm
    template_name = "barbearia/configurar_agenda.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def get_object(self, queryset=None):
        return self.request.user.profile

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Configuração de horários atualizada com sucesso!")
        return super().form_valid(form)


# ==========================================
# VIEWS DO PORTAL DO DESENVOLVEDOR / ADMIN
# ==========================================

class DesenvolvedorDashboardView(LoginRequiredMixin, TemplateView):
    """
    Painel de super-administrador/desenvolvedor para gerenciar tudo no sistema.
    """
    template_name = "desenvolvedor/desenvolvedor_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estatísticas globais
        context["total_clients"] = Profile.objects.filter(role="CLIENTE").count()
        context["total_barbers"] = Profile.objects.filter(role="BARBEIRO").count()
        context["total_bookings"] = Booking.objects.count()
        context["total_products"] = Product.objects.count()

        # Detalhamento do faturamento
        service_rev = Booking.objects.filter(status="CONCLUIDO").aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")

        plan_rev = Profile.objects.filter(plan_active=True, plan__isnull=False).aggregate(
            total=Sum("plan__price")
        )["total"] or decimal.Decimal("0.00")

        context["global_revenue"] = service_rev + plan_rev
        context["service_revenue"] = service_rev
        context["plan_revenue"] = plan_rev

        # Listas de entidades para gerenciamento
        context["users"] = Profile.objects.all().select_related("user", "assigned_barber", "plan")
        context["bookings"] = Booking.objects.all().select_related("client", "barber", "service")
        context["services"] = Service.objects.all()
        context["products"] = Product.objects.all()
        context["plans"] = SubscriptionPlan.objects.all()
        context["barbershops"] = Barbershop.objects.all()
        context["pending_reservations"] = ProductReservation.objects.filter(
            status="PENDENTE"
        ).select_related("client", "product").order_by("-created_at")

        # Adiciona formulários vazios para criação em modal
        context["product_form"] = ProductForm()
        context["service_form"] = ServiceForm()
        context["barbershop_form"] = BarbershopForm()

        return context


class DeveloperProductCreateView(LoginRequiredMixin, CreateView):
    """
    Criação de produtos (apenas para desenvolvedores).
    """
    model = Product
    form_class = ProductForm
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Produto cadastrado com sucesso!")
        return super().form_valid(form)


class DeveloperProductUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edição de produtos (apenas para desenvolvedores).
    """
    model = Product
    form_class = ProductForm
    template_name = "barbearia/product_form.html"
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Produto atualizado!")
        return super().form_valid(form)


class DeveloperProductDeleteView(LoginRequiredMixin, DeleteView):
    """
    Exclusão de produtos (apenas para desenvolvedores).
    """
    model = Product
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # Permite exclusão imediata via GET para manter a interface rápida
        return self.post(request, *args, **kwargs)


class DeveloperServiceCreateView(LoginRequiredMixin, CreateView):
    """
    Criação de serviços (apenas para desenvolvedores).
    """
    model = Service
    form_class = ServiceForm
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Serviço cadastrado com sucesso!")
        return super().form_valid(form)


class DeveloperServiceUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edição de serviços (apenas para desenvolvedores).
    """
    model = Service
    form_class = ServiceForm
    template_name = "barbearia/service_form.html"
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Serviço atualizado!")
        return super().form_valid(form)


class DeveloperServiceDeleteView(LoginRequiredMixin, DeleteView):
    """
    Exclusão de serviços (apenas para desenvolvedores).
    """
    model = Service
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class DeveloperUserCreateView(LoginRequiredMixin, CreateView):
    """
    Criação de usuários (apenas para desenvolvedores).
    """
    model = User
    form_class = DeveloperUserForm
    template_name = "barbearia/usuario_form.html"
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Usuário cadastrado com sucesso!")
        return super().form_valid(form)


class DeveloperUserUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edição de usuários (apenas para desenvolvedores).
    """
    model = User
    form_class = DeveloperUserForm
    template_name = "barbearia/usuario_form.html"
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Usuário atualizado com sucesso!")
        return super().form_valid(form)


class DeveloperUserDeleteView(LoginRequiredMixin, View):
    """
    Exclusão de usuários (apenas para desenvolvedores).
    """
    def get(self, request, pk, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "Você não pode deletar sua própria conta!")
        else:
            user.delete()
            messages.success(request, "Usuário removido com sucesso!")
        return redirect("desenvolvedor_dashboard")

    def post(self, request, pk, *args, **kwargs):
        return self.get(request, pk, *args, **kwargs)


class SeedDatabaseView(LoginRequiredMixin, View):
    """
    Alimenta o banco de dados com dados fictícios realistas para testes.
    """
    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Limpa dados existentes, exceto o usuário logado
        current_user = request.user
        User.objects.exclude(id=current_user.id).delete()
        Service.objects.all().delete()
        Product.objects.all().delete()
        SubscriptionPlan.objects.all().delete()
        Booking.objects.all().delete()
        Notification.objects.all().delete()
        Barbershop.objects.all().delete()
        ProductReservation.objects.all().delete()

        # Cria barbearias padrão
        bs1 = Barbershop.objects.create(
            name="BarberHub Matriz",
            address="Av. Paulista, 1000 - São Paulo",
            phone="551133333333",
            logo_url="https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=192&h=192&fit=crop"
        )
        bs2 = Barbershop.objects.create(
            name="BarberHub Filial Pinheiros",
            address="Rua dos Pinheiros, 450 - São Paulo",
            phone="551133334444",
            logo_url="https://images.unsplash.com/photo-1503951914875-452162b0f3f1?w=192&h=192&fit=crop"
        )

        # Garante que o usuário atual é Desenvolvedor e pertence à Matriz
        dev_profile, _ = Profile.objects.get_or_create(user=current_user)
        dev_profile.role = "DESENVOLVEDOR"
        dev_profile.barbershop = bs1
        dev_profile.save()

        # 1. Cria Serviços
        corte = Service.objects.create(name="Corte Masculino", price=45.00, duration_minutes=30, barbershop=bs1)
        barba = Service.objects.create(name="Barba Terapia", price=35.00, duration_minutes=30, barbershop=bs1)
        combo = Service.objects.create(name="Combo Cabelo & Barba", price=70.00, duration_minutes=60, barbershop=bs1)
        sobrancelha = Service.objects.create(name="Design de Sobrancelha", price=20.00, duration_minutes=15, barbershop=bs1)

        # 2. Cria Barbeiros
        barber1 = User.objects.create_user(
            username="lucas_barber",
            password="password123",
            first_name="Lucas",
            last_name="Barbeiro"
        )
        Profile.objects.create(user=barber1, role="BARBEIRO", phone="5511999999991", barbershop=bs2)

        barber2 = User.objects.create_user(
            username="rodrigo_barber",
            password="password123",
            first_name="Rodrigo",
            last_name="BarberHub"
        )
        Profile.objects.create(user=barber2, role="BARBEIRO", phone="5511999999992", barbershop=bs1)

        # 3. Cria Planos de Assinatura
        plan_gold = SubscriptionPlan.objects.create(
            name="Plano Gold",
            price=80.00,
            description="Cortes ilimitados no mês + 1 lavagem grátis.",
            features="Cortes de cabelo ilimitados\n1 Lavagem inclusa por mês\n10% de desconto em produtos\nAtendimento preferencial",
            created_by=barber2
        )
        plan_platinum = SubscriptionPlan.objects.create(
            name="Plano Platinum VIP",
            price=120.00,
            description="Cabelo e Barba ilimitados + drinks inclusos.",
            features="Cortes e barba ilimitados\nBebidas inclusas (cerveja/refrigerante)\n20% de desconto em produtos\nAgendamento flexível",
            created_by=barber2
        )

        # 4. Cria Clientes
        clients_data = [
            ("caio_cliente", "Caio", "Moura", "5511988888881", barber2, plan_gold, True, date(2026, 6, 20)),
            ("pedro_cliente", "Pedro", "Silva", "5511988888882", barber1, plan_platinum, True, date(2026, 6, 15)),
            ("gustavo_cliente", "Gustavo", "Santos", "5511988888883", barber2, None, False, None),
            ("marcos_cliente", "Marcos", "Oliveira", "5511988888884", barber1, plan_gold, False, date(2026, 5, 10)),  # Expirado/Inativo
        ]

        for username, fname, lname, phone, barber, plan, active, due in clients_data:
            u = User.objects.create_user(
                username=username,
                password="password123",
                first_name=fname,
                last_name=lname
            )
            p = Profile.objects.create(
                user=u,
                role="CLIENTE",
                phone=phone,
                assigned_barber=barber,
                plan=plan,
                plan_active=active,
                plan_due_date=due,
                barbershop=barber.profile.barbershop if barber else bs1
            )
            # Cria notificações para clientes ativos
            Notification.objects.create(
                client=u,
                message="Bem-vindo à BarberHub! Seu portal está pronto."
            )
            if active and plan:
                Notification.objects.create(
                    client=u,
                    message=f"Lembrete: Mensalidade do plano {plan.name} vence em {due.strftime('%d/%m/%Y')}."
                )

        # 5. Cria Produtos
        Product.objects.create(
            name="Pomada Modeladora BarberHub Matte",
            price=39.90,
            stock=15,
            description="Fixação forte com efeito seco e opaco. Perfeito para o dia a dia.",
            image_url="https://images.unsplash.com/photo-1608248597279-f99d160bfcbc?w=400",
            barbershop=bs1
        )
        Product.objects.create(
            name="Óleo Hidratante para Barba Premium",
            price=49.90,
            stock=8,
            description="Nutre, hidrata e alinha os fios da barba deixando um aroma amadeirado.",
            image_url="https://images.unsplash.com/photo-1626015829430-79b97c3fec41?w=400",
            barbershop=bs1
        )
        Product.objects.create(
            name="Shampoo Anticaspa Purificante",
            price=34.90,
            stock=12,
            description="Controla a oleosidade e previne a descamação do couro cabeludo.",
            image_url="https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?w=400",
            barbershop=bs2
        )

        # 6. Cria Agendamentos (Hoje, Passados e Próximos)
        client_user = User.objects.get(username="caio_cliente")
        client_user2 = User.objects.get(username="pedro_cliente")
        client_user3 = User.objects.get(username="gustavo_cliente")

        # Agendamentos de hoje
        Booking.objects.create(
            client=client_user,
            barber=barber2,
            service=combo,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("14:30", "%H:%M").time(),
            status="AGENDADO",
            notes="Gosta do cabelo degrade alto.",
            barbershop=bs1
        )
        Booking.objects.create(
            client=client_user3,
            barber=barber2,
            service=corte,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("16:00", "%H:%M").time(),
            status="AGENDADO",
            barbershop=bs1
        )

        # Concluídos de hoje
        Booking.objects.create(
            client=client_user2,
            barber=barber1,
            service=barba,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("10:00", "%H:%M").time(),
            status="CONCLUIDO",
            barbershop=bs2
        )

        # Próximo agendamento
        Booking.objects.create(
            client=client_user2,
            barber=barber1,
            service=combo,
            date=timezone.localdate() + timezone.timedelta(days=1),
            time=timezone.datetime.strptime("11:00", "%H:%M").time(),
            status="AGENDADO",
            barbershop=bs2
        )

        messages.success(request, "Banco de dados alimentado com sucesso!")
        return redirect("desenvolvedor_dashboard")


# ==========================================
# VIEWS DE AUTENTICAÇÃO E SEGURANÇA (RESET DE PRIMEIRO LOGIN)
# ==========================================

class CustomPasswordChangeView(PasswordChangeView):
    """
    View de alteração de senha forçada. Limpa a flag must_change_password após o sucesso.
    """
    template_name = "barbearia/alterar_senha.html"
    success_url = reverse_lazy("dashboard_redirect")

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = self.request.user.profile
        profile.must_change_password = False
        profile.save()
        messages.success(self.request, "Sua senha foi redefinida com sucesso!")
        return response


# ==========================================
# VIEWS DE VENDAS E RESERVAS DE PRODUTOS
# ==========================================

class ProductReserveView(LoginRequiredMixin, View):
    """
    Permite que um cliente reserve um produto para retirada.
    """
    def post(self, request, pk, *args, **kwargs):
        product = get_object_or_404(Product, pk=pk)
        if product.stock <= 0:
            messages.error(request, f"O produto {product.name} está esgotado no momento.")
            return redirect("cliente_dashboard")

        product.stock -= 1
        product.save()

        ProductReservation.objects.create(
            client=request.user,
            product=product,
            quantity=1,
            status="PENDENTE"
        )

        barber = request.user.profile.assigned_barber
        if barber:
            Notification.objects.create(
                client=barber,
                message=f"Reserva de Produto: O cliente {request.user.get_full_name() or request.user.username} reservou {product.name}."
            )

        messages.success(request, f"Produto {product.name} reservado com sucesso! Retire e pague no seu próximo corte.")
        return redirect("cliente_dashboard")


class CompleteProductReservationView(LoginRequiredMixin, View):
    """
    Permite que um barbeiro ou admin marque a reserva de um produto como concluída.
    """
    def post(self, request, pk, *args, **kwargs):
        if request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied

        reservation = get_object_or_404(ProductReservation, pk=pk)
        reservation.status = "CONCLUIDO"
        reservation.save()

        Notification.objects.create(
            client=reservation.client,
            message=f"Sua retirada do produto {reservation.product.name} foi confirmada!"
        )

        messages.success(request, f"Retirada do produto {reservation.product.name} confirmada com sucesso!")

        if request.user.profile.role == "DESENVOLVEDOR":
            return redirect("desenvolvedor_dashboard")
        return redirect("barbeiro_dashboard")


class CancelProductReservationView(LoginRequiredMixin, View):
    """
    Permite que um cliente, barbeiro ou admin cancele a reserva de um produto.
    """
    def post(self, request, pk, *args, **kwargs):
        reservation = get_object_or_404(ProductReservation, pk=pk)

        is_client = request.user.profile.role == "CLIENTE" and reservation.client == request.user
        is_staff = request.user.profile.role in ["BARBEIRO", "DESENVOLVEDOR"]
        if not (is_client or is_staff):
            raise PermissionDenied

        if reservation.status != "PENDENTE":
            messages.error(request, "Esta reserva não pode ser cancelada pois já foi finalizada ou cancelada.")
            return redirect("dashboard_redirect")

        product = reservation.product
        product.stock += reservation.quantity
        product.save()

        reservation.status = "CANCELADO"
        reservation.save()

        if is_client:
            barber = request.user.profile.assigned_barber
            if barber:
                Notification.objects.create(
                    client=barber,
                    message=f"Cancelamento de Reserva: O cliente {request.user.get_full_name() or request.user.username} cancelou a reserva de {product.name}."
                )
        else:
            Notification.objects.create(
                client=reservation.client,
                message=f"Sua reserva para o produto {product.name} foi cancelada."
            )

        messages.success(request, f"Reserva do produto {product.name} cancelada com sucesso.")

        if request.user.profile.role == "DESENVOLVEDOR":
            return redirect("desenvolvedor_dashboard")
        elif request.user.profile.role == "BARBEIRO":
            return redirect("barbeiro_dashboard")
        return redirect("cliente_dashboard")


# ==========================================
# VIEWS DE CRUD DE BARBEARIA DO DESENVOLVEDOR
# ==========================================

class DeveloperBarbershopCreateView(LoginRequiredMixin, CreateView):
    """
    Permite que desenvolvedores criem uma unidade de Barbearia.
    """
    model = Barbershop
    form_class = BarbershopForm
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Barbearia cadastrada com sucesso!")
        return super().form_valid(form)


class DeveloperBarbershopUpdateView(LoginRequiredMixin, UpdateView):
    """
    Permite que desenvolvedores editem uma unidade de Barbearia.
    """
    model = Barbershop
    form_class = BarbershopForm
    template_name = "desenvolvedor/barbearia_form.html"
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Barbearia atualizada com sucesso!")
        return super().form_valid(form)


class DeveloperBarbershopDeleteView(LoginRequiredMixin, View):
    """
    Permite que desenvolvedores excluam uma unidade de Barbearia.
    """
    def get(self, request, pk, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        barbershop = get_object_or_404(Barbershop, pk=pk)
        barbershop.delete()
        messages.success(request, "Barbearia removida com sucesso!")
        return redirect("desenvolvedor_dashboard")
