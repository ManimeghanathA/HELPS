from datetime import datetime
from weather_pipeline import WeatherPipeline

pipeline = WeatherPipeline()
record = pipeline.fetch_weather(12.9698, 79.1559, datetime(2026, 9, 4, 10, 30))

import json
print(json.dumps(record, indent=2))