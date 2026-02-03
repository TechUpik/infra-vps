# INFRA VPS

Infraestrutura base para VPS utilizando **Docker + Docker Compose**, focada em automação, orquestração de fluxos, proxy reverso e gerenciamento de containers.

O projeto centraliza serviços comuns de backend em uma VPS, com separação clara por stack e fácil manutenção.

---

## 🧱 Stack Utilizada

* **Traefik** – Proxy reverso e gerenciamento de certificados SSL (Let's Encrypt)
* **Portainer** – Interface web para gerenciamento de containers Docker
* **n8n** – Automação de workflows (low-code)
* **Prefect** – Orquestração de fluxos de dados e jobs Python

---

## 📁 Estrutura do Projeto

```
INFRA VPS
│
├── n8n/
│   └── docker-compose.yml
│
├── portainer/
│   └── docker-compose.yml
│
├── prefect/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── flows/
│       ├── backup_ambientes_b2b.py
│       └── exemplo_flow.py
│
├── traefik/
│   ├── docker-compose.yml
│   ├── traefik.toml
│   ├── traefik_dynamic.toml
│   └── acme.json
│
└── README.md
```

---

## 🚦 Serviços

### 🔀 Traefik

Responsável por:

* Proxy reverso
* Roteamento por domínio
* SSL automático com Let's Encrypt

Arquivos importantes:

* `traefik.toml`: configuração estática
* `traefik_dynamic.toml`: rotas e middlewares dinâmicos
* `acme.json`: certificados SSL (⚠️ manter permissão 600)

Inicialização:

```bash
cd traefik
docker compose up -d
```

---

### 🐳 Portainer

Interface web para gerenciamento do Docker:

* Containers
* Volumes
* Networks

Inicialização:

```bash
cd portainer
docker compose up -d
```

Acesso via navegador (exemplo):

```
https://portainer.seudominio.com
```

---

### 🔄 n8n

Ferramenta de automação de workflows:

* Integrações
* Jobs recorrentes
* APIs e Webhooks

Inicialização:

```bash
cd n8n
docker compose up -d
```

Acesso via navegador:

```
https://n8n.seudominio.com
```

---

### 🧠 Prefect

Orquestração de fluxos Python:

* Jobs agendados
* Pipelines de dados
* Monitoramento de execução

Arquivos:

* `Dockerfile`: imagem customizada
* `docker-compose.yml`: stack do Prefect
* `flows/`: definição dos fluxos

Exemplos de flows:

* `backup_ambientes_b2b.py`
* `exemplo_flow.py`

Inicialização:

```bash
cd prefect
docker compose up -d --build
```

---

## ⚙️ Pré-requisitos

* Docker
* Docker Compose
* VPS com portas 80 e 443 liberadas
* Domínio apontando para o IP da VPS

---

## 🔐 Observações Importantes

* Garanta permissão correta do `acme.json`:

```bash
chmod 600 traefik/acme.json
```

* Recomenda-se criar uma **network Docker externa** para o Traefik:

```bash
docker network create traefik
```

* Todos os serviços devem estar conectados a essa network

---

## 🚀 Subindo tudo

Ordem recomendada:

1. Traefik
2. Portainer
3. n8n
4. Prefect

---

## 📌 Objetivo do Projeto

Padronizar e acelerar a criação de infraestrutura em VPS para:

* Automações
* Pipelines de dados
* Backends internos
* Projetos pessoais ou B2B

---

## 📄 Licença

Uso interno / privado.
