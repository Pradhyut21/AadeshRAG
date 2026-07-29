import os
import urllib.request
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def generate_rajasthan_circular_pdf():
    os.makedirs("./data/rajasthani", exist_ok=True)
    pdf_path = "./data/rajasthani/Mukhya_Mantri_Ayushman_Jeevan_Raksha_Yojana.pdf"
    font_path = "NotoSansDevanagari.ttf"

    if not os.path.exists(font_path):
        print("Downloading NotoSansDevanagari font...")
        urllib.request.urlretrieve(
            'https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf',
            font_path
        )

    pdfmetrics.registerFont(TTFont('NotoSansHindi', font_path))
    c = canvas.Canvas(pdf_path, pagesize=letter)

    p1_lines = [
        "राजस्थान सरकार - वित्त (नियम) विभाग",
        "क्रमांक: प.1(2)वित्त/नियम/2022                                     जयपुर, दिनांक: 06 जनवरी, 2022",
        "",
        ":: परिपत्र ::",
        "विषय: 'मुख्यमंत्री आयुष्मान जीवन रक्षा योजना' के संचालन एवं प्रोत्साहन राशि वितरण बाबत।",
        "",
        "राज्य सरकार द्वारा सड़क दुर्घटना में गंभीर रूप से घायल व्यक्तियों को समय पर अस्पताल पहुँचाकर",
        "उनकी जान बचाने वाले भले व्यक्तियों को प्रोत्साहित करने के उद्देश्य से",
        "'मुख्यमंत्री आयुष्मान जीवन रक्षा योजना' लागू की जाती है।",
        "",
        "1. उद्देश्य एवं कार्यक्षेत्र:",
        "यह योजना सम्पूर्ण राजस्थान राज्य में प्रभावी होगी। योजना का मुख्य उद्देश्य सड़क दुर्घटना में",
        "घायल व्यक्तियों को त्वरित चिकित्सा सहायता उपलब्ध कराकर मृत्यु दर में कमी लाना है।",
        "",
        "2. पात्रता:",
        "(1) राज्य की सीमा के भीतर सड़क दुर्घटना में घायल किसी भी व्यक्ति को अस्पताल पहुँचाने वाला",
        "कोई भी आम नागरिक (भला व्यक्ति) इस योजना का पात्र होगा।",
        "(2) दुर्घटना पीड़ित का स्वयं का संबंधी या ड्यूटी पर तैनात पुलिस कर्मी इस योजना हेतु पात्र नहीं होंगे।",
        "",
        "3. प्रोत्साहन राशि एवं सम्मान:",
        "(1) सड़क दुर्घटना में गंभीर घायल व्यक्ति को समय पर अस्पताल/आघात केंद्र पहुँचाने वाले प्रत्येक भले व्यक्ति को रू0 10000/- (रुपये दस हजार मात्र) की प्रोत्साहन राशि प्रदान की जाएगी।",
        "(2) प्रोत्साहन राशि के साथ-साथ राज्य सरकार द्वारा एक प्रशस्ति पत्र भी प्रदान किया जाएगा।",
        "",
        "4. समय-सीमा एवं पोर्टल प्रविष्टि:",
        "अस्पताल के प्रभारी चिकित्सा अधिकारी दुर्घटना पीड़ित को भर्ती करते ही 48 घंटे के भीतर संबंधित पोर्टल पर भले व्यक्ति का विवरण दर्ज करेंगे।",
        "",
        "5. पुलिस पूछताछ एवं उत्पीड़न का निषेध:",
        "माननीय उच्चतम न्यायालय के आदेशानुसार अस्पताल अथवा पुलिस द्वारा घायल को पहुँचाने वाले व्यक्ति पर नाम, पता बताने या गवाह बनने का कोई दबाव नहीं बनाया जाएगा।"
    ]

    p2_lines = [
        "6. आर्थिक सहायता का भुगतान:",
        "प्रोत्साहन राशि सीधे भले व्यक्ति के बैंक खाते में डीबीटी के माध्यम से हस्तांतरित की जाएगी।",
        "",
        "7. बजट प्रावधान एवं कोष:",
        "योजना हेतु आवश्यक बजट की व्यवस्था राजस्थान सड़क सुरक्षा कोष से की जाएगी।",
        "",
        "ANNEXURE-I",
        "अस्पताल एवं चिकित्सालयों हेतु दिशा-निर्देश:",
        "1. पीड़ित का पंजीकरण समय एवं स्थिति दर्ज करना।",
        "2. भले व्यक्ति का बैंक विवरण (यदि स्वैच्छिक रूप से दिया गया हो)।",
        "3. 48 घंटे के भीतर पोर्टल सत्यापन एवं अनुशंसा।",
        "",
        "ANNEXURE-II",
        "जिला स्तरीय निगरानी समिति:",
        "1. जिला कलेक्टर की अध्यक्षता में गठित समिति द्वारा योजना की समीक्षा।",
        "2. प्रत्येक माह प्राप्त प्रकरणों का निस्तारण एवं प्रोत्साहन वितरण।"
    ]

    # Draw Page 1
    c.setFont('NotoSansHindi', 10)
    y = 750
    for line in p1_lines:
        if line.strip():
            c.drawString(50, y, line)
        y -= 18
    c.showPage()

    # Draw Page 2
    c.setFont('NotoSansHindi', 10)
    y = 750
    for line in p2_lines:
        if line.strip():
            c.drawString(50, y, line)
        y -= 18
    c.showPage()

    c.save()
    print(f"Generated clean Devanagari PDF with ReportLab: {pdf_path}")

if __name__ == "__main__":
    generate_rajasthan_circular_pdf()
