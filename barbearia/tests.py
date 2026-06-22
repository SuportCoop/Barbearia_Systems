import decimal
from datetime import date
from django.contrib.auth.models import User
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from unittest import mock
from .models import Barbershop, Booking, Notification, Product, Profile, Service, SubscriptionPlan, ProductReservation


class BarbeariaModelsTestCase(TestCase):
    """
    Casos de teste para modelos de banco de dados e lógica de negócios da Barbearia.
    """

    def setUp(self):
        # Create Barbers
        self.barber_user = User.objects.create_user(
            username="lucas_barber",
            password="password123"
        )
        self.barber_profile = Profile.objects.create(
            user=self.barber_user,
            role="BARBEIRO",
            phone="11999999999"
        )

        # Create Client
        self.client_user = User.objects.create_user(
            username="caio_client",
            password="password123"
        )
        self.client_profile = Profile.objects.create(
            user=self.client_user,
            role="CLIENTE",
            phone="11988888888",
            assigned_barber=self.barber_user
        )

        # Create Service
        self.service = Service.objects.create(
            name="Corte",
            price=decimal.Decimal("50.00"),
            duration_minutes=30
        )

        # Create Subscription Plan
        self.plan = SubscriptionPlan.objects.create(
            name="Plano Gold",
            price=decimal.Decimal("80.00"),
            description="Cortes ilimitados",
            features="Cortes ilimitados",
            created_by=self.barber_user
        )

    def test_booking_creation_and_duplication(self):
        """
        Testa a criação de agendamentos e valida a prevenção de agendamento duplicado.
        """
        today = timezone.localdate()
        time_slot = timezone.datetime.strptime("14:00", "%H:%M").time()

        # Create first valid booking
        booking1 = Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time_slot,
            status="AGENDADO"
        )
        self.assertEqual(booking1.status, "AGENDADO")

        # Attempt to book the same time and date (should trigger form block in view)
        # We test the model query check that views use
        duplicate_exists = Booking.objects.filter(
            barber=self.barber_user,
            date=today,
            time=time_slot,
            status="AGENDADO"
        ).exists()
        
        self.assertTrue(duplicate_exists)

    def test_barber_monthly_revenue_calculation(self):
        """
        Testa o cálculo correto do faturamento mensal de um barbeiro,
        incluindo agendamentos concluídos e mensalidades de planos ativos.
        """
        today = timezone.localdate()
        time_slot1 = timezone.datetime.strptime("09:00", "%H:%M").time()
        time_slot2 = timezone.datetime.strptime("10:00", "%H:%M").time()

        # Create completed booking (price 50.00)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time_slot1,
            status="CONCLUIDO"
        )

        # Create active plan subscription on customer (price 80.00)
        self.client_profile.plan = self.plan
        self.client_profile.plan_active = True
        self.client_profile.save()

        # Calculate revenue (soma de cortes concluidos no mes + mensalidades ativas)
        first_day_of_month = today.replace(day=1)
        completed_bookings = Booking.objects.filter(
            barber=self.barber_user,
            date__gte=first_day_of_month,
            date__lte=today,
            status="CONCLUIDO"
        )
        service_billing = completed_bookings.aggregate(
            total=Sum("service__price")
        )["total"] or decimal.Decimal("0.00")

        portfolio_clients = Profile.objects.filter(
            assigned_barber=self.barber_user,
            role="CLIENTE"
        )
        active_subscribers = portfolio_clients.filter(
            plan_active=True,
            plan__isnull=False
        )
        plan_billing = active_subscribers.aggregate(
            total=Sum("plan__price")
        )["total"] or decimal.Decimal("0.00")

        total_billing = service_billing + plan_billing
        self.assertEqual(total_billing, decimal.Decimal("130.00"))


class BarbeariaPermissionsTestCase(TestCase):
    """
    Casos de teste para restrições de acesso a páginas com base na função do usuário.
    """

    def setUp(self):
        self.client_user = User.objects.create_user(
            username="caio_client",
            password="password123"
        )
        Profile.objects.create(user=self.client_user, role="CLIENTE")

        self.barber_user = User.objects.create_user(
            username="lucas_barber",
            password="password123"
        )
        Profile.objects.create(user=self.barber_user, role="BARBEIRO")

    def test_client_cannot_access_barber_dashboard(self):
        """
        Verifica se o cliente tem acesso negado (retorna 403) ao painel do barbeiro.
        """
        self.client_user = User.objects.get(username="caio_client")
        self.client_profile = self.client_user.profile
        
        self.client_profile.role = "CLIENTE"
        self.client_profile.save()

        self.client_login = self.client_profile.user
        self.client_login_success = self.client_profile.user

        # Login as client
        self.client_logged_in = self.client.login(username="caio_client", password="password123")
        self.assertTrue(self.client_logged_in)

        # Get barber dashboard
        response = self.client.get(reverse("barbeiro_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_barber_can_access_barber_dashboard(self):
        """
        Verifica se o barbeiro pode acessar (retorna 200) o painel do barbeiro.
        """
        self.barber_logged_in = self.client.login(username="lucas_barber", password="password123")
        self.assertTrue(self.barber_logged_in)

        response = self.client.get(reverse("barbeiro_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_barber_isolation_on_booking_completion(self):
        """
        Verifica se um barbeiro não pode concluir o agendamento de outro barbeiro (retorna 403).
        """
        # Create another barber
        barber2_user = User.objects.create_user(username="rodrigo_barber", password="password123")
        Profile.objects.create(user=barber2_user, role="BARBEIRO")

        # Create service and booking for Barber 2
        service = Service.objects.create(name="Corte", price=decimal.Decimal("50.00"), duration_minutes=30)
        booking = Booking.objects.create(
            client=self.client_user,
            barber=barber2_user,
            service=service,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("15:00", "%H:%M").time(),
            status="AGENDADO"
        )

        # Login as Barber 1 (lucas_barber)
        self.client.login(username="lucas_barber", password="password123")

        # Attempt to mark Barber 2's booking as completed
        response = self.client.post(reverse("concluir_agendamento", args=[booking.id]))
        self.assertEqual(response.status_code, 403)
        
        # Verify booking is still AGENDADO
        booking.refresh_from_db()
        self.assertEqual(booking.status, "AGENDADO")

    def test_barber_isolation_on_plan_assignment(self):
        """
        Verifica se um barbeiro não pode editar a assinatura de um cliente atribuído a outro barbeiro (retorna 403).
        """
        # Create another barber
        barber2_user = User.objects.create_user(username="rodrigo_barber", password="password123")
        Profile.objects.create(user=barber2_user, role="BARBEIRO")

        # Assign client to Barber 2
        client_profile = self.client_user.profile
        client_profile.assigned_barber = barber2_user
        client_profile.save()

        # Login as Barber 1 (lucas_barber)
        self.client.login(username="lucas_barber", password="password123")

        # Attempt to assign a plan to Barber 2's client
        response = self.client.post(reverse("atribuir_plano", args=[client_profile.id]), {
            "plan": "",
            "plan_active": False,
            "assigned_barber": barber2_user.id
        })
        self.assertEqual(response.status_code, 403)

    def test_developer_user_crud(self):
        """
        Verifica se o desenvolvedor pode criar, editar e deletar usuários através de views personalizadas.
        """
        # Create Developer
        dev_user = User.objects.create_user(username="developer_admin", password="password123")
        Profile.objects.create(user=dev_user, role="DESENVOLVEDOR")

        # Login as Developer
        self.client.login(username="developer_admin", password="password123")

        # 1. Create a User (Barber)
        response = self.client.post(reverse("criar_usuario"), {
            "username": "new_seeded_client",
            "first_name": "Test",
            "last_name": "Client",
            "email": "test@barberhub.com",
            "phone": "11977777777",
            "role": "BARBEIRO",
            "password": "newpassword123"
        })
        self.assertEqual(response.status_code, 302)  # Redirects on success
        
        new_user = User.objects.get(username="new_seeded_client")
        self.assertEqual(new_user.profile.role, "BARBEIRO")
        self.assertEqual(new_user.profile.phone, "11977777777")

        # 2. Edit the User (make them a Developer)
        response = self.client.post(reverse("editar_usuario", args=[new_user.id]), {
            "username": "new_seeded_client",
            "first_name": "Test",
            "last_name": "Client",
            "email": "test@barberhub.com",
            "phone": "11977777777",
            "role": "DESENVOLVEDOR",
            "password": ""  # Blank password to maintain existing
        })
        self.assertEqual(response.status_code, 302)
        
        new_user.profile.refresh_from_db()
        self.assertEqual(new_user.profile.role, "DESENVOLVEDOR")

        # 3. Delete the User
        response = self.client.get(reverse("deletar_usuario", args=[new_user.id]))
        self.assertEqual(response.status_code, 302)
        
        # Verify user is deleted
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="new_seeded_client")

    def test_barber_can_edit_own_client_profile(self):
        """
        Verifica se um barbeiro pode editar com sucesso o perfil de um cliente atribuído a ele.
        """
        # Assign client to Barber 1 (lucas_barber)
        client_profile = self.client_user.profile
        client_profile.assigned_barber = self.barber_user
        client_profile.save()

        # Login as Barber 1
        self.client.login(username="lucas_barber", password="password123")

        # Edit client profile
        response = self.client.post(reverse("editar_cliente_perfil", args=[client_profile.id]), {
            "first_name": "UpdatedName",
            "last_name": "Client",
            "email": "updated@client.com",
            "phone": "11911112222",
            "plan": "",
            "plan_active": False,
            "assigned_barber": self.barber_user.id
        })
        self.assertEqual(response.status_code, 302)

        # Verify updates
        self.client_user.refresh_from_db()
        client_profile.refresh_from_db()
        self.assertEqual(self.client_user.first_name, "UpdatedName")
        self.assertEqual(client_profile.phone, "11911112222")

    def test_barber_cannot_edit_other_client_profile(self):
        """
        Verifica se um barbeiro recebe 403 ao tentar editar o perfil de um cliente atribuído a outro barbeiro.
        """
        # Create Barber 2
        barber2_user = User.objects.create_user(username="rodrigo_barber", password="password123")
        Profile.objects.create(user=barber2_user, role="BARBEIRO")

        # Assign client to Barber 2
        client_profile = self.client_user.profile
        client_profile.assigned_barber = barber2_user
        client_profile.save()

        # Login as Barber 1 (lucas_barber)
        self.client.login(username="lucas_barber", password="password123")

        # Attempt to edit client profile
        response = self.client.post(reverse("editar_cliente_perfil", args=[client_profile.id]), {
            "first_name": "HackName",
            "last_name": "Client",
            "email": "hacked@client.com",
            "phone": "11911112222",
            "plan": "",
            "plan_active": False,
            "assigned_barber": barber2_user.id
        })
        self.assertEqual(response.status_code, 403)

    def test_barber_can_edit_own_booking(self):
        """
        Verifica se um barbeiro pode editar/reagendar com sucesso um compromisso atribuído a ele.
        """
        # Create service and booking for Barber 1
        service = Service.objects.create(name="Corte", price=decimal.Decimal("50.00"), duration_minutes=30)
        booking = Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=service,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("15:00", "%H:%M").time(),
            status="AGENDADO"
        )

        # Login as Barber 1 (lucas_barber)
        self.client.login(username="lucas_barber", password="password123")

        # Edit booking time to 16:00
        new_time = timezone.datetime.strptime("16:00", "%H:%M").time()
        response = self.client.post(reverse("editar_agendamento", args=[booking.id]), {
            "barber": self.barber_user.id,
            "service": service.id,
            "date": timezone.localdate(),
            "time": new_time,
            "notes": "Updated notes"
        })
        self.assertEqual(response.status_code, 302)

        # Verify update
        booking.refresh_from_db()
        self.assertEqual(booking.time, new_time)
        self.assertEqual(booking.notes, "Updated notes")

    def test_barber_cannot_edit_other_booking(self):
        """
        Verifica se um barbeiro recebe 403 ao tentar editar/reagendar um compromisso atribuído a outro barbeiro.
        """
        # Create Barber 2
        barber2_user = User.objects.create_user(username="rodrigo_barber", password="password123")
        Profile.objects.create(user=barber2_user, role="BARBEIRO")

        # Create service and booking for Barber 2
        service = Service.objects.create(name="Corte", price=decimal.Decimal("50.00"), duration_minutes=30)
        booking = Booking.objects.create(
            client=self.client_user,
            barber=barber2_user,
            service=service,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("15:00", "%H:%M").time(),
            status="AGENDADO"
        )

        # Login as Barber 1 (lucas_barber)
        self.client.login(username="lucas_barber", password="password123")

        # Attempt to edit booking time
        new_time = timezone.datetime.strptime("16:00", "%H:%M").time()
        response = self.client.post(reverse("editar_agendamento", args=[booking.id]), {
            "barber": barber2_user.id,
            "service": service.id,
            "date": timezone.localdate(),
            "time": new_time,
            "notes": "Hacked"
        })
        self.assertEqual(response.status_code, 403)


class BarbeariaDailyRevenueAndCrossNotificationsTestCase(TestCase):
    """
    Casos de teste para a métrica de faturamento concluído hoje e notificações cruzadas
    disparadas durante o agendamento, cancelamento e atualizações.
    """

    def setUp(self):
        # Create Barbers
        self.barber_user = User.objects.create_user(
            username="lucas_barber",
            password="password123"
        )
        self.barber_profile = Profile.objects.create(
            user=self.barber_user,
            role="BARBEIRO",
            phone="11999999999"
        )

        # Create Client
        self.client_user = User.objects.create_user(
            username="caio_client",
            password="password123"
        )
        self.client_profile = Profile.objects.create(
            user=self.client_user,
            role="CLIENTE",
            phone="11988888888",
            assigned_barber=self.barber_user
        )

        # Create Service
        self.service = Service.objects.create(
            name="Corte",
            price=decimal.Decimal("50.00"),
            duration_minutes=30
        )

    def test_barber_daily_revenue_calculation(self):
        """
        Verifica se o faturamento concluído de hoje apenas agrega os agendamentos concluídos na data de hoje.
        """
        today = timezone.localdate()
        yesterday = today - timezone.timedelta(days=1)
        time1 = timezone.datetime.strptime("09:00", "%H:%M").time()
        time2 = timezone.datetime.strptime("10:00", "%H:%M").time()
        time3 = timezone.datetime.strptime("11:00", "%H:%M").time()

        # 1. Booking completed today: R$ 50.00 (Should be included)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time1,
            status="CONCLUIDO"
        )

        # 2. Booking scheduled today: R$ 50.00 (Should not be included since it is not completed)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time2,
            status="AGENDADO"
        )

        # 3. Booking completed yesterday: R$ 50.00 (Should not be included since it is not today)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=yesterday,
            time=time3,
            status="CONCLUIDO"
        )

        # Login as Barber
        self.client.login(username="lucas_barber", password="password123")

        # Request Barber Dashboard
        response = self.client.get(reverse("barbeiro_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["today_completed_billing"], decimal.Decimal("50.00"))

    def test_notification_on_booking_creation_by_client(self):
        """
        Verifica se o agendamento de um corte cria uma notificação para o barbeiro.
        """
        self.client.login(username="caio_client", password="password123")
        today = timezone.localdate()
        time_slot = timezone.datetime.strptime("14:00", "%H:%M").time()

        response = self.client.post(reverse("agendar"), {
            "barber": self.barber_user.id,
            "service": self.service.id,
            "date": today,
            "time": time_slot,
            "notes": "Testing creation notification"
        })
        self.assertEqual(response.status_code, 302)

        # Verify a notification was created for the barber
        barber_notifications = self.barber_user.notifications.all()
        self.assertTrue(barber_notifications.exists())
        notification = barber_notifications.first()
        self.assertIn("caio_client", notification.message)
        self.assertIn(today.strftime('%d/%m/%Y'), notification.message)

    def test_notification_on_booking_cancellation_by_client(self):
        """
        Verifica se o cancelamento de um agendamento por um cliente envia uma notificação para o barbeiro.
        """
        today = timezone.localdate()
        time_slot = timezone.datetime.strptime("14:00", "%H:%M").time()
        booking = Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time_slot,
            status="AGENDADO"
        )

        self.client.login(username="caio_client", password="password123")
        response = self.client.post(reverse("cancelar_agendamento", args=[booking.id]))
        self.assertEqual(response.status_code, 302)

        # Verify notification for the barber
        barber_notifications = self.barber_user.notifications.filter(message__contains="cancelou")
        self.assertTrue(barber_notifications.exists())

    def test_notification_on_booking_cancellation_by_barber(self):
        """
        Verifica se o cancelamento de um agendamento pelo barbeiro envia uma notificação para o cliente.
        """
        today = timezone.localdate()
        time_slot = timezone.datetime.strptime("14:00", "%H:%M").time()
        booking = Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time_slot,
            status="AGENDADO"
        )

        self.client.login(username="lucas_barber", password="password123")
        response = self.client.post(reverse("cancelar_agendamento", args=[booking.id]))
        self.assertEqual(response.status_code, 302)

        # Verify notification for the client
        client_notifications = self.client_user.notifications.filter(message__contains="cancelou")
        self.assertTrue(client_notifications.exists())
        self.assertIn("lucas_barber", client_notifications.first().message)

    def test_notification_on_booking_reschedule_by_barber(self):
        """
        Verifica se a edição/reagendamento da data ou hora do agendamento por um barbeiro dispara uma notificação para o cliente.
        """
        today = timezone.localdate()
        time_slot = timezone.datetime.strptime("14:00", "%H:%M").time()
        booking = Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=time_slot,
            status="AGENDADO"
        )

        self.client.login(username="lucas_barber", password="password123")

        new_date = today + timezone.timedelta(days=1)
        new_time = timezone.datetime.strptime("16:00", "%H:%M").time()

        response = self.client.post(reverse("editar_agendamento", args=[booking.id]), {
            "barber": self.barber_user.id,
            "service": self.service.id,
            "date": new_date,
            "time": new_time,
            "notes": "Rescheduled by barber"
        })
        self.assertEqual(response.status_code, 302)

        # Verify notification for the client
        client_notifications = self.client_user.notifications.filter(message__contains="reagendou")
        self.assertTrue(client_notifications.exists())
        notification = client_notifications.first()
        self.assertIn("lucas_barber", notification.message)
        self.assertIn(new_date.strftime('%d/%m/%Y'), notification.message)

    def test_barber_client_creation_and_auto_assignment(self):
        """
        Verifica se um barbeiro pode cadastrar um novo cliente e se ele é automaticamente
        vinculado à sua carteira.
        """
        self.client.login(username="lucas_barber", password="password123")
        
        response = self.client.post(reverse("barbeiro_criar_usuario"), {
            "username": "brand_new_client",
            "first_name": "Jose",
            "last_name": "Aldo",
            "email": "aldo@ufc.com",
            "phone": "11966667777",
            "password": "brandnewpassword123"
        })
        self.assertEqual(response.status_code, 302)  # Redirects on success

        # Check that user is created
        new_user = User.objects.get(username="brand_new_client")
        self.assertEqual(new_user.first_name, "Jose")
        
        # Check that profile role is CLIENTE and assigned_barber is the creating barber
        profile = new_user.profile
        self.assertEqual(profile.role, "CLIENTE")
        self.assertEqual(profile.phone, "11966667777")
        self.assertEqual(profile.assigned_barber, self.barber_user)

    def test_client_with_assigned_barber_sees_only_that_barber(self):
        """
        Verifica se um cliente com um barbeiro associado apenas consegue ver/agendar aquele barbeiro.
        """
        # Create a second barber
        barber2 = User.objects.create_user(username="rodrigo_barber", password="password123")
        Profile.objects.create(user=barber2, role="BARBEIRO")

        # Verify client is assigned to self.barber_user ("lucas_barber")
        self.assertEqual(self.client_user.profile.assigned_barber, self.barber_user)

        self.client.login(username="caio_client", password="password123")
        response = self.client.get(reverse("agendar"))
        self.assertEqual(response.status_code, 200)

        # Assert only self.barber_user is in the form queryset choices
        barber_queryset = response.context["form"].fields["barber"].queryset
        self.assertEqual(barber_queryset.count(), 1)
        self.assertIn(self.barber_user, barber_queryset)
        self.assertNotIn(barber2, barber_queryset)

    def test_client_without_assigned_barber_sees_all_barbers(self):
        """
        Verifica se um cliente sem barbeiro associado vê todos os barbeiros disponíveis no formulário de agendamento.
        """
        # Create a second barber
        barber2 = User.objects.create_user(username="rodrigo_barber", password="password123")
        Profile.objects.create(user=barber2, role="BARBEIRO")

        # Unassign client's barber
        profile = self.client_user.profile
        profile.assigned_barber = None
        profile.save()

        self.client.login(username="caio_client", password="password123")
        response = self.client.get(reverse("agendar"))
        self.assertEqual(response.status_code, 200)

        # Assert both barbers are present in form choices
        barber_queryset = response.context["form"].fields["barber"].queryset
        self.assertEqual(barber_queryset.count(), 2)
        self.assertIn(self.barber_user, barber_queryset)
        self.assertIn(barber2, barber_queryset)

    def test_barber_dashboard_weekly_revenue_and_mensalistas(self):
        """
        Verifica se o painel do barbeiro calcula corretamente o número de clientes mensalistas
        ativos e o faturamento do serviço concluído da semana atual.
        """
        # Create active subscription plan for the client
        plan = SubscriptionPlan.objects.create(
            name="Plano VIP",
            price=decimal.Decimal("100.00"),
            description=" VIP",
            features="VIP",
            created_by=self.barber_user
        )
        self.client_user.profile.plan = plan
        self.client_user.profile.plan_active = True
        self.client_user.profile.save()

        # Create booking completed today (this week)
        today = timezone.localdate()
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=timezone.datetime.strptime("10:00", "%H:%M").time(),
            status="CONCLUIDO"
        )

        # Create booking completed 8 days ago (last week)
        last_week = today - timezone.timedelta(days=8)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=last_week,
            time=timezone.datetime.strptime("11:00", "%H:%M").time(),
            status="CONCLUIDO"
        )

        self.client.login(username="lucas_barber", password="password123")
        response = self.client.get(reverse("barbeiro_dashboard"))
        self.assertEqual(response.status_code, 200)

        # Assert metrics are correctly calculated
        self.assertEqual(response.context["mensalistas_count"], 1)
        self.assertEqual(response.context["weekly_revenue"], decimal.Decimal("50.00"))  # Only today's booking is this week

    @mock.patch("requests.post")
    def test_send_notifications_management_command(self, mock_post):
        """
        Verifica se a chamada do comando send_notifications filtra os agendamentos
        e invoca a API de WhatsApp da Codesflow.
        """
        from django.core.management import call_command
        from unittest import mock

        # Mock a successful API response
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Create a booking for today
        today = timezone.localdate()
        booking = Booking.objects.create(
            client=self.client_user,
            barber=self.barber_user,
            service=self.service,
            date=today,
            time=timezone.datetime.strptime("09:00", "%H:%M").time(),
            status="AGENDADO"
        )

        # Check phone number is cleaned and starts with 55
        self.client_user.profile.phone = "11988888888"
        self.client_user.profile.save()

        # Run command
        call_command("send_notifications")

        # Verify API request was made and flags were updated
        self.assertTrue(mock_post.called)
        booking.refresh_from_db()
        self.assertTrue(booking.notified_day_of)


class NewFeaturesTestCase(TestCase):
    def setUp(self):
        self.barbershop = Barbershop.objects.create(name="Test Shop")
        self.user = User.objects.create_user(username="test_user", password="password123")
        self.profile = Profile.objects.create(user=self.user, role="BARBEIRO", barbershop=self.barbershop, must_change_password=True)
        self.product = Product.objects.create(name="Test Product", price=10.00, stock=5, barbershop=self.barbershop)
        self.client_user = User.objects.create_user(username="client_user", password="password123")
        self.client_profile = Profile.objects.create(user=self.client_user, role="CLIENTE", barbershop=self.barbershop)

    def test_forced_password_change_middleware(self):
        # Log in the user who must change password
        self.client.login(username="test_user", password="password123")
        # Try to access dashboard
        response = self.client.get(reverse("barbeiro_dashboard"))
        # Should redirect to password change page
        self.assertEqual(response.status_code, 302)
        self.assertIn("alterar-senha", response.url)

    def test_product_reservation_flow(self):
        # Log in the client
        self.client.login(username="client_user", password="password123")
        # Reserve product
        response = self.client.post(reverse("reservar_produto", args=[self.product.id]))
        # Should redirect back to dashboard
        self.assertEqual(response.status_code, 302)
        
        # Verify product stock decremented
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

        # Verify reservation was created
        res = ProductReservation.objects.get(client=self.client_user, product=self.product)
        self.assertEqual(res.status, "PENDENTE")
        self.assertEqual(res.quantity, 1)


class SchedulingSynchronizationTestCase(TestCase):
    """
    Casos de teste para sincronização de agendamentos, lógica de disponibilidade,
    prevenção de sobreposição e agendamento em nome de clientes.
    """
    def setUp(self):
        # Cria Barbeiro
        self.barber = User.objects.create_user(username="barber_lucas", password="password123")
        Profile.objects.create(user=self.barber, role="BARBEIRO", phone="11999999999")
        
        # Cria Cliente
        self.client_user = User.objects.create_user(username="client_caio", password="password123")
        Profile.objects.create(user=self.client_user, role="CLIENTE", phone="11988888888")
        
        # Cria Serviços com diferentes durações
        self.service_short = Service.objects.create(name="Corte Rápido", price=30.00, duration_minutes=30)
        self.service_long = Service.objects.create(name="Combo Completo", price=70.00, duration_minutes=60)
        
    def test_get_available_slots_logic(self):
        from barbearia.views import get_available_slots
        from datetime import date, time as dt_time
        
        today = date(2026, 7, 1)
        
        # 1. Inicialmente, todos os slots das 08:00 às 20:00 devem estar livres (24 slots de 30 mins)
        slots = get_available_slots(self.barber, today, service_duration=30)
        self.assertEqual(len(slots), 24)
        self.assertIn("08:00", slots)
        self.assertIn("19:30", slots)
        
        # 2. Adiciona um agendamento AGENDADO às 10:00 (duração de 30 mins)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber,
            service=self.service_short,
            date=today,
            time=dt_time(10, 0),
            status="AGENDADO"
        )
        
        slots = get_available_slots(self.barber, today, service_duration=30)
        self.assertEqual(len(slots), 23)
        self.assertNotIn("10:00", slots)
        self.assertIn("09:30", slots)
        self.assertIn("10:30", slots)
        
        # 3. Solicitando a disponibilidade de slot de serviço de 60 minutos.
        # Como 10:00 está ocupado:
        # - O slot 09:30 NÃO deve estar disponível porque se sobreporia a 10:00 (começa 09:30, termina 10:30, ocupado).
        # - O slot 10:00 está ocupado.
        # Portanto, tanto 09:30 quanto 10:00 devem ser excluídos!
        slots_60 = get_available_slots(self.barber, today, service_duration=60)
        self.assertNotIn("09:30", slots_60)
        self.assertNotIn("10:00", slots_60)
        self.assertIn("09:00", slots_60)
        self.assertIn("10:30", slots_60)

    def test_availability_api_endpoint(self):
        self.client.login(username="client_caio", password="password123")
        today_str = "2026-07-01"
        
        response = self.client.get(reverse("horarios_disponiveis"), {
            "barber_id": self.barber.id,
            "date": today_str,
            "service_id": self.service_short.id
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("slots", data)
        self.assertEqual(len(data["slots"]), 24)

    def test_booking_form_validation(self):
        from barbearia.forms import BookingForm
        from datetime import date, time as dt_time
        
        today = date(2026, 7, 1)
        
        # Cria um agendamento às 14:00 (duração 60 mins)
        Booking.objects.create(
            client=self.client_user,
            barber=self.barber,
            service=self.service_long,
            date=today,
            time=dt_time(14, 0),
            status="AGENDADO"
        )
        
        # Tenta agendar às 14:30 (deve falhar devido a sobreposição)
        form_data = {
            "barber": self.barber.id,
            "service": self.service_short.id,
            "date": today,
            "time": "14:30",
            "notes": ""
        }
        form = BookingForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("conflita com outro agendamento", form.errors["__all__"][0])
        
        # Tenta um horário livre às 15:00 (deve ter sucesso)
        form_data_valid = {
            "barber": self.barber.id,
            "service": self.service_short.id,
            "date": today,
            "time": "15:00",
            "notes": ""
        }
        form_valid = BookingForm(data=form_data_valid)
        self.assertTrue(form_valid.is_valid())

    def test_barber_booking_on_behalf_of_client(self):
        # Faz login como Barbeiro
        self.client.login(username="barber_lucas", password="password123")
        today_str = "2026-07-01"
        
        # Envia agendamento
        response = self.client.post(reverse("barbeiro_agendar"), {
            "client": self.client_user.id,
            "barber": self.barber.id,
            "service": self.service_short.id,
            "date": today_str,
            "time": "11:30",
            "notes": "Agendado pelo barbeiro"
        })
        self.assertEqual(response.status_code, 302) # Redireciona para o painel do barbeiro
        
        # Verifica se o agendamento foi criado
        booking = Booking.objects.get(
            client=self.client_user,
            barber=self.barber,
            date=today_str,
            time="11:30:00"
        )
        self.assertEqual(booking.notes, "Agendado pelo barbeiro")

    @mock.patch("requests.post")
    def test_send_booking_confirmation_request(self, mock_post):
        from barbearia.tasks import send_booking_confirmation_request
        from unittest import mock
        
        # Simula resposta da API
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Cria agendamento
        booking = Booking.objects.create(
            client=self.client_user,
            barber=self.barber,
            service=self.service_short,
            date=timezone.localdate(),
            time=timezone.datetime.strptime("17:00", "%H:%M").time(),
            status="AGENDADO"
        )
        
        # Define número de telefone
        self.client_user.profile.phone = "11988888888"
        self.client_user.profile.save()
        
        # Executa a função
        success = send_booking_confirmation_request(booking)
        self.assertTrue(success)
        self.assertTrue(mock_post.called)

    def test_barber_custom_schedule_and_break_slots(self):
        from barbearia.views import get_available_slots
        from barbearia.forms import BookingForm
        from datetime import date, time as dt_time
        
        today = date(2026, 8, 1)
        
        # Configura expediente customizado e pausa para o barbeiro
        profile = self.barber.profile
        profile.work_start = dt_time(9, 0)
        profile.work_end = dt_time(17, 0)
        profile.break_start = dt_time(12, 0)
        profile.break_end = dt_time(13, 0)
        profile.save()
        
        # 1. Testa a lógica de disponibilidade (get_available_slots)
        slots = get_available_slots(self.barber, today, service_duration=30)
        
        # Total de slots deve ser: (17:00 - 09:00 = 8 horas = 16 slots) - (2 slots da pausa de 1 hora) = 14 slots
        self.assertEqual(len(slots), 14)
        
        # Verifica limites de expediente
        self.assertNotIn("08:00", slots)
        self.assertNotIn("08:30", slots)
        self.assertIn("09:00", slots)
        self.assertIn("16:30", slots)
        self.assertNotIn("17:00", slots)
        
        # Verifica exclusão de pausa
        self.assertNotIn("12:00", slots)
        self.assertNotIn("12:30", slots)
        self.assertIn("11:30", slots)
        self.assertIn("13:00", slots)
        
        # 2. Testa a validação no formulário BookingForm
        # Agendamento fora do expediente (08:30)
        form_data_outside = {
            "barber": self.barber.id,
            "service": self.service_short.id,
            "date": today,
            "time": "08:30",
            "notes": ""
        }
        form_outside = BookingForm(data=form_data_outside)
        self.assertFalse(form_outside.is_valid())
        self.assertIn("dentro do expediente do barbeiro", form_outside.errors["__all__"][0])
        
        # Agendamento durante a pausa (12:00)
        form_data_break = {
            "barber": self.barber.id,
            "service": self.service_short.id,
            "date": today,
            "time": "12:00",
            "notes": ""
        }
        form_break = BookingForm(data=form_data_break)
        self.assertFalse(form_break.is_valid())
        self.assertIn("conflita com o intervalo de pausa do barbeiro", form_break.errors["__all__"][0])
        
        # Agendamento válido (13:00)
        form_data_valid = {
            "barber": self.barber.id,
            "service": self.service_short.id,
            "date": today,
            "time": "13:00",
            "notes": ""
        }
        form_valid = BookingForm(data=form_data_valid)
        self.assertTrue(form_valid.is_valid())

    @mock.patch("requests.post")
    def test_send_subscription_billing_reminders(self, mock_post):
        from barbearia.tasks import send_subscription_billing_reminders
        from datetime import date, time as dt_time, timedelta
        from unittest import mock
        
        # Simula resposta de sucesso da API
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Cria um plano de assinatura para os testes
        plan = SubscriptionPlan.objects.create(
            name="Plano Mensalista Teste",
            price=decimal.Decimal("90.00"),
            description="Plano de Teste",
            features="Teste",
            created_by=self.barber
        )
        
        today = timezone.localdate()
        
        # 1. Cliente 1: Vencimento em 3 dias (Deve ser notificado)
        user1 = User.objects.create_user(username="client_billing_3d", password="password123")
        profile1 = Profile.objects.create(
            user=user1,
            role="CLIENTE",
            phone="11911111111",
            plan=plan,
            plan_active=True,
            plan_due_date=today + timedelta(days=3)
        )
        
        # 2. Cliente 2: Vencimento hoje (Deve ser notificado)
        user2 = User.objects.create_user(username="client_billing_today", password="password123")
        profile2 = Profile.objects.create(
            user=user2,
            role="CLIENTE",
            phone="11922222222",
            plan=plan,
            plan_active=True,
            plan_due_date=today
        )
        
        # 3. Cliente 3: Vencimento ontem (Deve ser notificado como atrasado)
        user3 = User.objects.create_user(username="client_billing_yesterday", password="password123")
        profile3 = Profile.objects.create(
            user=user3,
            role="CLIENTE",
            phone="11933333333",
            plan=plan,
            plan_active=True,
            plan_due_date=today - timedelta(days=1)
        )
        
        # 4. Cliente 4: Vencimento em outro dia (Não deve ser notificado)
        user4 = User.objects.create_user(username="client_billing_other", password="password123")
        profile4 = Profile.objects.create(
            user=user4,
            role="CLIENTE",
            phone="11944444444",
            plan=plan,
            plan_active=True,
            plan_due_date=today + timedelta(days=5)
        )
        
        # Executa a tarefa de cobranças
        sent_count = send_subscription_billing_reminders()
        
        # Deve ter enviado 3 notificações via WhatsApp
        self.assertEqual(sent_count, 3)
        self.assertEqual(mock_post.call_count, 3)
        
        # Verifica se as notificações internas foram devidamente salvas no BD
        self.assertTrue(Notification.objects.filter(client=user1, message__contains="vence em 3 dias").exists())
        self.assertTrue(Notification.objects.filter(client=user2, message__contains="vence hoje").exists())
        self.assertTrue(Notification.objects.filter(client=user3, message__contains="venceu ontem").exists())
        self.assertFalse(Notification.objects.filter(client=user4).exists())

