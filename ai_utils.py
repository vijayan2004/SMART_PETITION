import re
import nltk
import PyPDF2
from textblob import TextBlob
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib
import os

# Ensure NLTK resources are downloaded
nltk.download('punkt')
nltk.download('vader_lexicon')

# Load Sentiment Analyzer
sia = SentimentIntensityAnalyzer()

# Define categories and officer assignments based on keywords
CATEGORY_KEYWORDS = {
    "Healthcare": {
        "keywords": ["hospital", "medicine", "doctor", "health", "treatment", "medical"],
        "officer": "Health Officer"
    },
    "Education": {
        "keywords": ["school", "college", "university", "teacher", "student", "education"],
        "officer": "Education Officer"
    },
    "Environment": {
        "keywords": ["climate", "pollution", "forest", "green", "sustainability", "nature"],
        "officer": "Environment Officer"
    },
    "Governance": {
        "keywords": ["policy", "government", "law", "regulation", "administration"],
        "officer": "Government Administrator"
    },
    "Agriculture": {
        "keywords": ["farm", "farmer", "crop", "agriculture", "irrigation", "pesticide"],
        "officer": "Agriculture Officer"
    },
    "Panchayat Raj": {
        "keywords": ["village", "panchayat", "rural", "development", "local"],
        "officer": "Panchayat Officer"
    },
    "Revenue Administration": {
        "keywords": ["tax", "land", "property", "assessment", "valuation"],
        "officer": "Revenue Officer"
    }
}

# Load or train a simple sentiment model
MODEL_FILE = "sentiment_model.pkl"

def train_sentiment_model():
    """Trains a simple sentiment analysis model and saves it."""
    data = [
        ("This petition is very urgent and needs immediate attention!", "positive"),
        ("We demand better healthcare facilities for rural areas.", "positive"),
        ("The system is completely broken and inefficient.", "negative"),
        ("There is no proper response from the authorities.", "negative"),
        ("We appreciate the efforts taken by the administration.", "positive"),
        ("No action has been taken despite multiple complaints.", "negative")
    ]

    texts, labels = zip(*data)
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(texts)
    y = [1 if label == "positive" else 0 for label in labels]

    model = LogisticRegression()
    model.fit(X, y)

    joblib.dump((vectorizer, model), MODEL_FILE)

# Train the model if it does not exist
if not os.path.exists(MODEL_FILE):
    train_sentiment_model()

def categorize_petition(title, description):
    """Categorizes a petition based on title and description, assigns priority and officer."""
    text = ((title or "") + " " + (description or "")).strip().lower()

    for category, details in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in details["keywords"]):
            officer_assigned = details["officer"]

            # Determine priority level using sentiment analysis
            sentiment, _ = analyze_sentiment(text)
            priority = "High" if sentiment == "Negative" else "Medium"
            return category, priority, officer_assigned

    return "General", "Low", "General Officer"

def analyze_sentiment(text):
    """Performs sentiment analysis using VADER and ML model."""
    if not text:  # Ensure text is not None
        return "Neutral", 0.0

    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    
    vader_score = sia.polarity_scores(text)['compound']
    
    vectorizer, model = joblib.load(MODEL_FILE)
    text_vector = vectorizer.transform([text])
    prediction = model.predict(text_vector)[0]

    # Combine sentiment results
    if polarity > 0.2 and vader_score > 0.2 and prediction == 1:
        return "Positive", polarity
    elif polarity < -0.2 or vader_score < -0.2 or prediction == 0:
        return "Negative", polarity
    else:
        return "Neutral", polarity

def predict_petition_success(title, description):
    """Predicts petition success likelihood based on sentiment and word count."""
    title = title if title else ""
    description = description if description else ""

    text = title + " " + description

    sentiment, polarity = analyze_sentiment(text)
    word_count = len(re.findall(r'\w+', text))

    if sentiment == "Positive" and polarity > 0.2 and word_count > 50:
        return "High"
    elif sentiment == "Negative" and polarity < -0.2 and word_count < 20:
        return "Low"
    else:
        return "Medium"

# ---------------------------
# File Handling - Extract Text from PDF and TXT Files
# ---------------------------

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = ""
    try:
        with open(pdf_path, "rb") as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text.strip()

def extract_text_from_txt(txt_path):
    """Extracts text from a TXT file."""
    text = ""
    try:
        with open(txt_path, "r", encoding="utf-8") as txt_file:
            text = txt_file.read()
    except Exception as e:
        print(f"Error reading TXT file: {e}")
    return text.strip()
