# Vernon AI Chatbot

An AI-powered customer service chatbot for the City of Vernon, built to help residents find information from [vernon.ca](https://vernon.ca) quickly and accurately. The chatbot crawls the City's website, ingests the content into a searchable knowledge base, and uses Claude (Anthropic's AI) to answer questions grounded in real City content — with source citations, confidence scoring, and automatic handoff to staff when needed.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Security and Privacy](#security-and-privacy)
- [System Requirements](#system-requirements)
- [Quick Start (Local Development)](#quick-start-local-development)
- [Environment Variables Reference](#environment-variables-reference)
- [Deployment](#deployment)
  - [Backend on Railway](#backend-on-railway)
  - [Frontend on Vercel](#frontend-on-vercel)
  - [Post-Deployment Checklist](#post-deployment-checklist)
- [Admin Dashboard Guide](#admin-dashboard-guide)
- [Council Meeting Transcription](#council-meeting-transcription)
- [Embeddable Chat Widget](#embeddable-chat-widget)
- [API Reference](#api-reference)
- [Maintenance and Operations](#maintenance-and-operations)

---

## Features

### Core Chat
- **AI-Powered Q&A** — Answers grounded exclusively in City of Vernon website content via RAG (Retrieval-Augmented Generation)
- **Real-Time Streaming** — Responses appear token-by-token via Server-Sent Events (SSE)
- **Source Citations** — Every answer includes clickable links to the source pages on vernon.ca
- **Bilingual Support** — English and French language toggle; responses generated in the selected language
- **Suggested Questions** — Pre-built quick-action chips (e.g., "Pay property taxes", "Recreation programs")
- **Conversation History** — Full session persistence with message replay on page refresh

### Knowledge Base
- **Website Crawler** — Crawls vernon.ca using sitemap + link following (configurable depth, concurrency, delay)
- **Incremental Updates** — Detects new, changed, and removed pages; only re-indexes what changed
- **News Release Ingestion** — Crawls 360+ news articles from the vernon.ca sitemap
- **PDF Ingestion** — Automatically extracts and indexes PDFs found during crawl, plus manual PDF upload via admin
- **Council Meeting Transcription** — Discovers meetings from the eScribe portal, downloads video audio, transcribes with Whisper, generates AI summaries and action items, and indexes transcriptions for search

### Intelligence
- **Confidence Scoring** — Blended score (60% LLM self-assessment + 40% retrieval distance) on every response
- **Human Handoff** — When confidence is low or the AI cannot answer, displays staff contact info with an optional AI-generated conversation summary
- **Topic Routing** — Keyword-based classification into departments (Water & Utilities, Building & Permits, Recreation & Parks, Taxes & Finance, Roads & Transportation, Waste & Recycling, Council & Governance) with topic-specific prompts
- **Response Caching** — Identical questions served from cache (configurable TTL) to reduce API costs

### Admin Dashboard
- **Analytics Overview** — Total conversations, messages, average confidence, response times
- **Top Questions** — Most frequently asked questions ranked by count
- **Unanswered Questions** — Questions where confidence fell below threshold
- **Hourly Traffic Chart** — Message volume distribution by hour of day
- **Topic Distribution** — Pie chart of questions by department topic
- **Conversation Browser** — Browse and inspect full conversation transcripts with feedback
- **Crawl Management** — View knowledge base stats, trigger full or incremental recrawls
- **Document Upload** — Upload PDFs directly to the knowledge base
- **Council Meeting Manager** — Discover, process, and review meeting transcriptions and summaries
- **Audit Log** — Timestamped record of all system actions (queries, crawls, uploads, discoveries)

### Security and Ops
- **Rate Limiting** — Configurable per-endpoint rate limits (general API + chat)
- **Input Sanitization** — HTML stripping, length enforcement, and prompt injection protection
- **Admin Authentication** — API key-based auth for all admin endpoints
- **Data Retention** — Automatic daily purge of conversations older than configurable threshold (default 90 days)
- **Scheduled Recrawl** — Optional cron-based automatic recrawl (APScheduler)
- **Embeddable Widget** — Drop-in `<script>` tag to embed the chatbot on any page

---

## Architecture

```
┌─────────────────────────────┐       ┌──────────────────────────────────┐
│     Frontend (Vercel)       │       │       Backend (Railway)           │
│                             │       │                                  │
│  Next.js 14 + React 18     │◄─────►│  FastAPI + Uvicorn               │
│  Tailwind CSS               │ HTTPS │                                  │
│  Recharts (admin charts)    │       │  ┌──────────┐  ┌──────────────┐ │
│  react-markdown             │       │  │ Claude AI │  │ ChromaDB     │ │
│                             │       │  │ (Anthropic│  │ (Vector      │ │
│  /           → Chat UI      │       │  │  API)     │  │  Store)      │ │
│  /admin      → Dashboard    │       │  └──────────┘  └──────────────┘ │
│  /embed      → Widget view  │       │                                  │
│                             │       │  ┌──────────┐  ┌──────────────┐ │
└─────────────────────────────┘       │  │ SQLite   │  │ Whisper      │ │
                                      │  │ (Sessions,│  │ (faster-     │ │
                                      │  │  Analytics│  │  whisper,    │ │
                                      │  │  Meetings)│  │  CPU int8)   │ │
                                      │  └──────────┘  └──────────────┘ │
                                      │                                  │
                                      │  ┌──────────┐  ┌──────────────┐ │
                                      │  │ Web      │  │ eScribe      │ │
                                      │  │ Scraper  │  │ Scraper      │ │
                                      │  │ (BS4)    │  │ (Meetings)   │ │
                                      │  └──────────┘  └──────────────┘ │
                                      └──────────────────────────────────┘
```

**Data Flow:**
1. The web scraper crawls vernon.ca, chunks the content, and stores embeddings in ChromaDB
2. When a user asks a question, the backend retrieves the most relevant chunks from ChromaDB
3. The chunks are sent as context to Claude, which generates a grounded answer
4. The response streams back to the frontend with source citations and confidence score
5. All interactions are logged to SQLite for analytics, audit, and conversation history

---

## Security and Privacy

- **No PII Storage** — The chatbot does not collect or store personally identifiable information. Conversations are stored with anonymous session IDs only.
- **Configurable Data Retention** — Conversations are automatically purged after a configurable period (default: 90 days). A daily job runs at 3:00 AM to enforce this.
- **Admin Authentication** — All admin and analytics endpoints require an `X-Admin-Key` header. The key is set via the `ADMIN_API_KEY` environment variable.
- **Rate Limiting** — Per-IP rate limits on all endpoints prevent abuse (default: 30 req/min general, 10 req/min chat).
- **Input Sanitization** — User messages are stripped of HTML, truncated to a maximum length, and checked for prompt injection patterns before processing.
- **CORS Protection** — Only explicitly whitelisted origins can access the API.
- **Audit Logging** — Every chat query, crawl, document upload, and meeting discovery is logged with timestamps, confidence scores, and retrieved context for accountability.
- **No Outbound Data Sharing** — The only external API call is to Anthropic (Claude) for answer generation. No user data is sent to any other third party.

---

## System Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.12 or higher |
| Node.js | 20 or higher |
| ffmpeg | Required for council meeting audio extraction |
| RAM | 4 GB minimum (Whisper small model + sentence-transformers embedding model) |
| Disk | ~2 GB for models + crawl data (grows with content) |
| Anthropic API Key | Required — sign up at [console.anthropic.com](https://console.anthropic.com) |

> **Note:** ffmpeg is only required if you plan to use the council meeting transcription feature. It is included automatically in the Docker image.

---

## Quick Start (Local Development)

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/vernon-chatbot.git
cd vernon-chatbot
```

### 2. Start the Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
# Set ADMIN_API_KEY to a secure random string

uvicorn app.main:app --reload
```

The backend starts at **http://localhost:8000**. Verify by visiting http://localhost:8000/api/health.

### 3. Start the Frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend starts at **http://localhost:3000**.

### 4. Crawl the Website

Trigger the initial crawl to build the knowledge base:

```bash
curl -X POST http://localhost:8000/api/ingest
```

This crawls vernon.ca (approximately 1,600 pages including news releases), chunks the content, and stores it in ChromaDB. The first crawl takes several minutes depending on your connection speed.

### 5. Start Chatting

Open **http://localhost:3000** in your browser and ask a question about the City of Vernon.

### 6. Access the Admin Dashboard

Open **http://localhost:3000/admin** and enter your `ADMIN_API_KEY` when prompted.

---

## Environment Variables Reference

All backend configuration is managed through environment variables (or a `.env` file). Copy `.env.example` to `.env` and customize.

### Required

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key for Claude | *(none — required)* |
| `ADMIN_API_KEY` | Secret key for admin dashboard access | *(none — required for admin)* |

### Website Crawling

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_URL` | The website to crawl | `https://vernon.ca` |
| `MAX_CRAWL_PAGES` | Maximum number of pages to crawl | `2000` |
| `MAX_CRAWL_DEPTH` | Maximum link-following depth | `10` |
| `CRAWL_DELAY` | Delay between requests in seconds | `0.3` |
| `CRAWL_CONCURRENCY` | Number of concurrent crawl threads | `10` |
| `CRAWL_TIMEOUT` | Per-page request timeout in seconds | `15` |
| `USE_SITEMAP` | Parse sitemap.xml for URL discovery | `true` |
| `INCLUDE_NEWS_ARCHIVE` | Include news release articles in crawl | `true` |
| `INGEST_PDFS` | Auto-extract PDFs found during crawl | `true` |

### AI and Embeddings

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_MODEL` | Sentence-transformers model for embeddings | `all-MiniLM-L6-v2` |
| `CLAUDE_MODEL` | Claude model ID for answer generation | `claude-sonnet-4-5-20250929` |
| `TOP_K_RESULTS` | Number of chunks retrieved per query | `5` |
| `CONFIDENCE_THRESHOLD` | Below this score, handoff is triggered | `0.65` |

### Database and Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./vernon_chatbot.db` |
| `CHROMA_PATH` | Directory for ChromaDB vector store | `./chroma_data` |

### Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `RATE_LIMIT` | General API rate limit | `30/minute` |
| `RATE_LIMIT_CHAT` | Chat endpoint rate limit | `10/minute` |

### Privacy and Retention

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_RETENTION_DAYS` | Days before conversations are purged | `90` |
| `MAX_MESSAGE_LENGTH` | Maximum user message length (characters) | `2000` |

### Bilingual

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_LANGUAGE` | Default language (`en` or `fr`) | `en` |

### Caching

| Variable | Description | Default |
|----------|-------------|---------|
| `CACHE_TTL_SECONDS` | Response cache time-to-live | `3600` |
| `CACHE_MAX_SIZE` | Maximum cached responses | `500` |

### Scheduled Recrawl

| Variable | Description | Default |
|----------|-------------|---------|
| `RECRAWL_ENABLED` | Enable automatic scheduled recrawl | `false` |
| `RECRAWL_CRON_HOUR` | Hour (0-23) for daily recrawl | `2` |

### Human Handoff

| Variable | Description | Default |
|----------|-------------|---------|
| `HANDOFF_EMAIL` | Staff email shown on handoff | *(empty)* |
| `HANDOFF_PHONE` | Staff phone shown on handoff | *(empty)* |
| `HANDOFF_URL` | Contact page URL shown on handoff | `https://www.vernon.ca/contact-us` |
| `HANDOFF_SUMMARY_ENABLED` | Generate AI conversation summary for staff | `true` |

### Topic Routing

| Variable | Description | Default |
|----------|-------------|---------|
| `TOPIC_ROUTING_ENABLED` | Enable keyword-based topic classification | `true` |

### Council Meeting Transcription

| Variable | Description | Default |
|----------|-------------|---------|
| `COUNCIL_MEETINGS_ENABLED` | Enable council meeting features | `true` |
| `WHISPER_MODEL_SIZE` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`) | `small` |
| `ESCRIBE_PORTAL_URL` | eScribe portal URL for meeting discovery | `https://pub-vernon.escribemeetings.com` |

### Server

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["http://localhost:3000"]` |

### Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL (set in frontend environment) | `http://localhost:8000` |

---

## Deployment

### Backend on Railway

[Railway](https://railway.app) provides container hosting with persistent storage, ideal for the backend's SQLite database and ChromaDB vector store.

#### Step 1: Create a Railway Account

Sign up at [railway.app](https://railway.app) and create a new project.

#### Step 2: Connect Your Repository

1. In your Railway project, click **"New Service"** > **"GitHub Repo"**
2. Select your vernon-chatbot repository
3. Railway will detect the Dockerfile automatically

#### Step 3: Configure the Service

1. Go to **Settings** for the service
2. Set **Root Directory** to `backend`
3. Set **Builder** to "Dockerfile" (should auto-detect)
4. Set **Start Command** to: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

> Railway dynamically assigns a port via the `$PORT` environment variable.

#### Step 4: Add a Persistent Volume

The backend stores data in SQLite and ChromaDB files that must survive redeployments.

1. Go to your service's **Volumes** tab
2. Click **"Add Volume"**
3. Set **Mount Path** to `/app/data`
4. After adding the volume, update your environment variables:
   - `DATABASE_URL` = `sqlite:////app/data/vernon_chatbot.db`
   - `CHROMA_PATH` = `/app/data/chroma_data`

#### Step 5: Set Environment Variables

In your Railway service's **Variables** tab, add all required variables:

```
ANTHROPIC_API_KEY=sk-ant-...your-key...
ADMIN_API_KEY=your-secure-random-string
TARGET_URL=https://vernon.ca
DATABASE_URL=sqlite:////app/data/vernon_chatbot.db
CHROMA_PATH=/app/data/chroma_data
CORS_ORIGINS=["https://your-frontend-domain.vercel.app"]
RECRAWL_ENABLED=true
RECRAWL_CRON_HOUR=2
HANDOFF_EMAIL=info@vernon.ca
HANDOFF_PHONE=250-545-1361
HANDOFF_URL=https://www.vernon.ca/contact-us
WHISPER_MODEL_SIZE=small
```

> Set `CORS_ORIGINS` to your Vercel frontend URL after deploying the frontend.

#### Step 6: Deploy

1. Click **"Deploy"** or push to your connected branch
2. Railway builds the Docker image (first build takes ~5 minutes due to model downloads)
3. Once deployed, Railway provides a public URL (e.g., `https://vernon-chatbot-production.up.railway.app`)

#### Step 7: Verify and Initialize

1. Check the health endpoint: `https://your-railway-url/api/health`
2. Trigger the initial crawl:

```bash
curl -X POST https://your-railway-url/api/ingest
```

3. The crawl runs in the background. Check progress at `/api/status`.

#### Step 8: Custom Domain (Optional)

1. In Railway service **Settings** > **Networking** > **Custom Domain**
2. Add your domain (e.g., `api.vernonchatbot.ca`)
3. Add the CNAME record to your DNS provider as instructed
4. Update `CORS_ORIGINS` to include both Vercel and custom domains

---

### Frontend on Vercel

[Vercel](https://vercel.com) is the ideal host for Next.js applications with automatic builds and global CDN.

#### Step 1: Import to Vercel

1. Sign up at [vercel.com](https://vercel.com) and click **"Import Project"**
2. Select your vernon-chatbot GitHub repository

#### Step 2: Configure Build Settings

1. Set **Root Directory** to `frontend`
2. Framework Preset should auto-detect **Next.js**
3. Build Command: `npm run build` (default)
4. Output Directory: `.next` (default)

#### Step 3: Set Environment Variables

In the Vercel project settings, add:

```
NEXT_PUBLIC_API_URL=https://your-railway-url.up.railway.app
```

> This must point to your Railway backend URL (from Step 6 above).

#### Step 4: Deploy

1. Click **"Deploy"**
2. Vercel builds and deploys in approximately 1 minute
3. Your frontend is live at `https://your-project.vercel.app`

#### Step 5: Custom Domain (Optional)

1. In Vercel **Settings** > **Domains**, add your domain (e.g., `chat.vernon.ca`)
2. Add the DNS records as instructed by Vercel
3. Update the backend's `CORS_ORIGINS` environment variable on Railway to include your custom domain

#### Step 6: Update Backend CORS

After deploying the frontend, go back to Railway and update `CORS_ORIGINS`:

```
CORS_ORIGINS=["https://your-project.vercel.app","https://chat.vernon.ca"]
```

---

### Post-Deployment Checklist

After both services are deployed, verify everything works:

- [ ] **Health check** — Visit `https://your-backend-url/api/health` and confirm `{"status":"ok"}`
- [ ] **Trigger crawl** — `POST /api/ingest` and wait for completion (check `/api/status`)
- [ ] **Test chat** — Open the frontend URL and ask "How do I pay my property taxes?"
- [ ] **Verify sources** — Confirm the response includes source links to vernon.ca pages
- [ ] **Test admin** — Open `/admin`, enter your API key, and verify the dashboard loads
- [ ] **Enable auto-recrawl** — Set `RECRAWL_ENABLED=true` on Railway so content stays fresh
- [ ] **Process council meetings** — In the admin dashboard, click "Discover Meetings" then "Process All"
- [ ] **Test embed widget** — Add the embed script to a test page (see [Embeddable Chat Widget](#embeddable-chat-widget))

---

## Admin Dashboard Guide

Access the admin dashboard at `https://your-frontend-url/admin`. You will be prompted to enter your `ADMIN_API_KEY`.

### Dashboard Overview

The main dashboard shows analytics for a configurable period (7, 30, 90 days, or 1 year):

- **Stats Cards** — Total conversations, total messages, average confidence score, and average response time
- **Hourly Chart** — Bar chart showing when users are most active (helps staff planning)
- **Topic Distribution** — Pie chart showing which departments get the most questions

### Top Questions

Shows the most frequently asked questions. Use this to:
- Identify common information needs
- Improve website content for frequently asked topics
- Spot trends in resident inquiries

### Unanswered Questions

Lists questions where the AI's confidence was below the threshold. Use this to:
- Identify gaps in website content that should be filled
- Find topics that need more detailed coverage on vernon.ca
- Discover new services residents are asking about

### Crawl Management

- **Knowledge Base Chunks** — Total number of text chunks in the vector store
- **Tracked Pages** — Number of unique web pages being tracked
- **Trigger Crawl** — Run an incremental crawl to pick up website changes
- **Full Recrawl** — Delete everything and re-crawl from scratch (use sparingly)

### Document Upload

Upload PDF documents directly to the knowledge base without crawling. Useful for:
- Internal policy documents
- Forms and applications
- Reports that aren't on the main website

### Council Meetings

See [Council Meeting Transcription](#council-meeting-transcription) below.

### Conversation Browser

Browse all chat sessions, view full conversation transcripts, and see user feedback (thumbs up/down). Useful for quality assurance and understanding how residents interact with the chatbot.

### Audit Log

Timestamped record of all system actions. Filter by action type:
- `chat_query` — Every chat interaction with confidence and topic
- `document_uploaded` — PDF uploads with file details
- `meetings_discovered` — Meeting discovery events
- `crawl_triggered` — Manual crawl triggers

---

## Council Meeting Transcription

The chatbot can automatically transcribe City of Vernon council meetings from the [eScribe portal](https://pub-vernon.escribemeetings.com), generate executive summaries, extract action items, and make meeting content searchable through the chatbot.

### How It Works

1. **Discovery** — The system queries the eScribe portal's calendar API to find all meetings with video recordings
2. **Audio Download** — For each meeting, ffmpeg extracts audio from the HLS video stream as 16kHz mono WAV
3. **Transcription** — faster-whisper (a local Whisper implementation) transcribes the audio on CPU
4. **Summarization** — Claude generates an executive summary and extracts action items (motions, assignments, deadlines)
5. **Indexing** — The transcription is chunked and stored in ChromaDB, making it searchable through the chatbot

### Processing Times

Processing time depends on meeting length and the Whisper model size:

| Model | Accuracy | Speed (per hour of audio) | RAM Usage |
|-------|----------|---------------------------|-----------|
| `tiny` | Basic | ~5 minutes | ~1 GB |
| `base` | Good | ~10 minutes | ~1.5 GB |
| `small` | Very good (recommended) | ~20-30 minutes | ~2.5 GB |
| `medium` | Excellent | ~45-60 minutes | ~5 GB |
| `large-v3` | Best | ~90+ minutes | ~10 GB |

> The `small` model is recommended for production use. It provides good accuracy with reasonable processing times on CPU.

### Using the Admin Interface

1. Open the admin dashboard and scroll to **Council Meetings**
2. Click **"Discover Meetings"** to scan the eScribe portal for available meetings
3. The table shows all discovered meetings with their status
4. Click **"Process All"** to start background processing of all pending meetings, or click **"Process"** next to an individual meeting
5. Monitor progress via the status bar that appears during processing
6. Once complete, expand a meeting to view its executive summary, action items, and transcription preview

### Status Indicators

| Status | Color | Meaning |
|--------|-------|---------|
| Pending | Gray | Discovered but not yet processed |
| Downloading | Blue | Audio being extracted from video stream |
| Transcribing | Yellow | Whisper is transcribing the audio |
| Summarizing | Purple | Claude is generating summary and action items |
| Indexing | Green (light) | Chunks being stored in ChromaDB |
| Complete | Green | Fully processed and searchable |
| Error | Red | Processing failed (click to see error details, can retry) |

### After Processing

Once meetings are processed, users can ask the chatbot questions like:
- "What was discussed at the last council meeting?"
- "Were there any motions about parking?"
- "What action items came out of the January council meeting?"

The topic routing system automatically detects council-related questions and prioritizes meeting transcription content in the response.

---

## Embeddable Chat Widget

Embed the chatbot on any website with a single script tag:

```html
<script
  src="https://your-frontend-url/embed.js"
  data-host="https://your-frontend-url"
  data-position="bottom-right"
  data-button-color="#2563eb"
  data-lang="en"
  data-width="400"
  data-height="600"
></script>
```

### Configuration Attributes

| Attribute | Description | Default |
|-----------|-------------|---------|
| `data-host` | URL of your frontend deployment | Auto-detected from script src |
| `data-position` | `bottom-right` or `bottom-left` | `bottom-right` |
| `data-button-color` | Hex color for the floating button | `#2563eb` (blue) |
| `data-lang` | Default language (`en` or `fr`) | `en` |
| `data-width` | Widget width in pixels | `400` |
| `data-height` | Widget height in pixels | `600` |

The widget renders a floating chat button that opens an iframe containing the full chat interface. It is self-contained and does not conflict with the host page's styles.

---

## API Reference

### Public Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check — returns `{"status": "ok"}` |
| `/api/status` | GET | Knowledge base stats (chunk count, tracked pages, crawl status) |
| `/api/suggestions` | GET | Suggested questions for the chat UI. Query param: `?language=en` |
| `/api/sessions` | POST | Create a new chat session. Query param: `?language=en` |
| `/api/sessions/{id}/messages` | GET | Retrieve message history for a session |
| `/api/chat` | POST | Send a message and receive an AI response. Body: `{"message": "...", "stream": true, "session_id": "...", "language": "en"}` |
| `/api/feedback` | POST | Submit feedback on a response. Body: `{"message_id": 1, "rating": 1, "comment": "..."}` |
| `/api/ingest` | POST | Trigger a website crawl. Body (optional): `{"url": "...", "full": false}` |
| `/api/ingest/documents` | POST | Upload a PDF document (requires `X-Admin-Key` header) |

### Admin Endpoints

All admin endpoints require the `X-Admin-Key` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/analytics/summary` | GET | Dashboard summary stats. Query: `?days=30` |
| `/api/admin/analytics/top-questions` | GET | Most asked questions. Query: `?days=30&limit=10` |
| `/api/admin/analytics/unanswered` | GET | Low-confidence questions. Query: `?days=30` |
| `/api/admin/analytics/hourly` | GET | Hourly message distribution. Query: `?days=7` |
| `/api/admin/analytics/topics` | GET | Topic distribution. Query: `?days=30` |
| `/api/admin/analytics/feedback` | GET | Feedback details. Query: `?days=30` |
| `/api/admin/conversations` | GET | List conversations. Query: `?page=1&per_page=20` |
| `/api/admin/conversations/{id}` | GET | Full conversation detail |
| `/api/admin/crawl-status` | GET | Current crawl and knowledge base status |
| `/api/admin/crawl/trigger` | POST | Trigger a crawl. Query: `?full=false` |
| `/api/admin/cache/clear` | POST | Clear the response cache |
| `/api/admin/documents` | GET | List uploaded PDF documents |
| `/api/admin/documents/{filename}` | DELETE | Remove a PDF from the knowledge base |
| `/api/admin/audit-logs` | GET | Audit log entries. Query: `?days=30&action=chat_query&page=1` |
| `/api/admin/meetings` | GET | List council meetings. Query: `?status=complete&page=1` |
| `/api/admin/meetings/processing-status` | GET | Current meeting processing status |
| `/api/admin/meetings/{id}` | GET | Meeting detail (summary, action items, transcription) |
| `/api/admin/meetings/discover` | POST | Discover meetings from eScribe portal |
| `/api/admin/meetings/process-all` | POST | Start processing all pending meetings |
| `/api/admin/meetings/{id}/process` | POST | Process a single meeting |

---

## Maintenance and Operations

### Keeping Content Fresh

**Automatic recrawl (recommended):**

Set these environment variables on Railway:
```
RECRAWL_ENABLED=true
RECRAWL_CRON_HOUR=2
```

This runs an incremental crawl daily at 2:00 AM. Only new and changed pages are re-indexed; removed pages are cleaned up automatically.

**Manual recrawl:**

Via the admin dashboard, click the "Trigger Crawl" button, or use the API:
```bash
curl -X POST https://your-backend-url/api/admin/crawl/trigger \
  -H "X-Admin-Key: your-admin-key"
```

For a full re-index (deletes everything and starts fresh):
```bash
curl -X POST "https://your-backend-url/api/admin/crawl/trigger?full=true" \
  -H "X-Admin-Key: your-admin-key"
```

### Data Retention

Conversations are automatically deleted after `DATA_RETENTION_DAYS` (default: 90 days). The purge job runs daily at 3:00 AM. This is not configurable by schedule, but the retention period is adjustable.

### Cache Management

The response cache reduces Anthropic API costs by serving identical questions from cache. To clear the cache (e.g., after a content update):

```bash
curl -X POST https://your-backend-url/api/admin/cache/clear \
  -H "X-Admin-Key: your-admin-key"
```

The cache also auto-invalidates after any crawl or document upload.

### Monitoring

- **Health check:** `GET /api/health` — returns `{"status": "ok"}` when the service is running
- **Status:** `GET /api/status` — returns knowledge base size, crawl status, cache stats, and LLM configuration status
- **Admin dashboard:** The analytics overview provides ongoing visibility into usage, confidence, and response times

### Updating the Knowledge Base

| Scenario | Action |
|----------|--------|
| Website content changed | Trigger an incremental crawl (auto-recrawl handles this) |
| New PDF to add | Upload via admin dashboard "Document Upload" section |
| New council meetings | Click "Discover Meetings" then "Process All" in admin |
| Major website redesign | Trigger a full recrawl to re-index everything |
| Remove incorrect content | Delete specific documents via admin, or full recrawl |

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "LLM not configured" | Missing `ANTHROPIC_API_KEY` | Set the environment variable and restart |
| Admin dashboard returns 403 | Wrong or missing admin key | Verify `ADMIN_API_KEY` matches in backend env and your browser |
| Crawl returns 0 pages | Target URL unreachable or blocked | Check `TARGET_URL`, ensure the site allows crawling |
| Low confidence on all answers | Knowledge base is empty | Trigger a crawl first with `POST /api/ingest` |
| Meeting processing fails at "downloading" | ffmpeg not installed | Ensure ffmpeg is in the Docker image (included in Dockerfile) |
| Meeting processing fails at "transcribing" | Insufficient memory for Whisper model | Try a smaller model: set `WHISPER_MODEL_SIZE=base` or `tiny` |
| Frontend shows "Failed to fetch" | CORS misconfigured | Update `CORS_ORIGINS` on Railway to include your frontend URL |
| Chat responses are slow | No cache, large knowledge base | Enable caching (default), consider reducing `TOP_K_RESULTS` |

### Updating Dependencies

```bash
# Backend
cd backend
pip install --upgrade -r requirements.txt

# Frontend
cd frontend
npm update
```

### Logs

On Railway, view logs in the Railway dashboard under your service's **Deployments** > **Logs** tab. Key log messages to watch for:

- `Vernon Chatbot backend started` — Successful startup
- `Auto-recrawl scheduled at 02:00` — Recrawl schedule confirmed
- `Scheduled recrawl complete: X pages` — Successful auto-recrawl
- `Successfully processed: Meeting Title` — Meeting transcription complete

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Uvicorn |
| AI | Claude (Anthropic API) via `anthropic` SDK |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector Store | ChromaDB |
| Database | SQLite via SQLAlchemy |
| Transcription | faster-whisper (CTranslate2, CPU int8) |
| Audio | ffmpeg (HLS stream extraction) |
| Scheduling | APScheduler |
| Charts | Recharts |
| Markdown | react-markdown |
| Rate Limiting | slowapi |
| Web Scraping | BeautifulSoup4, requests |
| PDF Parsing | pypdf |
