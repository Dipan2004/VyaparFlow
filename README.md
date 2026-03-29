# 🚀 VyaparFlow

An **autonomous multi-agent business workflow system** that transforms simple WhatsApp-style messages into complete business operations — in real time.

---

## ❗ Problem Statement

Small and medium businesses heavily rely on **informal communication platforms like WhatsApp** to manage daily operations such as orders, billing, and payments.

However, this leads to several critical challenges:

### 🔴 1. Manual Order Processing

* Orders are received as unstructured text (e.g., *"bhaiya 10 kurti bhej do"*)
* Staff must manually interpret, note, and process each request
* High dependency on human attention and accuracy

---

### 🔴 2. Fragmented Workflow

* Order taking, invoice generation, and payment tracking happen separately
* No unified system → leads to confusion and inefficiency
* No real-time visibility of business operations

---

### 🔴 3. Time-Consuming Operations

* Each order takes **3–5 minutes** to process manually
* At scale (100+ orders/day), this consumes **6–8 hours daily**

---

### 🔴 4. High Error Rate

* Mistakes in quantity, pricing, or customer details
* Missed entries and incorrect billing
* Leads to financial loss and customer dissatisfaction

---

### 🔴 5. Missed Revenue Opportunities

* Delayed responses → lost customers
* Forgotten follow-ups → missed payments
* No tracking → lost orders

---

### 🔴 6. Labour Dependency

* Requires dedicated staff for:

  * Order handling
  * Billing
  * Payment tracking
* Increases operational costs significantly

---

### 🔴 7. No Intelligence or Automation

* Traditional systems do not:

  * Understand intent
  * Extract structured data
  * Make decisions
  * Recover from errors

---

## 💡 Solution: VyaparFlow

VyaparFlow solves these problems by introducing a **fully autonomous, multi-agent system** that:

* Understands natural language messages
* Extracts structured business data
* Executes workflows automatically
* Generates invoices instantly
* Handles payment requests
* Maintains real-time logs and dashboards
* Recovers intelligently from failures

---

## 🧠 Overview

VyaparFlow automates core business tasks for small and medium enterprises:

* 📦 Order processing
* 🧾 Invoice generation
* 💳 Payment requests
* 📊 Ledger & dashboard updates

---

## ⚡ Key Features

* 📩 WhatsApp-style message processing
* 🤖 Multi-agent architecture (Intent → Extraction → Validation → Execution)
* 🧾 Structured invoice generation (Item, Qty, Price, Total)
* 💳 Integrated payment request flow
* 📊 Business dashboard (orders + payment ledger)
* 📡 Real-time system logs & pipeline visualization
* 🔁 Intelligent fallback (NVIDIA NIM → OpenRouter)
* 📱 Live notification system (critical alerts only)

---

## 🏗️ System Architecture

```text
User Message
     ↓
Orchestrator
     ↓
IntentAgent → ExtractionAgent → ValidationAgent
     ↓
SkillRouter → InvoiceAgent → PaymentAgent → LedgerAgent
     ↓
Autonomy Layer (Verification, Monitor, Prediction, Urgency)
     ↓
Event Bus (WebSocket)
     ↓
Frontend (WhatsApp UI + Dashboard + Notifications)
```

---

## 🔄 Workflow

1. User sends message (e.g., *"bhaiya 10 kurti bhej do"*)
2. Intent is detected automatically
3. Data is extracted & validated
4. Invoice is generated with structured details
5. Payment request is sent
6. Ledger is updated
7. Dashboard & logs update in real time

---

## 🧪 Tech Stack

### Backend

* FastAPI
* WebSocket (real-time events)
* Multi-agent system

### AI / LLM

* NVIDIA NIM (primary)
* OpenRouter (fallback)

### Frontend

* React + TypeScript
* Real-time UI rendering
* Notification system

---

## ⚙️ Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/your-username/vyaparflow.git
cd vyaparflow
```

### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## 📊 Impact

* ⏱️ ~6 hours/day saved
* 💰 ₹10,000+ monthly cost reduction
* 👨‍💼 Up to ₹15,000 labour savings
* 📈 ₹75,000 revenue recovery/month



---

## 👨‍💻 Team

* Dipan Giri
* Archi Kanungo

---

## 🏁 Conclusion

VyaparFlow transforms unstructured business communication into **fully autonomous workflows**, enabling businesses to operate efficiently with minimal manual effort.

> From message → to money — automatically.
