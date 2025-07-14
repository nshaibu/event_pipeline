from .sentiment_analysis_pipeline import SentimentAnalysisPipeline
from dotenv import load_dotenv
import os

load_dotenv()


pipeline = SentimentAnalysisPipeline(
    sender_email=os.getenv("SENDER_EMAIL"),
    sender_password=os.getenv("SENDER_PASSWORD"),
    recipient_email=os.getenv("RECIPIENT_EMAIL"),
)
pipeline.start()
