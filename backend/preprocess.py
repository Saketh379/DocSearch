# backend/preprocess.py
import os
import nltk
import re
import string
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

try:
    _ = stopwords.words('english')
except Exception:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')
    nltk.download('omw-1.4')

STOPWORDS = set(stopwords.words('english'))
LEMMATIZER = WordNetLemmatizer()

def preprocess(text):
    text = text.lower()
    tokens = re.compile(r"\b[0-9a-zA-Z']+\b").findall(text)
    tokens = [t for t in tokens if t not in STOPWORDS]
    tokens = [LEMMATIZER.lemmatize(t) for t in tokens]
    return " ".join(tokens)
