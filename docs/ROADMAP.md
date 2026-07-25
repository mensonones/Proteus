# Proteus Customization Roadmap

Este documento rastreia ideias e melhorias sugeridas para personalização contínua do Proteus e suas skills de Red Teaming.

## Agentic Exploit Sandbox (Agente Cicada)

**Objetivo:** Evoluir a fase de exploração e desenvolvimento de PoCs (Agente Cicada) de verificações puramente lógicas/estáticas para validações ativas em tempo de execução 100% isoladas.

**Contexto e Motivação:**
Inspirado por frameworks de 2025/2026 como o *OpenAnt* e o *ProjectDiscovery Neo*, o "Padrão Ouro" da pesquisa de vulnerabilidade em IA agora exige que os achados (findings) comprovem a sua explorabilidade (*adversarial verification*). Como o Proteus já conta com defesas anti-slop excelentes (como o agente Skeptic e seus 11 Gates), o próximo gargalo para reduzir o atrito do analista humano é automatizar a execução da PoC gerada num laboratório blindado.

**Proposta de Implementação (Conceito):**
- Expandir o comando `proteus lab create` (ou as skills associadas ao *Cicada/Artificer*) para suportar a criação instantânea de containeres efêmeros/descartáveis (ex: Docker) baseados nos artefatos da target.
- O agente `Cicada` passará a desenvolver o script de exploit, disparar a criação da Sandbox, injetar a PoC na rede isolada da Sandbox e capturar o retorno de execução (stdout/stderr).
- **Validação Autônoma:** O resultado de execução da Sandbox servirá de insumo irrevogável para atestar que o bug é explorável de fato. Se o contêiner colapsar com o comportamento esperado do exploit, o *Skeptic* será automaticamente desarmado em relação ao Gate 11 (PoC Dependency).

**Benefícios Esperados:**
- Evita danos acidentais aos servidores de produção da target (visto que o sandbox seria um espelho enxuto gerado a partir do código fonte analisado).
- Eleva o *confidence level* do reporte gerado para próximo de 100%, economizando horas de triagem humana na tentativa de reproduzir configurações peculiares localmente.

> [!NOTE]
> **Status:** ✅ **Implementado** (Arquitetura atualizada: `proteus-cicada.md` e `poc-exploit` agora forçam a geração e execução do sandbox).

---

## 0-Day Discovery Agent (Agente "Maverick")

**Objetivo:** Introduzir um agente dedicado exclusivamente à descoberta de vulnerabilidades lógicas inéditas e 0-days (*Lateral Thinking* e *First Principles*), sem sofrer de "Esquizofrenia de Prompt" ao tentar encontrar bugs convencionais.

**Contexto e Motivação:**
Os LLMs atuais são exímios no reconhecimento de padrões (ex: identificar um XSS ou SQLi clássico). No entanto, forçá-los a procurar bugs tradicionais *e* pensar de forma criativa/absurda no mesmo prompt gera degradação na qualidade da análise. Para encontrar falhas de lógica de negócios severas ou encadeamentos imprevistos (0-days), é necessário um escopo de análise que ignore totalmente o OWASP Top 10 e foque puramente na manipulação de Invariantes e Máquinas de Estado do alvo.

**Proposta de Implementação (Conceito):**
- Criar um novo especialista paralelo na suíte Chimera (ex: `proteus-maverick`).
- **Prompt Isolation:** O *Maverick* será instruído a assumir que o código é 100% seguro contra injeções técnicas. Sua única missão é propor teorias de abuso de features (*Feature Abuse Chaining*) e fluxos ilógicos.
- **Integração com o Coordinator:** Na mesma rodada (Round), o Coordenador delegará a análise de código para a Força-Tarefa padrão (Argus, Loom, Chaos) para varredura de falhas técnicas, e para o *Maverick* para análise puramente lógica.
- **Validação Cruzada:** As teorias "insanas" do *Maverick* serão enviadas diretamente ao agente *Skeptic* (Devil's Advocate), que as submeterá aos rigorosos 11 Gates do Proteus. Apenas teorias lógicas sólidas que provarem impacto e viabilidade chegarão ao relatório final.

**Benefícios Esperados:**
- Permite que o Proteus escale para descobrir falhas estruturais massivas (frequentemente as mais bem pagas em Bug Bounty) sem poluir a eficácia dos agentes focados na caça a N-days.

> [!NOTE]
> **Status:** ✅ **Implementado** (Agente `proteus-maverick` instanciado com isolamento de prompt focado em Lateral Thinking; skill de setup `zero-day-maverick` integrada ao comando unificado).
