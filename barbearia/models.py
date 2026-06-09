from django.contrib.auth.models import User
from django.db import models


class SubscriptionPlan(models.Model):
    """
    Subscription plans created by barbers/admins and assigned to clients.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    features = models.TextField(
        help_text="Lista de benefícios separados por quebra de linha."
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_plans"
    )

    def __str__(self):
        return f"{self.name} - R$ {self.price}"

    def get_features_list(self):
        """
        Splits features text by lines to render as bullet points.
        """
        return [f.strip() for f in self.features.split("\n") if f.strip()]


class Profile(models.Model):
    """
    Extends standard Django User model with roles, billing, and plans.
    """
    ROLE_CHOICES = (
        ("CLIENTE", "Cliente"),
        ("BARBEIRO", "Barbeiro"),
        ("DESENVOLVEDOR", "Desenvolvedor"),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="CLIENTE"
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    assigned_barber = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portfolio_clients"
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscribers"
    )
    plan_active = models.BooleanField(default=False)
    plan_due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Service(models.Model):
    """
    Services provided by the barbershop.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(default=30)

    def __str__(self):
        return f"{self.name} (R$ {self.price})"


class Booking(models.Model):
    """
    Booking / scheduling records.
    """
    STATUS_CHOICES = (
        ("AGENDADO", "Agendado"),
        ("CONCLUIDO", "Concluído"),
        ("CANCELADO", "Cancelado"),
    )

    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="client_bookings"
    )
    barber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="barber_bookings"
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="AGENDADO"
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["date", "time"]

    def __str__(self):
        return f"{self.client.username} -> {self.barber.username} ({self.date} @ {self.time})"


class Product(models.Model):
    """
    Products for sale in the barbershop.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(max_length=500, blank=True, default="")

    def __str__(self):
        return f"{self.name} (R$ {self.price}) - Estoque: {self.stock}"


class Notification(models.Model):
    """
    System notifications / alerts for clients.
    """
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notificação para {self.client.username}: {self.message[:30]}"
