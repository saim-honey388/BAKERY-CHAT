# BAKERY-CHAT: Complete Workflow Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture & Components](#architecture--components)
3. [Complete Request Flow](#complete-request-flow)
4. [Database Schema & Models](#database-schema--models)
5. [Agent System](#agent-system)
6. [Order Processing Workflow](#order-processing-workflow)
7. [RAG Pipeline](#rag-pipeline)
8. [Session Management](#session-management)
9. [Database Migration & Schema Fix](#database-migration--schema-fix)
10. [Testing & Validation](#testing--validation)
11. [Setup & Deployment](#setup--deployment)
12. [Troubleshooting](#troubleshooting)

---

## Project Overview

BAKERY-CHAT is a production-grade conversational AI system for Sunrise Bakery that uses a modular, agent-based, retrieval-augmented generation (RAG) pipeline. The system handles customer inquiries, product information, and complete order processing through natural language interactions.

### Key Features
- **Multi-Agent Architecture**: Specialized agents for different intents (orders, products, general info, meta)
- **RAG Pipeline**: Hybrid retrieval using FAISS (dense) + Whoosh (sparse) with cross-encoder reranking
- **Order Management**: Complete cart-based ordering system with validation and persistence
- **Session Management**: Redis-backed session handling with in-memory fallback
- **Database Integration**: SQLAlchemy with SQLite for product catalog and order management

---

## Architecture & Components

```
BAKERY-CHAT/
├── backend/
│   ├── agents/              # Modular intent agents
│   │   ├── base_agent.py    # Abstract base class
│   │   ├── order_agent.py   # Order processing & cart management
│   │   ├── product_info_agent.py  # Menu lookups & recommendations
│   │   ├── general_info_agent.py  # FAQs, hours, locations
│   │   └── meta_agent.py    # System/meta queries
│   ├── app/                 # Core application logic
│   │   ├── main.py          # FastAPI app & endpoints
│   │   ├── controller.py    # Request orchestration & routing
│   │   ├── session.py       # Session/context management
│   │   ├── preprocess.py    # Text normalization & preprocessing
│   │   ├── embed.py         # Embedding generation
│   │   ├── retrieval.py     # Hybrid retrieval system
│   │   ├── rerank.py        # Cross-encoder reranking
│   │   ├── prompt_builder.py # LLM prompt construction
│   │   ├── generate.py      # LLM client (Groq API)
│   │   └── postprocess.py   # Response formatting & citations
│   ├── data/                # Data models & management
│   │   ├── database.py      # SQLAlchemy setup
│   │   ├── models.py        # Database models
│   │   ├── populate_db.py   # Database population
│   │   ├── menu_store.py    # Menu search & fuzzy matching
│   │   ├── raw/             # Source data files
│   │   └── processed/       # Precomputed indices
│   ├── nlu/                 # Natural Language Understanding
│   │   ├── intent_model.py  # Rule-based intent classification
│   │   ├── entity_extractor.py # Entity extraction
│   │   ├── llm_router.py    # LLM-based fallback routing
│   │   └── rules.py         # Rule-based routing utilities
│   ├── schemas/             # Pydantic models
│   │   ├── io_models.py     # API & agent contracts
│   │   └── order_models.py  # Order-specific models
│   └── utils/               # Utilities
│       ├── logger.py        # Logging setup
│       ├── analytics.py     # Event tracking
│       └── security.py      # PII masking
├── frontend/                # React frontend
├── migrations/              # Alembic database migrations
└── test files & documentation
```

---

## Complete Request Flow

### 1. Request Reception
```
User Query → FastAPI (/query endpoint) → Controller.handle_query()
```

### 2. Session Management
```python
# session.py
session_manager.add_message(session_id, "user", query)
conversation_context = session_manager.get_conversation_context(session_id)
```

### 3. Preprocessing & NLU
```python
# preprocess.py - Text normalization, spell correction
normalized_query = preprocess.normalize(query)

# nlu/intent_model.py - Intent detection
intents = rule_based_intents(query)
if not intents:
    intents = llm_route(query)  # LLM fallback

# nlu/entity_extractor.py - Entity extraction
entities = entity_extractor.extract(query)
```

### 4. Agent Routing & Context Bias
```python
# controller.py - Smart routing with order context bias
if cart_state.get("awaiting_fulfillment") or cart_state.get("awaiting_details"):
    intents = ["order"] + [i for i in intents if i != "order"]

# Route to appropriate agent(s)
for intent in intents:
    agent = AGENT_MAP.get(intent)
    result = agent.handle(session_id, query, session_context)
```

### 5. Agent Processing
Each agent processes the request based on its specialization:

#### Order Agent Flow
```python
# agents/order_agent.py
1. Cart Management (per-session shopping cart)
2. Entity Integration (name, phone, address, time, payment)
3. Product Lookup & Stock Validation
4. Fulfillment Type Handling (pickup/delivery)
5. Missing Details Collection
6. Order Confirmation & Finalization
7. Database Persistence & Receipt Generation
```

#### Product Info Agent Flow
```python
# agents/product_info_agent.py
1. Database Query Construction
2. Category & Price Filtering
3. Fuzzy Matching & Search
4. Result Formatting with Stock Status
```

### 6. RAG Pipeline (for General Info)
```python
# retrieval.py - Hybrid retrieval
dense_results = faiss_search(query_embedding)
sparse_results = whoosh_search(query)
combined_results = merge_results(dense_results, sparse_results)

# rerank.py - Cross-encoder reranking
reranked_docs = cross_encoder.rerank(query, combined_results)

# prompt_builder.py - Context assembly
prompt = build_prompt(query, reranked_docs, conversation_history, agent_facts)

# generate.py - LLM generation
response = groq_llm.generate(prompt)

# postprocess.py - Response formatting
final_response = format_response(response, citations)
```

### 7. Response Assembly & Session Update
```python
# controller.py
session_manager.add_message(session_id, "assistant", final_response)
return {"response": final_response, "citations": citations, "intents": intents}
```

---

## Database Schema & Models

### Core Models

#### Product Model
```python
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    category = Column(String)
    quantity_in_stock = Column(Integer, nullable=False, default=0)
```

#### Customer Model
```python
class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=True)
```

#### Order Model
```python
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    order_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.pending)
    pickup_or_delivery = Column(Enum(FulfillmentType), nullable=False)
    total_amount = Column(Float, nullable=True)  # Calculated from OrderItems
```

#### OrderItem Model
```python
class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_time_of_order = Column(Float, nullable=False)
```

### Database Relationships
```
Customer (1) ←→ (N) Order (1) ←→ (N) OrderItem (N) ←→ (1) Product
```

---

## Agent System

### Base Agent Interface
```python
class BaseAgent(ABC):
    name: str = "base"
    
    @abstractmethod
    def handle(self, session_id: str, query: str, session: List[Dict[str, Any]]) -> AgentResult:
        """Return structured facts; no tone or final prose here."""
        pass
```

### Agent Specializations

#### 1. Order Agent (`order_agent.py`)
**Responsibilities:**
- Shopping cart management (per-session)
- Multi-item parsing and quantity handling
- Stock validation and inventory updates
- Customer information collection
- Fulfillment type handling (pickup/delivery)
- Business hours validation
- Order confirmation and finalization
- Receipt generation and storage

**Key Features:**
```python
class ShoppingCart:
    def __init__(self):
        self.items = []  # List of {'product': Product, 'quantity': int}
        self.customer_info = {}
        self.delivery_info = {}
        self.pickup_info = {}
        self.fulfillment_type = None
        self.payment_method = None
        self.awaiting_fulfillment = False
        self.awaiting_details = False
        self.awaiting_confirmation = False
```

**Order Processing States:**
1. **Item Addition**: Parse products, validate stock, add to cart
2. **Fulfillment Selection**: Pickup vs delivery choice
3. **Details Collection**: Name, phone, address/time, payment method
4. **Confirmation**: Show receipt preview, await confirmation
5. **Finalization**: Create order, update inventory, generate receipt

#### 2. Product Info Agent (`product_info_agent.py`)
**Responsibilities:**
- Menu item lookups and searches
- Category-based filtering
- Price range filtering
- Stock status reporting
- Product recommendations

**Query Processing:**
```python
# Database query construction
db_query = db.query(Product)

# Category heuristics
if category_terms:
    db_query = db_query.filter(Product.category.ilike(f"%{category}%"))

# Text search
db_query = db_query.filter(
    or_(Product.name.ilike(search_term), Product.description.ilike(search_term))
)

# Price filtering
if price_min: db_query = db_query.filter(Product.price >= price_min)
if price_max: db_query = db_query.filter(Product.price <= price_max)
```

#### 3. General Info Agent (`general_info_agent.py`)
**Responsibilities:**
- FAQ responses
- Store hours and locations
- Delivery information
- General bakery information

**Uses RAG pipeline for complex queries**

#### 4. Meta Agent (`meta_agent.py`)
**Responsibilities:**
- System information queries
- "Who are you?" type questions
- Meta-conversational handling

---

## Order Processing Workflow

### Detailed Order Flow

#### Phase 1: Item Addition
```
User: "I want 2 chocolate cakes and 1 cheesecake"
↓
1. Multi-item parsing: Extract products and quantities
2. Database lookup: Find matching products
3. Stock validation: Check availability
4. Cart update: Add items to session cart
5. Upsell suggestions: Recommend complementary items
```

#### Phase 2: Fulfillment Selection
```
System: "Would you like delivery or pickup?"
User: "Pickup"
↓
1. Set fulfillment_type = 'pickup'
2. Set awaiting_details = True
3. Determine required details based on fulfillment type
```

#### Phase 3: Details Collection
```
Sequential collection of missing details:
1. Name: "What's the name for the order?"
2. Branch: "Which branch? (Downtown, Westside, Mall)"
3. Phone (pickup): "What's the best phone number?"
4. Pickup time: "What pickup time works? (8 AM–6 PM)"
5. Payment method: "How would you like to pay? (cash, card, UPI)"
```

#### Phase 4: Confirmation
```
System: Shows receipt preview with all details
User: "Yes, confirm" / "Place the order"
↓
1. Strong confirmation detection
2. Final stock validation
3. Order creation in database
4. Inventory updates
5. Receipt generation
6. Cart clearing
```

#### Phase 5: Database Persistence
```python
# Create customer record
customer = find_or_create_customer(db, session_id, name, phone)

# Create order record
order = Order(
    customer_id=customer.id,
    status=OrderStatus.pending,
    pickup_or_delivery=fulfillment_type,
    total_amount=cart.get_total()
)

# Create order items
for item in cart.items:
    order_item = OrderItem(
        order_id=order.id,
        product_id=item['product'].id,
        quantity=item['quantity'],
        price_at_time_of_order=item['product'].price
    )
    # Update inventory
    item['product'].quantity_in_stock -= item['quantity']
```

### Business Logic Validations

#### Stock Validation
```python
for item in cart.items:
    if product.quantity_in_stock < item['quantity']:
        return insufficient_stock_response(product, alternatives)
```

#### Business Hours Validation
```python
def _is_time_within_business_hours(iso_timestamp: str, branch_name: str) -> bool:
    dt = datetime.fromisoformat(iso_timestamp)
    open_time, close_time = get_branch_hours(branch_name, dt)
    return open_time <= dt.time() <= close_time
```

#### Confirmation Logic
```python
def _is_strong_confirmation(query: str) -> bool:
    strong_confirmations = [
        "yes", "confirm", "place order", "place the order",
        "that's correct", "sounds good", "proceed", "finalize"
    ]
    negation_words = ["not", "wait", "change", "no", "cancel"]
    
    if any(word in query.lower() for word in negation_words):
        return False
    return any(phrase in query.lower() for phrase in strong_confirmations)
```

---

## RAG Pipeline

### 1. Data Ingestion & Indexing
```python
# scripts/ingest_data.py
raw_data = load_raw_files()  # FAQ, locations, general info
chunks = chunk_documents(raw_data)
embeddings = generate_embeddings(chunks)

# Create indices
faiss_index = build_faiss_index(embeddings)  # Dense retrieval
whoosh_index = build_whoosh_index(chunks)   # Sparse retrieval
```

### 2. Hybrid Retrieval
```python
# retrieval.py
def hybrid_search(query: str, k: int = 10):
    # Dense retrieval
    query_embedding = embed_model.encode(query)
    dense_results = faiss_index.search(query_embedding, k)
    
    # Sparse retrieval
    sparse_results = whoosh_index.search(query, k)
    
    # Merge and deduplicate
    combined_results = merge_results(dense_results, sparse_results)
    return combined_results
```

### 3. Cross-Encoder Reranking
```python
# rerank.py
def rerank_documents(query: str, documents: List[Document]) -> List[Document]:
    pairs = [(query, doc.content) for doc in documents]
    scores = cross_encoder.predict(pairs)
    
    # Sort by relevance score
    ranked_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, score in ranked_docs]
```

### 4. Prompt Construction
```python
# prompt_builder.py
def build_prompt(query: str, context_docs: List[Document], 
                conversation_history: str, agent_facts: Dict) -> str:
    
    context_text = "\n".join([doc.content for doc in context_docs])
    
    prompt = f"""
    You are a friendly assistant at Sunrise Bakery.
    
    Context: {context_text}
    
    Conversation History: {conversation_history}
    
    Agent Facts: {agent_facts}
    
    User Query: {query}
    
    Response:"""
    
    return prompt
```

---

## Session Management

### Session Storage
```python
# session.py
class SessionManager:
    def __init__(self):
        self.redis_client = redis.Redis() if redis_available else None
        self.memory_store = {}  # Fallback
    
    def add_message(self, session_id: str, role: str, message: str):
        session_key = f"session:{session_id}"
        message_data = {
            "role": role,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.redis_client:
            self.redis_client.lpush(session_key, json.dumps(message_data))
            self.redis_client.expire(session_key, 3600)  # 1 hour TTL
        else:
            if session_id not in self.memory_store:
                self.memory_store[session_id] = []
            self.memory_store[session_id].append(message_data)
```

### Context Management
```python
def get_conversation_context(self, session_id: str, limit: int = 10) -> List[Dict]:
    """Get recent conversation history for context."""
    if self.redis_client:
        messages = self.redis_client.lrange(f"session:{session_id}", 0, limit-1)
        return [json.loads(msg) for msg in messages]
    else:
        return self.memory_store.get(session_id, [])[-limit:]
```

---

## Database Migration & Schema Fix

### Problem Identification
The original issue was a schema mismatch:
```
TypeError: 'total_amount' is an invalid keyword argument for Order
```

**Root Cause:**
- `Order` model defined `total_amount` field
- Database table `orders` didn't have this column
- Code tried to create Order with `total_amount=value`

### Migration Solution

#### 1. Alembic Migration Creation
```python
# migrations/versions/xxx_add_total_amount_column.py
def upgrade() -> None:
    # Add column as nullable for existing data
    op.add_column('orders', sa.Column('total_amount', sa.Float(), nullable=True))
    
    # Calculate totals for existing orders
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT o.id, COALESCE(SUM(oi.quantity * oi.price_at_time_of_order), 0) as total
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id
    """))
    
    # Update existing orders
    for order_id, calculated_total in result:
        connection.execute(sa.text("""
            UPDATE orders SET total_amount = :total WHERE id = :order_id
        """), {"total": calculated_total, "order_id": order_id})
```

#### 2. Field Name Correction
```python
# Fixed in order_agent.py
order_item = OrderItem(
    order_id=order.id,
    product_id=product.id,
    quantity=item['quantity'],
    price_at_time_of_order=product.price  # Was: unit_price
)
```

#### 3. Model Alignment
```python
# models.py - Made nullable to match database
total_amount = Column(Float, nullable=True)
```

### Migration Execution
```bash
# Fix database URL in alembic.ini
sqlalchemy.url = sqlite:///./backend/data/bakery.db

# Run custom migration script
python fix_database_schema.py

# Mark migration as applied
alembic stamp head
```

---

## Testing & Validation

### Test Suite Structure

#### 1. Database Schema Test
```python
# test_order_functionality.py
def test_order_creation():
    # Create test cart with items
    # Set all required details
    # Call _finalize_order directly
    # Verify order creation succeeds
    # Check database state
```

#### 2. Integration Test Flow
```
1. Verify existing orders preserved
2. Create new test order
3. Validate total_amount calculation
4. Confirm inventory updates
5. Check receipt generation
6. Verify database integrity
```

#### 3. Test Results Validation
```
✅ Order #5 created successfully with total_amount: $7.58
✅ All existing orders preserved:
   - Order #1: $25.00 (1x Chocolate Fudge Cake)
   - Order #2: $25.00 (1x Chocolate Fudge Cake)  
   - Order #3: $20.00 (1x Cheesecake)
   - Order #4: $0.00 (no items)
✅ Inventory properly updated
✅ Receipt generation working
```

### Continuous Testing Strategy
```python
# Run in virtual environment
.venv\Scripts\activate && python test_order_functionality.py

# Verify specific components
python -m pytest backend/tests/ -v

# Integration testing
python test_endpoints.py
```

---

## Setup & Deployment

### Environment Setup
```bash
# 1. Clone repository
git clone <repository-url>
cd BAKERY-CHAT

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Environment configuration
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Database Setup
```bash
# 1. Initialize database
python backend/data/database.py

# 2. Populate with sample data
python backend/data/populate_db.py

# 3. Run migrations (if needed)
alembic upgrade head

# 4. Verify setup
python test_order_functionality.py
```

### Data Ingestion
```bash
# Process raw data and build indices
python backend/scripts/ingest_data.py

# Verify indices created
ls backend/data/processed/
# Should see: chunks.json, faiss_index.bin, whoosh_index/
```

### Application Startup
```bash
# Start backend server
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend (separate terminal)
cd frontend
npm install
npm start
```

### Production Deployment
```bash
# Use production WSGI server
gunicorn backend.app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# Or with Docker
docker build -t bakery-chat .
docker run -p 8000:8000 bakery-chat
```

---

## Troubleshooting

### Common Issues & Solutions

#### 1. Database Schema Mismatch
**Error:** `'total_amount' is an invalid keyword argument for Order`
**Solution:**
```bash
python fix_database_schema.py
alembic stamp head
```

#### 2. Missing Dependencies
**Error:** `ModuleNotFoundError: No module named 'pydantic'`
**Solution:**
```bash
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

#### 3. Database Connection Issues
**Error:** `unable to open database file`
**Solution:**
- Check database path in `alembic.ini`
- Ensure `backend/data/bakery.db` exists
- Run `python backend/data/database.py` to create tables

#### 4. Index Files Missing
**Error:** `FileNotFoundError: faiss_index.bin not found`
**Solution:**
```bash
python backend/scripts/ingest_data.py
```

#### 5. API Key Issues
**Error:** `Groq API authentication failed`
**Solution:**
- Check `.env` file has correct `GROQ_API_KEY`
- Verify API key is valid and has credits

#### 6. Session Management Issues
**Error:** Redis connection failed
**Solution:**
- System falls back to in-memory storage automatically
- For production, ensure Redis is running: `redis-server`

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check database state
python -c "
from backend.data.database import SessionLocal
from backend.data.models import Order
db = SessionLocal()
orders = db.query(Order).all()
for o in orders:
    print(f'Order {o.id}: total_amount={o.total_amount}')
"
```

### Performance Monitoring
```python
# Check response times
import time
start = time.time()
# ... make request ...
print(f"Response time: {time.time() - start:.2f}s")

# Monitor database queries
# Enable SQLAlchemy logging in database.py
engine = create_engine(DATABASE_URL, echo=True)
```

---

## API Endpoints

### Main Chat Endpoint
```
POST /query
Content-Type: application/json

{
    "session_id": "unique-session-id",
    "query": "I want to order 2 chocolate cakes for pickup",
    "skip_llm": false  // Optional: return raw agent facts
}

Response:
{
    "response": "I've added 2 chocolate cakes to your cart...",
    "citations": [
        {"source": "menu.csv", "snippet": "Chocolate Fudge Cake - $25.00"}
    ],
    "intents": ["order"]
}
```

### Health Check
```
GET /health

Response:
{
    "status": "healthy",
    "database": "connected",
    "indices": "loaded"
}
```

---

## Configuration

### Environment Variables (.env)
```bash
# LLM Configuration
GROQ_API_KEY=your_groq_api_key_here
MODEL_NAME=llama3-8b-8192

# Database
DATABASE_URL=sqlite:///./backend/data/bakery.db

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
```

### Model Configuration (backend/app/config.py)
```python
class Config:
    # LLM Settings
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama3-8b-8192")
    MAX_TOKENS = 1000
    TEMPERATURE = 0.7
    
    # Retrieval Settings
    RETRIEVAL_K = 10
    RERANK_TOP_K = 5
    
    # Session Settings
    SESSION_TTL = 3600  # 1 hour
    MAX_CONVERSATION_LENGTH = 20
```

---

This comprehensive documentation covers the complete workflow of the BAKERY-CHAT system, from initial request processing through order finalization and database persistence. The system demonstrates a production-ready architecture with proper error handling, session management, and data persistence.