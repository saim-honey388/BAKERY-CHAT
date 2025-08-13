# BAKERY-CHAT

A Retrieval-Augmented Generation (RAG) based chatbot for bakery information, featuring a FastAPI backend and a React frontend.

---

## Features

- Conversational chatbot for bakery-related queries
- RAG pipeline: retrieval, reranking, prompt building, LLM generation, postprocessing
- Session management
- REST API (FastAPI)
- React frontend

---

## Project Structure

```
backend/    # FastAPI backend
frontend/   # React frontend
.env.example
.gitignore
README.md
```

---

## Setup Instructions

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
cp ../.env.example .env  # Create your own .env file from the example
```

> **Note:**  
> The `.env` file is **not** included in the repo for security reasons.  
> You must create your own `.env` file and add your API keys and secrets as needed.  
> See `.env.example` for the required variables.

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

## Environment Variables

- Copy `.env.example` to `.env`
- Fill in all required values (API keys, secrets, etc.)

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Commit your changes
4. Open a pull request

---

## License

MIT License

---

## Author

[saim-honey388](https://github.com/saim-honey388)
