# 🚛 Diário de Bordo - Carreira Realista (ATS & ETS2)

Um sistema web automatizado criado para facilitar o gerenciamento da "Carreira Realista" nos jogos **American Truck Simulator** e **Euro Truck Simulator 2**, baseada nas regras de Roleplay desenvolvidas pelo canal Tio Restanho. 

Abandone o caderno e a calculadora! O Diário de Bordo automatiza todos os cálculos de frete, comissões, manutenção, despesas com alimentação e avarias, permitindo que você foque 100% na estrada.

## 🚀 Funcionalidades Atuais

*   **Lançamento de Fretes:** Calcula automaticamente sua comissão com base na fase da campanha e deduz avarias.
*   **Linha do Tempo (Log de Eventos):** Registre refeições, pedágios, manutenções e abastecimentos com cálculo automático de dedução de saldo de acordo com a sua progressão (Empregado, Agregado, Autônomo, etc.).
*   **Controle de Jornada:** Encerre o dia e deixe o sistema gerenciar o pagamento de salários fixos a cada 30 dias trabalhados (ciclos).
*   **Gerenciamento de Perfil:** Ajuste sua base, empresa, fase atual (1 a 4) e moeda de preferência ($, €, R$).

## 🛠️ Tecnologias Utilizadas

*   **Backend:** Python 3, Flask
*   **Banco de Dados:** SQLite (via SQLAlchemy)
*   **Frontend:** HTML5, CSS3 (Custom Properties / Dark Theme) e Vanilla JavaScript (AJAX)

## 📁 Estrutura do Projeto

```text
/diario_bordo
│── app.py                  # Lógica principal do servidor Flask
│── README.md               # Documentação do projeto
├── /static                 # Arquivos estáticos
│   └── /css
│       └── style.css       # Estilização do painel (Tema Industrial)
└── /templates              # Telas (Jinja2)
    ├── base.html           # Esqueleto principal da aplicação
    ├── dashboard.html      # Painel de controle financeiro
    └── opcoes.html         # Configurações do perfil


Como executar o projeto localmente
    Clone ou baixe este repositório para o seu computador.

Crie e ative um Ambiente Virtual (Venv) na pasta do projeto:
    Bash
    python -m venv venv
    # No Windows:
        venv\Scripts\activate
    # No Linux/Mac:
        source venv/bin/activate

Instale as dependências necessárias (Flask e SQLAlchemy):
    Bash
    pip install flask flask-sqlalchemy python-dotenv

Execute a aplicação:
    Bash
    python app.py

Abra o navegador e acesse: http://127.0.0.1:5000