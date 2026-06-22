import datetime
import requests
from django.conf import settings
from django.utils import timezone
from barbearia.models import Booking, Profile, Notification

def clean_phone_number(phone):
    """
    Limpa o número de telefone para corresponder aos requisitos da API.
    Retorna apenas dígitos e garante que comece com 55 (DDI do Brasil).
    """
    if not phone:
        return None
    cleaned = "".join(c for c in phone if c.isdigit())
    if not cleaned:
        return None
    # Se não começar com 55 e tiver o tamanho típico de número brasileiro (10 ou 11 dígitos), adiciona o 55 no início
    if len(cleaned) in [10, 11] and not cleaned.startswith("55"):
        cleaned = "55" + cleaned
    return cleaned

def send_whatsapp_message(number, message):
    """
    Envia uma requisição POST para a API de WhatsApp da Codesflow.
    """
    url = getattr(settings, "WHATSAPP_API_URL", "https://appbks.codesflow.com.br/api/messages/send")
    token = getattr(settings, "WHATSAPP_API_TOKEN", "")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "number": number,
        "body": message,
        "userId": "",
        "queueId": "",
        "sendSignature": True,
        "closeTicket": False
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            print(f"Mensagem enviada com sucesso para {number}")
            return True
        else:
            print(f"Erro ao enviar para {number}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Falha na requisição para {number}: {str(e)}")
        return False

def send_daily_reminders():
    """
    Envia mensagens de lembrete por WhatsApp para todos os clientes agendados para hoje
    que ainda não foram notificados.
    """
    today = timezone.localdate()
    bookings = Booking.objects.filter(
        date=today,
        status="AGENDADO",
        notified_day_of=False
    ).select_related("client", "barber", "service")
    
    sent_count = 0
    for booking in bookings:
        phone = clean_phone_number(booking.client.profile.phone)
        if not phone:
            print(f"Cliente {booking.client.username} sem telefone válido.")
            continue
            
        client_name = booking.client.first_name or booking.client.username
        barber_name = booking.barber.get_full_name() or booking.barber.username
        service_name = booking.service.name
        time_str = booking.time.strftime("%H:%M")
        
        message = (
            f"Olá, {client_name}! 💈\n\n"
            f"Passando para lembrar que você tem um horário agendado hoje na *BarberHub*!\n"
            f"📅 *Data:* Hoje ({booking.date.strftime('%d/%m/%Y')})\n"
            f"⏰ *Horário:* {time_str}\n"
            f"💇‍♂️ *Serviço:* {service_name}\n"
            f"🧔 *Barbeiro:* {barber_name}\n\n"
            f"Por favor, tente chegar com 5 minutos de antecedência. Te esperamos lá!"
        )
        
        success = send_whatsapp_message(phone, message)
        if success:
            booking.notified_day_of = True
            booking.save(update_fields=["notified_day_of"])
            sent_count += 1
            
    return sent_count

def send_booking_confirmation_request(booking):
    """
    Envia uma mensagem de solicitação de confirmação por WhatsApp para o cliente de um agendamento específico.
    """
    phone = clean_phone_number(booking.client.profile.phone)
    if not phone:
        print(f"Cliente {booking.client.username} sem telefone válido para confirmação.")
        return False
        
    client_name = booking.client.first_name or booking.client.username
    barber_name = booking.barber.get_full_name() or booking.barber.username
    service_name = booking.service.name
    date_str = booking.date.strftime("%d/%m/%Y")
    time_str = booking.time.strftime("%H:%M")
    
    message = (
        f"Olá, {client_name}! 💈\n\n"
        f"Gostaríamos de confirmar o seu agendamento na *BarberHub*:\n"
        f"📅 *Data:* {date_str}\n"
        f"⏰ *Horário:* {time_str}\n"
        f"💇‍♂️ *Serviço:* {service_name}\n"
        f"🧔 *Barbeiro:* {barber_name}\n\n"
        f"Por favor, responda a esta mensagem com *SIM* para confirmar ou *NÃO* para cancelar seu horário."
    )
    
    return send_whatsapp_message(phone, message)

def send_all_confirmation_requests_for_tomorrow():
    """
    Envia solicitações de confirmação de agendamento por WhatsApp para todos os clientes agendados para amanhã.
    """
    tomorrow = timezone.localdate() + datetime.timedelta(days=1)
    bookings = Booking.objects.filter(
        date=tomorrow,
        status="AGENDADO"
    ).select_related("client", "barber", "service")
    
    sent_count = 0
    for booking in bookings:
        success = send_booking_confirmation_request(booking)
        if success:
            sent_count += 1
            
    return sent_count

def send_one_hour_before_reminders():
    """
    Envia notificações por WhatsApp 1 hora antes do horário agendado.
    Busca agendamentos cujo horário de atendimento está entre (agora + 45min) e (agora + 75min).
    """
    today = timezone.localdate()
    now_time = timezone.localtime().time()
    
    # Calcula o intervalo de tempo: de 45 minutos a 75 minutos a partir de agora
    now_dt = datetime.datetime.combine(today, now_time)
    start_time = (now_dt + datetime.timedelta(minutes=45)).time()
    end_time = (now_dt + datetime.timedelta(minutes=75)).time()
    
    bookings = Booking.objects.filter(
        date=today,
        status="AGENDADO",
        time__gte=start_time,
        time__lte=end_time,
        notified_one_hour_before=False
    ).select_related("client", "barber", "service")
    
    sent_count = 0
    for booking in bookings:
        phone = clean_phone_number(booking.client.profile.phone)
        if not phone:
            continue
            
        client_name = booking.client.first_name or booking.client.username
        time_str = booking.time.strftime("%H:%M")
        
        message = (
            f"Ei, {client_name}! ⏳\n\n"
            f"Seu horário na *BarberHub* está chegando! Seu corte está marcado para as *{time_str}* (daqui a aproximadamente 1 hora).\n\n"
            f"Contamos com a sua presença!"
        )
        
        success = send_whatsapp_message(phone, message)
        if success:
            booking.notified_one_hour_before = True
            booking.save(update_fields=["notified_one_hour_before"])
            sent_count += 1
            
    return sent_count


def send_subscription_billing_reminders():
    """
    Envia lembretes de cobrança de mensalidade por WhatsApp para os clientes.
    Verifica vencimentos hoje, em 3 dias e atrasados em 1 dia.
    """
    today = timezone.localdate()
    three_days_later = today + datetime.timedelta(days=3)
    yesterday = today - datetime.timedelta(days=1)
    
    # 1. Mensalidades vencendo em 3 dias (aviso prévio)
    profiles_3_days = Profile.objects.filter(
        role="CLIENTE",
        plan_active=True,
        plan__isnull=False,
        plan_due_date=three_days_later
    ).select_related("user", "plan")
    
    sent_count = 0
    for p in profiles_3_days:
        phone = clean_phone_number(p.phone)
        if not phone:
            continue
        client_name = p.user.first_name or p.user.username
        plan_name = p.plan.name
        price_str = str(p.plan.price)
        date_str = three_days_later.strftime("%d/%m/%Y")
        
        message = (
            f"Olá, {client_name}! 💈\n\n"
            f"Lembramos que a mensalidade do seu plano *{plan_name}* vence em 3 dias (no dia {date_str}), no valor de R$ {price_str}.\n\n"
            f"Você pode realizar o pagamento no seu próximo corte ou diretamente com seu barbeiro!"
        )
        
        success = send_whatsapp_message(phone, message)
        if success:
            Notification.objects.create(
                client=p.user,
                message=f"Lembrete: A mensalidade do plano {plan_name} vence em 3 dias ({date_str}) no valor de R$ {price_str}."
            )
            sent_count += 1
            
    # 2. Mensalidades vencendo hoje
    profiles_today = Profile.objects.filter(
        role="CLIENTE",
        plan_active=True,
        plan__isnull=False,
        plan_due_date=today
    ).select_related("user", "plan")
    
    for p in profiles_today:
        phone = clean_phone_number(p.phone)
        if not phone:
            continue
        client_name = p.user.first_name or p.user.username
        plan_name = p.plan.name
        price_str = str(p.plan.price)
        date_str = today.strftime("%d/%m/%Y")
        
        message = (
            f"Olá, {client_name}! 💈\n\n"
            f"Lembramos que a mensalidade do seu plano *{plan_name}* vence hoje ({date_str}), no valor de R$ {price_str}.\n\n"
            f"Por favor, regularize o pagamento com o seu barbeiro para continuar usufruindo dos benefícios!"
        )
        
        success = send_whatsapp_message(phone, message)
        if success:
            Notification.objects.create(
                client=p.user,
                message=f"Lembrete: A mensalidade do plano {plan_name} vence hoje ({date_str}) no valor de R$ {price_str}."
            )
            sent_count += 1
            
    # 3. Mensalidades vencidas ontem (atrasadas)
    profiles_yesterday = Profile.objects.filter(
        role="CLIENTE",
        plan_active=True,
        plan__isnull=False,
        plan_due_date=yesterday
    ).select_related("user", "plan")
    
    for p in profiles_yesterday:
        phone = clean_phone_number(p.phone)
        if not phone:
            continue
        client_name = p.user.first_name or p.user.username
        plan_name = p.plan.name
        price_str = str(p.plan.price)
        date_str = yesterday.strftime("%d/%m/%Y")
        
        message = (
            f"Atenção, {client_name}! ⚠️\n\n"
            f"Constatamos que a mensalidade do seu plano *{plan_name}* (R$ {price_str}) venceu ontem ({date_str}) e não foi identificada.\n\n"
            f"Por favor, entre em contato para regularizar seu plano e manter seus cortes ativos!"
        )
        
        success = send_whatsapp_message(phone, message)
        if success:
            Notification.objects.create(
                client=p.user,
                message=f"Alerta: A mensalidade do plano {plan_name} venceu ontem ({date_str}) no valor de R$ {price_str}."
            )
            sent_count += 1
            
    return sent_count
