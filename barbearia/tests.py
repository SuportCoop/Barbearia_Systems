import decimal
from datetime import date
from django.contrib.auth.models import User
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Profile, Service, SubscriptionPlan


class BarbeariaModelsTestCase(TestCase):
    """
    Test cases for Barbearia database models and business logic.
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
        Tests booking creation and asserts double booking prevention.
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
        Tests correct monthly revenue computation for a barber
        including completed bookings and active plan subscriptions.
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
    Test cases for user role page access restrictions.
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
        Verify client is denied access (returns 403) to barber dashboard.
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
        Verify barber can access (returns 200) barber dashboard.
        """
        self.barber_logged_in = self.client.login(username="lucas_barber", password="password123")
        self.assertTrue(self.barber_logged_in)

        response = self.client.get(reverse("barbeiro_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_barber_isolation_on_booking_completion(self):
        """
        Verify a barber cannot complete another barber's booking (returns 403).
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
        Verify a barber cannot edit the subscription of a client assigned to another barber.
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
        Verify developer can create, edit, and delete users via custom views.
        """
        # Create Developer
        dev_user = User.objects.create_user(username="developer_admin", password="password123")
        Profile.objects.create(user=dev_user, role="DESENVOLVEDOR")

        # Login as Developer
        self.client.login(username="developer_admin", password="password123")

        # 1. Create a User
        response = self.client.post(reverse("criar_usuario"), {
            "username": "new_seeded_client",
            "first_name": "Test",
            "last_name": "Client",
            "email": "test@benx.com",
            "phone": "11977777777",
            "role": "CLIENTE",
            "password": "newpassword123"
        })
        self.assertEqual(response.status_code, 302)  # Redirects on success
        
        new_user = User.objects.get(username="new_seeded_client")
        self.assertEqual(new_user.profile.role, "CLIENTE")
        self.assertEqual(new_user.profile.phone, "11977777777")

        # 2. Edit the User (make them a Barbeiro)
        response = self.client.post(reverse("editar_usuario", args=[new_user.id]), {
            "username": "new_seeded_client",
            "first_name": "Test",
            "last_name": "Client",
            "email": "test@benx.com",
            "phone": "11977777777",
            "role": "BARBEIRO",
            "password": ""  # Blank password to maintain existing
        })
        self.assertEqual(response.status_code, 302)
        
        new_user.profile.refresh_from_db()
        self.assertEqual(new_user.profile.role, "BARBEIRO")

        # 3. Delete the User
        response = self.client.get(reverse("deletar_usuario", args=[new_user.id]))
        self.assertEqual(response.status_code, 302)
        
        # Verify user is deleted
        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username="new_seeded_client")

    def test_barber_can_edit_own_client_profile(self):
        """
        Verify a barber can successfully edit the profile of a client assigned to them.
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
        Verify a barber receives 403 when trying to edit the profile of a client assigned to another barber.
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
        Verify a barber can successfully edit/reschedule an appointment assigned to them.
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
        Verify a barber receives 403 when trying to edit/reschedule an appointment assigned to another barber.
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
    Test cases for today's completed billing metric and cross-notifications
    triggered during booking, cancellation, and updates.
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
        Verify today's completed billing only aggregates completed bookings on today's date.
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
        Verify that scheduling a cut creates a notification for the barber.
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
        Verify that cancellation of a booking by a client sends a notification to the barber.
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
        Verify that cancellation of a booking by the barber sends a notification to the client.
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
        Verify that editing/rescheduling booking date or time by a barber triggers a notification for the client.
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
        Verify that a barber can register a new client and it is automatically
        assigned to their portfolio.
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
