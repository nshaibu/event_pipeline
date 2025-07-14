from .sentiment_analysis_pipeline import SentimentAnalysisPipeline
from dotenv import load_dotenv

load_dotenv()


pipeline = SentimentAnalysisPipeline()
pipeline.start()
