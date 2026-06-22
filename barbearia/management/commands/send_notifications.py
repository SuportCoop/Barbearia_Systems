from django.core.management.base import BaseCommand
from barbearia.tasks import send_daily_reminders, send_one_hour_before_reminders, send_subscription_billing_reminders


class Command(BaseCommand):
    help = "Envia mensagens automáticas de WhatsApp para agendamentos do dia, 1 hora antes do corte e cobranças de plano."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando processamento de notificações de WhatsApp...")
        
        daily_sent = send_daily_reminders()
        self.stdout.write(self.style.SUCCESS(f"{daily_sent} lembretes diários enviados."))
        
        one_hour_sent = send_one_hour_before_reminders()
        self.stdout.write(self.style.SUCCESS(f"{one_hour_sent} lembretes de 1 hora enviados."))
        
        billing_sent = send_subscription_billing_reminders()
        self.stdout.write(self.style.SUCCESS(f"{billing_sent} cobranças/lembretes de planos de assinatura enviados."))
        
        self.stdout.write("Processamento concluído.")

