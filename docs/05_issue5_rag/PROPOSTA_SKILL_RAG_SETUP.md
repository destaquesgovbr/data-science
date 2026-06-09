# Proposta: Skill "rag-setup" para Claude Code

**Data:** 2026-06-09  
**Autor:** Luis Felipe de Moraes  
**Objetivo:** Automatizar setup completo de ambientes RAG

---

## 🎯 Problema

Durante a escala de 250 → 10k notícias, identificamos que **redescobrir o roteiro de setup consome tempo significativo**:

- ⏱️ **15-20 minutos** de troubleshooting por ambiente novo
- 🔄 **8 problemas recorrentes** (senha postgres, schema, PYTHONPATH, etc)
- 📝 **Múltiplas tentativas** até acertar configuração
- 🧠 **Conhecimento implícito** que precisa ser redescoberto

**Impacto:**
- Setup manual propenso a erros
- Tempo desperdiçado em problemas já resolvidos
- Dificuldade para novos membros do time
- Risco de deploy inconsistente

---

## 💡 Solução Proposta: Skill `rag-setup`

### O que é?

Uma **Skill do Claude Code** que encapsula todo o conhecimento de setup de ambientes RAG, automatizando:

1. Detecção de ambiente (local vs EC2 vs Docker)
2. Instalação de dependências
3. Configuração de PostgreSQL + pgvector
4. Criação de schema correto
5. Setup de virtual environment
6. Configuração de variáveis de ambiente
7. Validação do setup completo

### Como Funciona?

```bash
# No Claude Code ou terminal
/rag-setup --env ec2

# Ou com parâmetros
/rag-setup --env local --database ragdb_dev --reset
```

**O Claude Code:**
1. Detecta o ambiente atual
2. Executa `setup_ec2_environment.sh` (já criado)
3. Valida cada etapa
4. Reporta progresso em tempo real
5. Troubleshooting automático se algo falhar

---

## 📋 Funcionalidades da Skill

### Comandos Principais

```bash
# Setup completo
/rag-setup --env {local|ec2|docker}

# Apenas database
/rag-setup --database-only

# Apenas Python environment
/rag-setup --python-only

# Reset completo (cuidado!)
/rag-setup --reset --env ec2

# Validar setup existente
/rag-setup --validate

# Troubleshooting interativo
/rag-setup --diagnose
```

### Parâmetros

```
--env           Ambiente alvo: local, ec2, docker
--database      Nome do banco (default: ragdb)
--password      Senha postgres (default: gerada)
--python-ver    Versão Python (default: 3.12)
--gpu           Forçar instalação CUDA (default: auto-detect)
--reset         Resetar ambiente existente
--validate      Apenas validar, não modificar
--diagnose      Modo troubleshooting
--quiet         Modo silencioso (apenas erros)
--verbose       Modo verboso (debug)
```

---

## 🏗️ Arquitetura da Skill

### Estrutura de Diretórios

```
.claude/
└── skills/
    └── rag-setup/
        ├── skill.json           # Metadados da skill
        ├── main.py              # Lógica principal
        ├── templates/
        │   ├── .env.template
        │   ├── database.yaml
        │   └── schema.sql
        ├── validators/
        │   ├── postgres.py
        │   ├── python.py
        │   └── network.py
        └── troubleshooters/
            ├── authentication.py
            ├── dependencies.py
            └── permissions.py
```

### Fluxo de Execução

```
1. DETECÇÃO
   ├─ Detectar OS (Ubuntu, macOS, etc)
   ├─ Detectar se tem PostgreSQL instalado
   ├─ Detectar se tem Python 3.12+
   └─ Detectar se tem GPU (nvidia-smi)

2. VALIDAÇÃO
   ├─ Checar se já existe setup
   ├─ Checar se banco existe
   └─ Avisar se vai sobrescrever

3. INSTALAÇÃO
   ├─ PostgreSQL + pgvector
   ├─ Python dependencies
   └─ Configurações

4. CONFIGURAÇÃO
   ├─ Senha postgres
   ├─ Criar banco + schema
   ├─ Virtual environment
   └─ .env file

5. VALIDAÇÃO FINAL
   ├─ Testar conexão PostgreSQL
   ├─ Testar import Python
   ├─ Testar embedding model
   └─ Gerar relatório

6. TROUBLESHOOTING (se necessário)
   ├─ Diagnóstico automático
   ├─ Sugestões de fix
   └─ Aplicar fixes se autorizado
```

---

## 🎯 Casos de Uso

### Caso 1: Novo Desenvolvedor

```bash
# Desenvolvedor clonando repo pela primeira vez
git clone <repo>
cd data-science

# Setup automático
/rag-setup --env local

# Output:
# ✓ PostgreSQL instalado
# ✓ Banco 'ragdb_dev' criado
# ✓ Schema aplicado (38 tabelas, 12 índices)
# ✓ Python venv criado em .venv/
# ✓ Dependências instaladas (23 packages)
# ✓ .env configurado
# 
# ✅ Setup completo! Próximos passos:
# 1. source .venv/bin/activate
# 2. python scripts/index_corpus.py --help
```

### Caso 2: Deploy Produção

```bash
# SSH na EC2 limpa
ssh user@ec2

# Setup completo em um comando
/rag-setup --env ec2 --database ragdb --password <senha-forte>

# Valida tudo
/rag-setup --validate

# Se OK, indexar
python scripts/index_corpus.py --input data/corpus_50k.json
```

### Caso 3: Troubleshooting

```bash
# Algo deu errado...
/rag-setup --diagnose

# Output:
# ❌ PostgreSQL: senha inválida
#    Fix: sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'nova_senha';"
# 
# ❌ Python: módulo 'psycopg' não encontrado
#    Fix: pip install psycopg[binary]
# 
# ⚠️ Schema: tabela 'document_chunks' sem constraint UNIQUE
#    Fix: ALTER TABLE document_chunks ADD CONSTRAINT...
#
# Aplicar fixes automaticamente? [y/N]
```

### Caso 4: Atualização de Schema

```bash
# Novo schema disponível
git pull

# Atualizar apenas database
/rag-setup --database-only --apply-migrations

# Valida migração
/rag-setup --validate
```

---

## 🔧 Implementação

### skill.json

```json
{
  "name": "rag-setup",
  "version": "1.0.0",
  "description": "Automated setup for RAG Q&A systems",
  "author": "Luis Felipe de Moraes",
  "requires": {
    "claude-code": ">=1.0.0",
    "python": ">=3.12",
    "os": ["ubuntu", "debian", "macos"]
  },
  "commands": {
    "setup": {
      "description": "Full environment setup",
      "parameters": [
        {"name": "env", "type": "choice", "choices": ["local", "ec2", "docker"], "required": true},
        {"name": "database", "type": "string", "default": "ragdb"},
        {"name": "reset", "type": "boolean", "default": false}
      ]
    },
    "validate": {
      "description": "Validate existing setup",
      "parameters": []
    },
    "diagnose": {
      "description": "Diagnose and fix issues",
      "parameters": [
        {"name": "auto-fix", "type": "boolean", "default": false}
      ]
    }
  },
  "scripts": {
    "pre-setup": "scripts/pre_check.sh",
    "setup": "scripts/setup_ec2_environment.sh",
    "post-setup": "scripts/validate_setup.py",
    "diagnose": "scripts/diagnose_environment.py"
  }
}
```

### main.py (pseudo-código)

```python
#!/usr/bin/env python3
"""
RAG Setup Skill - Main Entry Point
"""

import sys
from pathlib import Path
from skill_framework import Skill, Command, Parameter

class RAGSetupSkill(Skill):
    name = "rag-setup"
    version = "1.0.0"
    
    @Command(
        description="Full environment setup",
        parameters=[
            Parameter("env", choices=["local", "ec2", "docker"], required=True),
            Parameter("database", type=str, default="ragdb"),
            Parameter("reset", type=bool, default=False)
        ]
    )
    def setup(self, env: str, database: str, reset: bool):
        """Execute full setup"""
        
        # 1. Detect current state
        state = self.detect_environment()
        self.print_state(state)
        
        # 2. Warn if reset needed
        if state.has_existing and not reset:
            if not self.confirm("Existing setup detected. Reset?"):
                return
        
        # 3. Execute setup script
        result = self.run_script(f"setup_{env}.sh", {
            "DATABASE": database,
            "RESET": reset
        })
        
        # 4. Validate
        if result.success:
            validation = self.validate()
            if validation.all_passed:
                self.success("✅ Setup complete!")
                self.print_next_steps()
            else:
                self.warning("⚠️ Setup complete but validation failed")
                self.print_issues(validation.issues)
        else:
            self.error("❌ Setup failed")
            self.troubleshoot(result.error)
    
    @Command(description="Validate existing setup")
    def validate(self):
        """Validate all components"""
        checks = [
            self.check_postgres(),
            self.check_python(),
            self.check_schema(),
            self.check_dependencies()
        ]
        return ValidationResult(checks)
    
    @Command(
        description="Diagnose and fix issues",
        parameters=[
            Parameter("auto_fix", type=bool, default=False)
        ]
    )
    def diagnose(self, auto_fix: bool):
        """Diagnose problems and suggest/apply fixes"""
        issues = self.scan_for_issues()
        
        for issue in issues:
            self.print_issue(issue)
            self.print_fix(issue.fix)
            
            if auto_fix:
                if self.confirm(f"Apply fix for '{issue.name}'?"):
                    self.apply_fix(issue.fix)

if __name__ == "__main__":
    skill = RAGSetupSkill()
    skill.run()
```

---

## 📊 Benefícios Esperados

### Métricas de Sucesso

| Métrica | Antes | Depois (Skill) | Melhoria |
|---------|-------|----------------|----------|
| Tempo de setup | 15-20 min | 2-3 min | **-85%** |
| Taxa de erro | 60% | 5% | **-92%** |
| Tentativas até sucesso | 3-5 | 1 | **-80%** |
| Conhecimento necessário | Alto | Baixo | **+80% acessibilidade** |

### ROI

**Tempo economizado por setup:**
- Manual: 20 minutos
- Skill: 3 minutos
- **Economia: 17 minutos**

**Cenários:**
- 10 setups/mês × 17 min = **3 horas/mês**
- 100 setups/ano × 17 min = **28 horas/ano**
- Com 5 desenvolvedores = **140 horas/ano**

**Valor adicional:**
- ✅ Redução de frustração
- ✅ Onboarding mais rápido
- ✅ Deploy consistente
- ✅ Menos tickets de suporte

---

## 🚀 Roadmap de Implementação

### Fase 1: MVP (1 semana)
- [ ] Criar `skill.json`
- [ ] Integrar `setup_ec2_environment.sh` existente
- [ ] Comando básico `/rag-setup --env local`
- [ ] Validação simples (postgres + python)

### Fase 2: Validação e Diagnóstico (1 semana)
- [ ] Comando `/rag-setup --validate`
- [ ] Comando `/rag-setup --diagnose`
- [ ] Auto-fix para 8 problemas comuns
- [ ] Relatório detalhado de estado

### Fase 3: Multi-Ambiente (1 semana)
- [ ] Suporte EC2 completo
- [ ] Suporte Docker
- [ ] Detecção automática de ambiente
- [ ] Templates configuráveis

### Fase 4: Avançado (2 semanas)
- [ ] Migração de schema automática
- [ ] Backup/restore integrado
- [ ] Monitoramento de saúde
- [ ] Integração com CI/CD

---

## 🤔 Alternativas Consideradas

### 1. Apenas Script Bash
- ✅ Simples de implementar
- ❌ Sem inteligência (não adapta a situações)
- ❌ Troubleshooting manual
- **Decisão:** Insuficiente

### 2. Ansible Playbook
- ✅ Poderoso e maduro
- ❌ Curva de aprendizado alta
- ❌ Overhead para casos simples
- **Decisão:** Over-engineering

### 3. Docker Compose
- ✅ Ambiente isolado
- ❌ Não resolve setup de host EC2
- ❌ Overhead de containers
- **Decisão:** Complementar, não substituto

### 4. Skill do Claude Code ✅
- ✅ Inteligente (adapta a problemas)
- ✅ Integrado ao fluxo de trabalho
- ✅ Aprende com contexto
- ✅ Troubleshooting automático
- **Decisão:** ESCOLHIDO

---

## ✅ Recomendação

**Implementar Skill `rag-setup` com prioridade ALTA**

### Justificativa

1. **ROI positivo em <1 mês** (28h economizadas/ano)
2. **Reduz barreira de entrada** para novos desenvolvedores
3. **Previne erros custosos** em produção
4. **Documenta conhecimento implícito** de forma executável
5. **Escalável** para outros projetos RAG do time

### Próximos Passos

1. ✅ Aprovar proposta (este documento)
2. 📝 Criar issue no repositório
3. 🏗️ Implementar Fase 1 (MVP)
4. 🧪 Testar com 3 desenvolvedores
5. 📊 Medir métricas de sucesso
6. 🚀 Deploy para todo o time

---

**Criado em:** 2026-06-09  
**Status:** 📋 Proposta para aprovação  
**Prioridade:** 🔴 Alta  
**Esforço estimado:** 3-5 semanas  
**ROI estimado:** 140 horas/ano
