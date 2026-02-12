How to Run Locally
1. Backend:


cd backend
cp .env.example .env          # Edit with your ANTHROPIC_API_KEY and TARGET_URL
pip install -r requirements.txt
uvicorn app.main:app --reload
2. Frontend:


cd frontend
npm install
npm run dev
3. Ingest your website:


curl -X POST http://localhost:8000/api/ingest
Or pass a URL directly:


curl -X POST http://localhost:8000/api/ingest -H "Content-Type: application/json" -d '{"url": "https://yoursite.com"}'
4. Open http://localhost:3000 and start chatting.

API Endpoints
Endpoint	Method	Description
/api/health	GET	Health check
/api/status	GET	Knowledge base stats
/api/ingest	POST	Crawl & ingest website
/api/chat	POST	Send message, get AI response (SSE streaming)
Key Features
Web scraper crawls your site following internal links, respecting depth/page limits
RAG pipeline retrieves relevant chunks and grounds Claude's answers in your content
SSE streaming — answers appear token-by-token in real time
Source citations — every answer includes links to the source pages
System prompt ensures the bot only answers from your content and suggests human handoff when unsure