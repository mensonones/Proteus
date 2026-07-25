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
