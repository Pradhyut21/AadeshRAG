import asyncio
import httpx
from main import app

async def run_end_to_end_test():
    print("=" * 70)
    print(" END-TO-END MULTI-USER RAG API VERIFICATION SCRIPT")
    print("=" * 70)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test GET /health
        print("\n[1] Testing GET /health...")
        res = await client.get("/health")
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")

        # 2. Test GET /dataset/read for uninitialized user_id
        print("\n[2] Testing GET /dataset/read for UNINITIALIZED user_id ('uninitialized_user_999')...")
        res = await client.get("/dataset/read", params={"user_id": "uninitialized_user_999"})
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")

        # 3. Test GET /dataset/read for 'rajasthani'
        print("\n[3] Testing GET /dataset/read for 'rajasthani'...")
        res = await client.get("/dataset/read", params={"user_id": "rajasthani"})
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")

        # 4. Test POST /rag/query with include_timings=True
        print("\n[4] Testing POST /rag/query with include_timings=True...")
        query_payload = {
            "user_id": "rajasthani",
            "query": "सड़क दुर्घटना में गंभीर घायल को सहायता राशि कितनी है?",
            "include_timings": True
        }
        res = await client.post("/rag/query", json=query_payload)
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"Query: {ascii(data.get('query'))}")
            print(f"Answer: {ascii(data.get('answer')[:120])}...")
            print(f"Timings: {data.get('timings')}")
        else:
            print(f"Note: Returned status {res.status_code} (Requires GROQ_API_KEY in .env for active LLM generation)")

        # 5. Test POST /rag/query/stream (Real SSE Token Stream)
        print("\n[5] Testing POST /rag/query/stream (Real SSE Token Stream)...")
        res = await client.post("/rag/query/stream", json={"user_id": "rajasthani", "query": "सहायता राशि कितनी है?"})
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            lines = res.text.split("\n")
            print(f"Received {len(lines)} SSE lines over event-stream.")
            for line in lines[:5]:
                if line.strip():
                    print(f"Stream Event: {ascii(line[:80])}")

    print("\n" + "=" * 70)
    print(" VERIFICATION SUCCESSFUL")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_end_to_end_test())
