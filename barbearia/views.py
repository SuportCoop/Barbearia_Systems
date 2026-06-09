import decimal
from datetime import date
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (CreateView, DeleteView,RedirectView, TemplateView,UpdateView,View,)
from barbearia.forms import AssignPlanForm,BookingForm,ClientRegistrationForm,DeveloperUserForm,BarberClientProfileForm,ProductForm,ServiceForm, SubscriptionPlanForm, BarberClientForm
from .models import ( Booking,Notification, Product,   Profile, Service,SubscriptionPlan,)


class UserLoginView(LoginView):
    """
    Custom login view.
    """
    template_name = "barbearia/login.html"

    def get_success_url(self):
        return reverse_lazy("dashboard_redirect")


class UserRegisterView(CreateView):
    """
    Registration view for new clients.
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
    Logout view handling simple GET/POST requests.
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
    Redirects user to their role-specific dashboard.
    """
    pattern_name = "cliente_dashboard"

    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        # Ensure profile exists
        profile, created = Profile.objects.get_or_create(user=user)
        if profile.role == "BARBEIRO":
            return reverse_lazy("barbeiro_dashboard")
        elif profile.role == "DESENVOLVEDOR":
            return reverse_lazy("desenvolvedor_dashboard")
        return reverse_lazy("cliente_dashboard")


# ==========================================
# CLIENT PORTAL VIEWS
# ==========================================

class ClienteDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard for clients to view bookings, plans, and notifications.
    """
    template_name = "barbearia/cliente_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = Profile.objects.get_or_create(user=user)

        # Force CLIENTE role if user logs in without profile
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
        context["products"] = Product.objects.filter(stock__gt=0)[:4]
        return context


class BookingCreateView(LoginRequiredMixin, CreateView):
    """
    Allows clients to schedule a booking.
    """
    model = Booking
    form_class = BookingForm
    template_name = "barbearia/agendar.html"
    success_url = reverse_lazy("cliente_dashboard")

    def form_valid(self, form):
        booking = form.save(commit=False)
        booking.client = self.request.user

        # Validation: Check for double booking
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

        # Create system notification for Client
        Notification.objects.create(
            client=self.request.user,
            message=(
                f"Agendamento confirmado para {booking.date.strftime('%d/%m/%Y')} "
                f"às {booking.time.strftime('%H:%M')} com {booking.barber.get_full_name() or booking.barber.username}."
            )
        )

        # Create notification for Barber
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
    Cancels a booking (marks status as CANCELADO).
    """
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        # Allow cancel only if owner or staff
        if booking.client != request.user:
            if request.user.profile.role == "BARBEIRO" and booking.barber != request.user:
                raise PermissionDenied
            elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
                raise PermissionDenied

        booking.status = "CANCELADO"
        booking.save()

        # Notify Client and Barber based on who cancelled
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

        # Redirect back to where it was called
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        return redirect("dashboard_redirect")


class MarkNotificationReadView(LoginRequiredMixin, View):
    """
    Marks all user notifications as read.
    """
    def post(self, request, *args, **kwargs):
        Notification.objects.filter(client=request.user, is_read=False).update(is_read=True)
        return redirect("cliente_dashboard")


# ==========================================
# BARBER VIEWS
# ==========================================

class BarbeiroDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard displaying statistics and management panels for barbers.
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

        # Portfolio Clients count
        portfolio_clients = Profile.objects.filter(
            assigned_barber=barber,
            role="CLIENTE"
        )
        context["portfolio_clients"] = portfolio_clients

        # Daily bookings
        today_bookings = Booking.objects.filter(
            barber=barber,
            date=today
        ).order_by("time")
        context["today_bookings"] = today_bookings

        # Clients served today (Completed)
        context["served_today_count"] = today_bookings.filter(
            status="CONCLUIDO"
        ).count()

        # Faturamento do Dia (Daily billing of completed bookings today)
        today_completed_bookings = today_bookings.filter(status="CONCLUIDO")
        today_completed_billing = today_completed_bookings.aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")
        context["today_completed_billing"] = today_completed_billing

        # Billing (Monthly calculation)
        first_day_of_month = today.replace(day=1)
        completed_this_month = Booking.objects.filter(
            barber=barber,
            date__gte=first_day_of_month,
            date__lte=today,
            status="CONCLUIDO"
        )
        # Sum services prices
        service_billing = completed_this_month.aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")

        # Active subscriptions billing
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

        # Subscription plans created by this barber or developers
        context["plans"] = SubscriptionPlan.objects.all()

        return context


class PlanCreateView(LoginRequiredMixin, CreateView):
    """
    Allows a barber to create a subscription plan.
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
    Allows a barber to edit a subscription plan.
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
    Allows assigning a plan and due date to a client profile.
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
        # Add client notification about the plan change
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
    Marks a booking as completed.
    """
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)

        if request.user.profile.role == "BARBEIRO" and booking.barber != request.user:
            raise PermissionDenied
        elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied

        booking.status = "CONCLUIDO"
        booking.save()

        # Notify customer
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
    Barber user creation of clients.
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
        profile.save()
        self.object = user  # Set the object for get_success_url redirects
        messages.success(self.request, f"Cliente {user.get_full_name() or user.username} cadastrado com sucesso e vinculado à sua carteira!")
        return redirect(self.get_success_url())

class BarberClientProfileUpdateView(LoginRequiredMixin, UpdateView):
    """
    Allows a barber to edit a client's profile from their portfolio.
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
    Allows a barber to reschedule/edit their client's booking.
    """
    model = Booking
    form_class = BookingForm
    template_name = "barbearia/agendar.html"
    success_url = reverse_lazy("barbeiro_dashboard")

    def dispatch(self, request, *args, **kwargs):
        booking = self.get_object()
        if request.user.profile.role == "BARBEIRO" and booking.barber != request.user:
            raise PermissionDenied
        elif request.user.profile.role not in ["BARBEIRO", "DESENVOLVEDOR"]:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        booking = form.save(commit=False)
        # Check if date or time is modified by comparing with current DB state
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


# ==========================================
# DEVELOPER / ADMIN PORTAL VIEWS
# ==========================================

class DesenvolvedorDashboardView(LoginRequiredMixin, TemplateView):
    """
    Super-admin/developer panel to manage everything in the system.
    """
    template_name = "desenvolvedor/desenvolvedor_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Global stats
        context["total_clients"] = Profile.objects.filter(role="CLIENTE").count()
        context["total_barbers"] = Profile.objects.filter(role="BARBEIRO").count()
        context["total_bookings"] = Booking.objects.count()
        context["total_products"] = Product.objects.count()

        # Revenue breakdown
        service_rev = Booking.objects.filter(status="CONCLUIDO").aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")

        plan_rev = Profile.objects.filter(plan_active=True, plan__isnull=False).aggregate(
            total=Sum("plan__price")
        )["total"] or decimal.Decimal("0.00")

        context["global_revenue"] = service_rev + plan_rev
        context["service_revenue"] = service_rev
        context["plan_revenue"] = plan_rev

        # Entity lists for management
        context["users"] = Profile.objects.all().select_related("user", "assigned_barber", "plan")
        context["bookings"] = Booking.objects.all().select_related("client", "barber", "service")
        context["services"] = Service.objects.all()
        context["products"] = Product.objects.all()
        context["plans"] = SubscriptionPlan.objects.all()

        # Add empty forms for modal creation
        context["product_form"] = ProductForm()
        context["service_form"] = ServiceForm()

        return context


class DeveloperProductCreateView(LoginRequiredMixin, CreateView):
    """
    Developer only product creation.
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
    Developer only product editing.
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
    Developer only product deletion.
    """
    model = Product
    success_url = reverse_lazy("desenvolvedor_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # Allow immediate delete via GET to keep UI fast
        return self.post(request, *args, **kwargs)


class DeveloperServiceCreateView(LoginRequiredMixin, CreateView):
    """
    Developer only service creation.
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
    Developer only service editing.
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
    Developer only service deletion.
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
    Developer only user creation.
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
    Developer only user editing.
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
    Developer only user deletion.
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
    Seeds database with realistic mockup data for testing.
    """
    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != "DESENVOLVEDOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Clear existing data except the logged-in user
        current_user = request.user
        User.objects.exclude(id=current_user.id).delete()
        Service.objects.all().delete()
        Product.objects.all().delete()
        SubscriptionPlan.objects.all().delete()
        Booking.objects.all().delete()
        Notification.objects.all().delete()

        # Ensure current user is Developer
        dev_profile, _ = Profile.objects.get_or_create(user=current_user)
        dev_profile.role = "DESENVOLVEDOR"
        dev_profile.save()

        # 1. Create Services
        corte = Service.objects.create(name="Corte Masculino", price=45.00, duration_minutes=30)
        barba = Service.objects.create(name="Barba Terapia", price=35.00, duration_minutes=30)
        combo = Service.objects.create(name="Combo Cabelo & Barba", price=70.00, duration_minutes=60)
        sobrancelha = Service.objects.create(name="Design de Sobrancelha", price=20.00, duration_minutes=15)

        # 2. Create Barbers
        barber1 = User.objects.create_user(
            username="lucas_barber",
            password="password123",
            first_name="Lucas",
            last_name="Barbeiro"
        )
        Profile.objects.create(user=barber1, role="BARBEIRO", phone="5511999999991")

        barber2 = User.objects.create_user(
            username="rodrigo_barber",
            password="password123",
            first_name="Rodrigo",
            last_name="Benx"
        )
        Profile.objects.create(user=barber2, role="BARBEIRO", phone="5511999999992")

        # 3. Create Subscription Plans
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

        # 4. Create Clients
        clients_data = [
            ("caio_cliente", "Caio", "Moura", "5511988888881", barber2, plan_gold, True, date(2026, 6, 20)),
            ("pedro_cliente", "Pedro", "Silva", "5511988888882", barber1, plan_platinum, True, date(2026, 6, 15)),
            ("gustavo_cliente", "Gustavo", "Santos", "5511988888883", barber2, None, False, None),
            ("marcos_cliente", "Marcos", "Oliveira", "5511988888884", barber1, plan_gold, False, date(2026, 5, 10)),  # Expired/Inactive
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
                plan_due_date=due
            )
            # Create notifications for active clients
            Notification.objects.create(
                client=u,
                message="Bem-vindo à Barbearia Benx! Seu portal está pronto."
            )
            if active and plan:
                Notification.objects.create(
                    client=u,
                    message=f"Lembrete: Mensalidade do plano {plan.name} vence em {due.strftime('%d/%m/%Y')}."
                )

        # 5. Create Products
        Product.objects.create(
            name="Pomada Modeladora Benx Matte",
            price=39.90,
            stock=15,
            description="Fixação forte com efeito seco e opaco. Perfeito para o dia a dia.",
            image_url="https://images.unsplash.com/photo-1608248597279-f99d160bfcbc?w=400"
        )
        Product.objects.create(
            name="Óleo Hidratante para Barba Premium",
            price=49.90,
            stock=8,
            description="Nutre, hidrata e alinha os fios da barba deixando um aroma amadeirado.",
            image_url="https://images.unsplash.com/photo-1626015829430-79b97c3fec41?w=400"
        )
        Product.objects.create(
            name="Shampoo Anticaspa Purificante",
            price=34.90,
            stock=12,
            description="Controla a oleosidade e previne a descamação do couro cabeludo.",
            image_url="https://images.unsplash.com/photo-1535585209827-a15fcdbc4c2d?w=400"
        )

        # 6. Create Bookings (Today's, Past, and Upcoming)
        client_user = User.objects.get(username="caio_cliente")
        client_user2 = User.objects.get(username="pedro_cliente")
        client_user3 = User.objects.get(username="gustavo_cliente")

        # Today's scheduled
        Booking.objects.create(
            client=client_user,
            barber=barber2,
            service=combo,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("14:30", "%H:%M").time(),
            status="AGENDADO",
            notes="Gosta do cabelo degrade alto."
        )
        Booking.objects.create(
            client=client_user3,
            barber=barber2,
            service=corte,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("16:00", "%H:%M").time(),
            status="AGENDADO"
        )

        # Today's completed
        Booking.objects.create(
            client=client_user2,
            barber=barber1,
            service=barba,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("10:00", "%H:%M").time(),
            status="CONCLUIDO"
        )

        # Upcoming booking
        Booking.objects.create(
            client=client_user2,
            barber=barber1,
            service=combo,
            date=timezone.localdate() + timezone.timedelta(days=1),
            time=timezone.datetime.strptime("11:00", "%H:%M").time(),
            status="AGENDADO"
        )

        messages.success(request, "Banco de dados alimentado com sucesso!")
        return redirect("desenvolvedor_dashboard")
