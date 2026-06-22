from django.contrib.auth.models import User
from django.db import models
from datetime import time as datetime_time


class Barbershop(models.Model):
    """
    Unidades de negócio da barbearia (tenants/filiais).
    """
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    logo_url = models.URLField(max_length=500, blank=True, default="")

    def __str__(self):
        return self.name


class SubscriptionPlan(models.Model):
    """
    Planos de assinatura criados por barbeiros/administradores e atribuídos a clientes.
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
        Divide o texto de recursos por linhas para renderizar como tópicos.
        """
        return [f.strip() for f in self.features.split("\n") if f.strip()]


class Profile(models.Model):
    """
    Estende o modelo padrão de usuário do Django com funções, faturamento e planos.
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
    barbershop = models.ForeignKey(
        Barbershop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles"
    )
    must_change_password = models.BooleanField(default=False)
    work_start = models.TimeField(default=datetime_time(8, 0), verbose_name="Início do Expediente")
    work_end = models.TimeField(default=datetime_time(20, 0), verbose_name="Fim do Expediente")
    break_start = models.TimeField(null=True, blank=True, verbose_name="Início da Pausa")
    break_end = models.TimeField(null=True, blank=True, verbose_name="Fim da Pausa")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Service(models.Model):
    """
    Serviços oferecidos pela barbearia.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(default=30)
    barbershop = models.ForeignKey(
        Barbershop,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="services"
    )

    def __str__(self):
        return f"{self.name} (R$ {self.price})"


class Booking(models.Model):
    """
    Registros de agendamentos / reservas.
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
    notified_day_of = models.BooleanField(default=False)
    notified_one_hour_before = models.BooleanField(default=False)
    barbershop = models.ForeignKey(
        Barbershop,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bookings"
    )

    class Meta:
        ordering = ["date", "time"]

    def __str__(self):
        return f"{self.client.username} -> {self.barber.username} ({self.date} @ {self.time})"


class Product(models.Model):
    """
    Produtos para venda na barbearia.
    """
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(max_length=500, blank=True, default="")
    barbershop = models.ForeignKey(
        Barbershop,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products"
    )

    def __str__(self):
        return f"{self.name} (R$ {self.price}) - Estoque: {self.stock}"


class Notification(models.Model):
    """
    Notificações do sistema / alertas para os clientes.
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


class ProductReservation(models.Model):
    """
    Reservas de produtos feitas por clientes para retirada posterior.
    """
    STATUS_CHOICES = (
        ("PENDENTE", "Pendente Retirada"),
        ("CONCLUIDO", "Concluído/Pago"),
        ("CANCELADO", "Cancelado"),
    )

    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="product_reservations"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_reservations"
    )
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDENTE"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.client.username} reservou {self.product.name} (Qtd: {self.quantity})"
