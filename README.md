# 🛡️ PGCC Platform v0.5 - Plateforme GRC Souveraine & IA Locale

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Vue.js](https://img.shields.io/badge/vuejs-v3-brightgreen.svg)
![FastAPI](https://img.shields/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=flat&logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/ollama-%23000000.svg?style=flat&logo=ollama&logoColor=white)

> **Plateforme de Gouvernance des Risques Cyber (GRC) conforme ISO 27002:2022, intégrant une Intelligence Artificielle Souveraine (Locale) pour l'analyse automatisée des écarts et la gestion documentaire.**

## 🌟 Vision & Innovation

La plupart des solutions GRC (Governance, Risk, Compliance) sont cloud-based, coûteuses et exposent les données sensibles de l'entreprise à des tiers. 

**PGCC Platform** change la donne en offrant :
1.  **Souveraineté Totale :** Toutes les données restent dans votre infrastructure (Docker + PostgreSQL local). Aucune fuite vers le cloud public.
2.  **IA Locale (RAG) :** Utilisation d'Ollama (modèles Phi3/Llama3/Nomic-Embed) pour analyser vos PSSI et procédures sans envoyer de données externes. L'IA comprend le contexte métier spécifique à votre organisation.
3.  **Conformité Native :** Matrice dynamique couvrant les **93 contrôles officiels** de la norme ISO/IEC 27002:2022, répartis en 4 domaines (Organisationnel, Personnes, Physique, Technologique).
4.  **Graphe de Connaissances :** Liaisons sémantiques automatiques entre Risques ↔ Applications ↔ Serveurs ↔ Contrôles ISO pour une vision holistique du SI.

## 🏗️ Architecture Technique

Le projet suit une architecture moderne, scalable et conteneurisée.

### Stack Backend (Python)
*   **Framework :** [FastAPI](https://fastapi.tiangolo.com/) (Asynchrone haute performance).
*   **ORM :** SQLAlchemy 2.0 (Async) + AsyncPG.
*   **Base de Données :** PostgreSQL 15+ avec extension **PgVector** (pour le stockage vectoriel RAG).
*   **Auth :** JWT (JSON Web Tokens) + RBAC (Role-Based Access Control) granulaire.
*   **IA Service :** Client HTTP asynchrone vers Ollama (`httpx`).

### Stack Frontend (JavaScript)
*   **Framework :** Vue.js 3 (Composition API).
*   **Build Tool :** Vite (Ultra-rapide HMR).
*   **State Management :** Pinia.
*   **UI Components :** Design System custom inspiré TailwindCSS / Material Design.

### Infrastructure
*   **Orchestration :** Docker Compose.
*   **Services :** Postgres (DB), Backend (API), Frontend (SPA), Ollama (Host Machine).

## 🧭 Architecture cible et documentation

La référence d'architecture pour les évolutions futures est documentée dans :

- [Architecture cible](docs/ARCHITECTURE_TARGET.md)
- [Modèle de données cible](docs/TARGET_DATA_MODEL.md)
- [Interactions entre modules](docs/MODULE_INTERACTIONS.md)

Ces documents définissent l'orientation modulaire de PGCC et la roadmap. Ils ne remplacent pas l'analyse du code existant avant une migration.

## 📂 Structure du Projet

```text
pgcc-platform/
├── backend/                # API RESTful FastAPI
│   ├── app/
│   │   ├── api/v1/endpoints/ # Routes (Auth, Risks, Apps, ISO, Docs, AI)
│   │   ├── models/           # Entités SQLAlchemy (Risk, Application, DocumentChunk...)
│   │   ├── services/         # Logique métier (RBAC, RAGService, Extractor)
│   │   └── core/             # Config DB, Security, Settings
│   ├── scripts/              # Scripts utilitaires (Seed ISO, Init DB, Build Graph)
│   └── requirements.txt      # Dépendances Python
├── frontend/               # SPA Vue.js
│   ├── src/
│   │   ├── views/            # Pages principales (Dashboard, RisksView, IsoComplianceView...)
│   │   ├── components/       # Composants réutilisables (AppLayout, ModalUpload...)
│   │   ├── stores/           # État global Pinia (Auth store)
│   │   └── router/           # Configuration routes protégées
│   └── package.json          # Dépendances Node/NPM
├── docker-compose.yaml     # Orchestration des containers
├── .env.example            # Template variables d'environnement (SECRET_KEY, DB_PASS...)
└── README.md               # Ce fichier