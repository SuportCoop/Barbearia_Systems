from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile, SubscriptionPlan, Service, Booking, Product


class ClientRegistrationForm(UserCreationForm):
    """
    Form for clients to register their own account.
    """
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")
    phone = forms.CharField(max_length=20, required=True, label="WhatsApp")

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("first_name", "last_name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            # Profile is created or updated
            profile, created = Profile.objects.get_or_create(user=user)
            if User.objects.count() == 1:
                profile.role = "DESENVOLVEDOR"
            else:
                profile.role = "CLIENTE"
            profile.phone = self.cleaned_data["phone"]
            profile.save()
        return user


class BookingForm(forms.ModelForm):
    """
    Form for scheduling a haircut.
    """
    barber = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Barbeiro",
        empty_label="Selecione um barbeiro"
    )

    class Meta:
        model = Booking
        fields = ["barber", "service", "date", "time", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Observações (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only users with profile role='BARBEIRO' can be selected as barbers
        self.fields["barber"].queryset = User.objects.filter(profile__role="BARBEIRO")
        self.fields["service"].empty_label = "Selecione o serviço"


class SubscriptionPlanForm(forms.ModelForm):
    """
    Form for barbers/admins to create/edit subscription plans.
    """
    class Meta:
        model = SubscriptionPlan
        fields = ["name", "price", "description", "features"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Descreva o plano..."}),
            "features": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Corte de cabelo ilimitado\n1 Cerveja grátis por mês\nAtendimento VIP"
                }
            ),
        }


class AssignPlanForm(forms.ModelForm):
    """
    Form for barbers to assign/update a plan for a client.
    """
    class Meta:
        model = Profile
        fields = ["plan", "plan_active", "plan_due_date", "assigned_barber"]
        widgets = {
            "plan_due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].empty_label = "Nenhum plano (Sem Assinatura)"
        # Barbers to assign
        self.fields["assigned_barber"].queryset = User.objects.filter(profile__role="BARBEIRO")
        self.fields["assigned_barber"].empty_label = "Não atribuído"


class ProductForm(forms.ModelForm):
    """
    Form for managing product inventory.
    """
    class Meta:
        model = Product
        fields = ["name", "price", "stock", "description", "image_url"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class ServiceForm(forms.ModelForm):
    """
    Form for managing services offered.
    """
    class Meta:
        model = Service
        fields = ["name", "price", "duration_minutes"]


class DeveloperUserForm(forms.ModelForm):
    """
    Unified form for the Developer to create/edit system users and roles.
    """
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, label="Função/Cargo")
    phone = forms.CharField(max_length=20, required=False, label="WhatsApp")
    assigned_barber = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Barbeiro da Carteira (Clientes)",
        help_text="testando"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        label="Senha",
        help_text="Deixe em branco para manter a senha atual na edição."
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_barber"].queryset = User.objects.filter(profile__role="BARBEIRO")
        self.fields["assigned_barber"].empty_label = "Não atribuído"
        
        if self.instance and self.instance.pk:
            profile, _ = Profile.objects.get_or_create(user=self.instance)
            self.fields["role"].initial = profile.role
            self.fields["phone"].initial = profile.phone
            self.fields["assigned_barber"].initial = profile.assigned_barber
            self.fields["password"].required = False
        else:
            self.fields["password"].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data["role"]
            profile.phone = self.cleaned_data["phone"]
            profile.assigned_barber = self.cleaned_data["assigned_barber"]
            profile.save()
        return user

class BarberClientForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")
    phone = forms.CharField(max_length=20, required=False, label="WhatsApp")
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=True,
        label="Senha"
    )
    
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data["phone"]
            profile.role = "CLIENTE"
            profile.save()
        return user
    

class BarberClientProfileForm(forms.ModelForm):
    """
    Form for Barbers to edit a client's profile details and subscription plan.
    """
    first_name = forms.CharField(max_length=30, required=True, label="Nome")
    last_name = forms.CharField(max_length=30, required=True, label="Sobrenome")
    email = forms.EmailField(required=True, label="E-mail")

    class Meta:
        model = Profile
        fields = ["phone", "plan", "plan_active", "plan_due_date", "assigned_barber"]
        widgets = {
            "plan_due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].empty_label = "Nenhum plano (Sem Assinatura)"
        self.fields["assigned_barber"].queryset = User.objects.filter(profile__role="BARBEIRO")
        self.fields["assigned_barber"].empty_label = "Não atribuído"
        
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            profile.save()
        return profile
