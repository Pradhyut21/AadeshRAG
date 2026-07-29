import pytest
from httpx import AsyncClient, ASGITransport
from main import app, vector_store
from pdf_parser import split_into_clauses, clean_ocr_text
from config import settings

has_groq_key = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here")

@pytest.fixture
def sample_pdf_text():
    return """
1. उद्देश्य एवं विस्तार:
राजस्थान सरकार द्वारा मुख्यमंत्री आयुष्मान जीवन रक्षा योजना लागू की गई है। इसके अंतर्गत सड़क दुर्घटना पीड़ितों को अस्पताल पहुँचाने वाले व्यक्ति (भले व्यक्ति) को प्रोत्साहन राशि दी जाएगी।

2. आर्थिक सहायता राशि:
सड़क दुर्घटना में गंभीर घायल व्यक्ति को समय पर अस्पताल पहुँचाने पर व्यक्ति को रू0 10000/- की प्रोत्साहन राशि एवं प्रशस्ति पत्र प्रदान किया जाएगा।

ANNEXURE-I
अस्पताल द्वारा 48 घंटे के भीतर पोर्टल पर प्रविष्टि दर्ज की जानी अनिवार्य है।
"""

def test_clean_ocr_text(sample_pdf_text):
    cleaned = clean_ocr_text(sample_pdf_text)
    assert "10000/-" in cleaned
    assert "ANNEXURE-I" in cleaned

def test_split_into_clauses(sample_pdf_text):
    clauses = split_into_clauses(sample_pdf_text)
    assert len(clauses) >= 2
    combined = " ".join(clauses)
    assert "10000/-" in combined

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "loaded_datasets" in data
    assert "llm_model" in data

@pytest.mark.asyncio
async def test_dataset_read_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/dataset/read", params={"user_id": "rajasthani"})
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "rajasthani"
    assert "status" in data
    assert "total_chunks" in data

@pytest.mark.asyncio
async def test_query_empty_bad_request():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/query", json={"user_id": "rajasthani", "query": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]

@pytest.mark.skipif(not has_groq_key, reason="GROQ_API_KEY not configured in .env - skipping live LLM integration test")
@pytest.mark.asyncio
async def test_rag_query_endpoint_schema():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/rag/query", json={"user_id": "rajasthani", "query": "सड़क दुर्घटना में कितनी सहायता राशि मिलती है?"})

    assert response.status_code == 200, f"Query failed: {response.text}"
    data = response.json()
    assert set(data.keys()) >= {"query", "answer", "context"}
    assert data["query"] == "सड़क दुर्घटना में कितनी सहायता राशि मिलती है?"
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert isinstance(data["context"], str)

@pytest.mark.skipif(not has_groq_key, reason="GROQ_API_KEY not configured in .env - skipping live LLM streaming test")
@pytest.mark.asyncio
async def test_rag_query_stream_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/rag/query/stream", json={"user_id": "rajasthani", "query": "प्रोत्साहन राशि कितनी है?"})
    
    assert response.status_code == 200
    events = [line for line in response.text.split("\n") if line.startswith("data:")]
    assert len(events) >= 5, "Real token streaming should yield metadata, multiple token deltas, and DONE events"
    assert "[Error:" not in response.text, f"Stream yielded API error event: {response.text}"
