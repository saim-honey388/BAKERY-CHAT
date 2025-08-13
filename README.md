# 🥐 BAKERY-CHAT

**BAKERY-CHAT** is an intelligent, Retrieval-Augmented Generation (RAG) based chatbot designed to answer bakery-related queries. It features a robust FastAPI backend and a modern React frontend, providing a seamless conversational experience for users seeking bakery information.

---

## 🚀 Features

- **Conversational Chatbot:** Natural language interaction for bakery FAQs, menu, locations, and more.
- **RAG Pipeline:** Combines document retrieval, reranking, prompt engineering, LLM-based generation, and postprocessing for accurate answers.
- **Session Management:** Maintains user context for multi-turn conversations.
- **RESTful API:** Built with FastAPI for high performance and easy integration.
- **Modern Frontend:** Responsive React interface for engaging user experience.

---

## 🛠️ Tech Stack

| Layer      | Technology / Tool         | Purpose                                      |
|------------|--------------------------|----------------------------------------------|
| Backend    | [FastAPI](https://fastapi.tiangolo.com/) | High-performance Python API framework        |
|            | [Pydantic](https://pydantic-docs.helpmanual.io/) | Data validation and settings management      |
|            | [Uvicorn](https://www.uvicorn.org/) | ASGI server for FastAPI                     |
|            | [Whoosh](https://whoosh.readthedocs.io/) | Full-text search indexing                   |
|            | [FAISS](https://github.com/facebookresearch/faiss) | Vector similarity search                    |
|            | [Python-dotenv](https://pypi.org/project/python-dotenv/) | Environment variable management             |
|            | [Groq API](https://groq.com/) | LLM-powered text generation                 |
| Frontend   | [React](https://react.dev/) | Modern JavaScript UI library                |
|            | [npm](https://www.npmjs.com/) | Package management                          |
| DevOps     | [Git](https://git-scm.com/) | Version control                             |
|            | [GitHub](https://github.com/) | Code hosting and collaboration              |

---

## 📁 Project Structure

```
backend/    # FastAPI backend (API, RAG pipeline, data, scripts)
frontend/   # React frontend (UI)
.env.example
.gitignore
README.md
```

---

## ⚡ Getting Started

### 1. Clone the Repository

```sh
git clone https://github.com/saim-honey388/BAKERY-CHAT.git
cd BAKERY-CHAT
```

### 2. Backend Setup

```sh
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # Fill in your API keys and secrets
```

> **Note:**  
> The `.env` file is **not** included in the repo for security.  
> You must create your own `.env` file and add your API keys and secrets as needed.  
> See `.env.example` for required variables.

#### Run the backend:

```sh
uvicorn app.main:app --reload
```

### 3. Frontend Setup

```sh
cd ../frontend
npm install
npm start
```

---

## 🔑 Environment Variables

- Copy `.env.example` to `.env`
- Fill in all required values (API keys, secrets, etc.)

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Commit your changes
4. Open a pull request

---

## 📄 License

MIT License

---

## 👤 Author

**[saim-honey388](https://github.com/saim-honey388)**

---

> _Built with 🍫 for the bakery community!_
