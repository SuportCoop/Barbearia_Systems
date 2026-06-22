# 💈 Documentação do Sistema - BarberHub

Bem-vindo à documentação oficial do sistema da **BarberHub**. Este documento detalha todas as funcionalidades disponíveis, regras de negócio e integrações da plataforma para apoiar na administração e atendimento aos clientes.

---

## 👥 1. Perfis e Controle de Acesso (Roles)

O sistema gerencia acessos por meio de três níveis de usuários em `Profile`:
*   **CLIENTE**:
    *   Visualiza barbeiros e serviços disponíveis.
    *   Agenda cortes de cabelo e barba de forma online e autônoma.
    *   Consulta e reserva produtos do estoque para retirada na loja física.
    *   Recebe lembretes no sistema e via WhatsApp.
    *   Visualiza os detalhes do seu plano ativo e a data de vencimento.
*   **BARBEIRO**:
    *   Acessa um painel administrativo (Dashboard) personalizado.
    *   Agenda horários e cadastra novos clientes diretamente pelo painel (com auto-vinculação do cliente à sua carteira).
    *   Gerencia o expediente e os horários de pausa individuais.
    *   Atribui e atualiza planos de mensalistas aos clientes.
    *   Acompanha indicadores de faturamento pessoal (diário, semanal e mensalistas).
*   **DESENVOLVEDOR (Admin)**:
    *   Acesso irrestrito a todas as áreas administrativas.
    *   CRUD completo (criação, edição e exclusão) de todos os usuários.
    *   Habilidade de forçar alteração de senha inicial para qualquer usuário (`must_change_password`).

---

## 📅 2. Agendamento Online e Sincronização Inteligente

O sistema garante que a agenda funcione sem conflitos e de maneira automática:
*   **Grade de Horários Dinâmica**: O sistema calcula os slots livres com base na duração do serviço escolhido (ex: 30 minutos para corte simples, 60 minutos para barba e corte completo).
*   **Validação de Sobreposição**: Impede que dois agendamentos ocupem o mesmo barbeiro no mesmo horário (rejeição automática no formulário).
*   **Expediente e Pausa Personalizados**: Cada barbeiro configura seu próprio horário de início/fim e sua janela de pausa (ex: almoço). O sistema bloqueia esses períodos automaticamente no grid de agendamento de clientes.
*   **Agendamento em Nome do Cliente**: Permite que o barbeiro preencha a agenda diretamente caso o cliente ligue ou mande mensagem pessoal.
*   **Barbeiro Preferencial**: Opcionalmente, um cliente pode ser associado a um barbeiro específico. Quando logado, esse cliente visualizará apenas a agenda de seu barbeiro preferencial para facilitar o processo.

---

## 💳 3. Clube de Assinatura (Mensalistas)

Modelagem de receita recorrente para fidelização de clientes:
*   **Planos Customizáveis**: Cadastro de planos de assinatura (`SubscriptionPlan`) com nome, preço, descrição e lista detalhada de benefícios (ex: "Cortes de cabelo ilimitados e 10% de desconto em produtos").
*   **Atribuição Simplificada**: O barbeiro vincula um plano ao cliente no perfil dele, definindo o status como ativo e registrando o dia do vencimento (`plan_due_date`).
*   **Cálculo de Faturamento**: Mensalidades de planos ativos entram diretamente na projeção de faturamento mensal do barbeiro responsável.

---

## 💬 4. Notificações e Lembretes via WhatsApp (Integração Codesflow)

O sistema conta com um motor automatizado (`tasks.py` acionado por tarefas diárias ou comandos do sistema) integrado ao WhatsApp:
*   **Solicitação de Confirmação**: Enviado na véspera do corte solicitando que o cliente responda "SIM" para confirmar ou "NÃO" para cancelar o agendamento.
*   **Lembrete do Dia**: Enviado todas as manhãs para os clientes com agendamento no dia, contendo data, hora, serviço e barbeiro.
*   **Lembrete de Última Hora**: Enviado automaticamente **1 hora antes** do horário reservado.
*   **Cobranças de Mensalidades**:
    *   **Aviso Prévio (3 dias antes)**: Lembra o cliente que o plano vencerá em breve e informa o valor.
    *   **No Dia (Hoje)**: Alerta sobre o vencimento no dia e orienta a regularização.
    *   **Atrasado (1 dia após)**: Envia uma notificação de atenção amigável sobre o vencimento ocorrido ontem para regularizar o plano.
*   **Log de Notificações Internas**: Além das mensagens no WhatsApp, todas as cobranças e avisos ficam salvos no histórico interno (`Notification` no banco de dados) que o cliente visualiza ao fazer login.

---

## 🛍️ 5. Venda e Reserva de Produtos

*   **Vitrine Digital**: Clientes visualizam produtos em estoque com fotos, descrição e preços.
*   **Reserva de Retirada**: Clientes podem reservar produtos para pagamento presencial no dia do corte.
*   **Controle de Estoque Automatizado**: No momento da reserva, o estoque do produto é debitado para evitar quebras de estoque físicas. Em caso de cancelamento da reserva, o estoque é reabastecido automaticamente.

---

## 📊 6. Painel Financeiro e Métricas (Dashboard)

Cada barbeiro tem acesso a um painel simples e robusto com os seguintes dados:
*   **Faturamento Diário**: Valor total dos serviços com status `CONCLUIDO` prestados no dia de hoje.
*   **Faturamento Semanal**: Valor acumulado de serviços concluídos na semana corrente.
*   **Mensalistas Ativos**: Contagem dos clientes da sua carteira que possuem assinatura ativa.
*   **Faturamento Mensal Estimado**: Soma do faturamento dos serviços concluídos no mês mais o valor fixo das mensalidades ativas do seu portfólio.
