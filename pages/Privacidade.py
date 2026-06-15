"""
Política de Privacidade — Vigil Summit 2026.
Exige conformidade com a LGPD (Lei 13.709/2018).
"""

import streamlit as st

st.set_page_config(page_title="Política de Privacidade — Vigil Summit", page_icon="🔒")

st.markdown("# 🔒 Política de Privacidade")
st.markdown("**Vigil Summit 2026 | Atualizado em junho de 2026**")

st.markdown("""
## 1. Quem trata seus dados
Os dados coletados neste formulário são tratados pela **Vigil.AI**, operacionalizado
pela **Pareto**, para fins exclusivos de gestão do evento Vigil Summit 2026.

## 2. Quais dados coletamos e por quê
| Dado | Finalidade | Base legal (LGPD) |
|---|---|---|
| Nome, e-mail, telefone | Confirmação de inscrição e comunicações do evento | Consentimento — Art. 7º, I |
| Cargo e empresa | Personalização das comunicações e qualificação do público | Interesse legítimo — Art. 7º, IX |
| LinkedIn | Enriquecimento de perfil com dados públicos | Interesse legítimo — Art. 7º, IX |
| Áreas de interesse e formação | Personalização de conteúdo e pontuação de propensão | Consentimento — Art. 7º, I |

## 3. Decisões automatizadas (Art. 20º)
Utilizamos um modelo de machine learning para calcular uma **pontuação de propensão**
com base nos dados fornecidos e em informações públicas. Essa pontuação orienta a
personalização das comunicações e a abordagem da equipe comercial no evento.

Você tem direito a solicitar **revisão humana** de qualquer decisão automatizada
que afete você, pelo e-mail: privacidade@vigilsummit.com.br

## 4. Por quanto tempo guardamos seus dados
Os dados são mantidos por até **12 meses** após o evento para fins de relacionamento
comercial. Após esse prazo, os dados são anonimizados ou excluídos.

## 5. Seus direitos (Art. 17º a 22º)
Você pode a qualquer momento:
- **Acessar** os dados que temos sobre você
- **Corrigir** informações incorretas
- **Solicitar exclusão** dos seus dados
- **Revogar** o consentimento
- **Solicitar portabilidade** dos dados em formato aberto (JSON)
- **Opor-se** a decisões automatizadas

Para exercer qualquer direito: **privacidade@vigilsummit.com.br**
Prazo de resposta: até 15 dias úteis.

## 6. Segurança
Adotamos medidas técnicas de segurança conforme o Art. 46º da LGPD:
dados armazenados em banco com acesso restrito, credenciais protegidas
por variáveis de ambiente e comunicações via canal criptografado.

## 7. Contato
Dúvidas sobre privacidade: **privacidade@vigilsummit.com.br**
""")

st.divider()
st.markdown(
    "<center><small>Vigil Summit 2026 · Realização Vigil.AI · "
    "Em conformidade com a Lei 13.709/2018 (LGPD)</small></center>",
    unsafe_allow_html=True,
)
