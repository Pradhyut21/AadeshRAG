import os
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

queries = [
    "सड़क दुर्घटना में घायल व्यक्ति को अस्पताल पहुँचाने पर कितनी प्रोत्साहन राशि दी जाती है?",
    "प्रोत्साहन राशि के अलावा राज्य सरकार द्वारा क्या सम्मान दिया जाता है?",
    "दुर्घटना के कितने समय के भीतर अस्पताल के प्रभारी चिकित्सा अधिकारी को पोर्टल पर विवरण दर्ज करना होता है?",
    "योजना के अंतर्गत प्रोत्साहन राशि का भुगतान किस माध्यम से किया जाएगा?",
    "क्या घायल व्यक्ति का स्वयं का संबंधी या ड्यूटी पर तैनात पुलिसकर्मी प्रोत्साहन राशि का पात्र होगा?",
    "क्या अस्पताल या पुलिस द्वारा घायल को पहुँचाने वाले व्यक्ति पर नाम-पता बताने का दबाव बनाया जा सकता है?",
    "योजना का मुख्य उद्देश्य क्या है और यह कहाँ प्रभावी होगी?",
    "योजना हेतु आवश्यक बजट की व्यवस्था किस कोष से की जाएगी?",
    "ANNEXURE-I के अनुसार अस्पताल एवं चिकित्सालयों के लिए क्या दिशा-निर्देश हैं?",
    "ANNEXURE-II के तहत जिला स्तरीय निगरानी समिति की अध्यक्षता कौन करता है?"
]

def generate_pdf_report():
    print("Executing 10 queries against live RAG API...")
    results = []
    
    with httpx.Client(timeout=30.0) as client:
        for idx, q in enumerate(queries, 1):
            print(f"[{idx}/10] Querying query #{idx}...")
            resp = client.post(
                "http://127.0.0.1:8080/rag/query",
                json={"user_id": "rajasthani", "query": q, "include_timings": True}
            )
            if resp.status_code == 200:
                results.append(resp.json())
            else:
                results.append({
                    "query": q,
                    "answer": f"[Error {resp.status_code}]",
                    "context": "",
                    "timings": {"total_ms": 0}
                })

    output_pdf = "rag_queries_evaluation_report.pdf"
    font_path = "NotoSansDevanagari.ttf"
    pdfmetrics.registerFont(TTFont('NotoSansHindi', font_path))

    c = canvas.Canvas(output_pdf, pagesize=letter)
    page_width, page_height = letter

    def draw_header(title):
        c.setFont('NotoSansHindi', 13)
        c.setFillColorRGB(0.1, 0.2, 0.5)
        c.drawString(40, page_height - 35, title)
        c.setStrokeColorRGB(0.2, 0.4, 0.8)
        c.setLineWidth(1)
        c.line(40, page_height - 42, page_width - 40, page_height - 42)

    y = page_height - 55
    draw_header("Multi-User RAG API - 10 Queries Evaluation Report")

    for idx, res in enumerate(results, 1):
        if y < 140:
            c.showPage()
            draw_header("Multi-User RAG API - Evaluation Report (Contd.)")
            y = page_height - 55

        # Query Title Box
        c.setFont('NotoSansHindi', 9.5)
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setLineWidth(0.5)
        c.setFillColorRGB(0.94, 0.96, 1.0)
        c.rect(40, y - 18, page_width - 80, 22, fill=True, stroke=True)
        c.setFillColorRGB(0, 0.25, 0.6)
        
        q_text = f"Q{idx}: {res['query']}"
        c.drawString(45, y - 13, q_text)
        y -= 28

        # Grounded Answer
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont('NotoSansHindi', 9)
        ans_lines = res['answer'].split('\n')
        c.drawString(45, y, "Grounded Answer:")
        y -= 14

        for al in ans_lines:
            if not al.strip():
                continue
            words = al.split(' ')
            line_buf = ""
            for w in words:
                if len(line_buf) + len(w) > 85:
                    c.drawString(55, y, line_buf)
                    y -= 13
                    line_buf = w + " "
                    if y < 60:
                        c.showPage()
                        draw_header("Multi-User RAG API - Evaluation Report (Contd.)")
                        y = page_height - 55
                else:
                    line_buf += w + " "
            if line_buf.strip():
                c.drawString(55, y, line_buf)
                y -= 13

        # Timings
        timings = res.get("timings", {})
        t_str = f"Execution Timings: Retrieval: {timings.get('retrieval_ms', 0)}ms | Generation: {timings.get('generation_ms', 0)}ms | Total: {timings.get('total_ms', 0)}ms"
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont('NotoSansHindi', 8)
        c.drawString(55, y, t_str)
        y -= 22

    c.save()
    print(f"Successfully generated PDF report: {os.path.abspath(output_pdf)}")

if __name__ == "__main__":
    generate_pdf_report()
