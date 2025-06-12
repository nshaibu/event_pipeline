import typing

from event_pipeline import EventBase
from event_pipeline.base import RetryPolicy
import logging
import httpx
from .custom_exception import InternalServerErrorException, BadRequestException
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor


class LoadData(EventBase):
    retry_policy = RetryPolicy(
        max_attempts=10,
        backoff_factor=0.005,
        max_backoff=100,
        retry_on_exceptions=[InternalServerErrorException, BadRequestException],
    )
    executor = ThreadPoolExecutor

    def process(self, url):
        logging.info("Fetching data from the api")
        self.stop_on_exception = True
        response = httpx.get(url)
        data = response.json()
        logging.info("Data fetched successfully")

        return True, data


class ProcessData(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].content

        user_post_counts = defaultdict(int)

        for post in previous_value:
            user_post_counts[post["userId"]] += 1

        # Convert to a regular dict and print results
        user_post_counts = dict(user_post_counts)
        return True, user_post_counts


class GraphData(EventBase):
    def process(self, *args, **kwargs):
        import matplotlib.pyplot as plt

        # Your data
        user_post_counts = self.previous_result[0].content

        # Extract keys and values
        user_ids = list(user_post_counts.keys())
        post_counts = list(user_post_counts.values())

        # Generate unique colors for each bar
        colors = plt.cm.get_cmap(
            "tab10", len(user_ids)
        )  # 'tab10' is a nice colormap with 10 distinct colors

        # Create the bar chart
        plt.figure(figsize=(10, 6))
        bars = plt.bar(
            user_ids, post_counts, color=[colors(i) for i in range(len(user_ids))]
        )

        # Add labels and title
        plt.xlabel("User ID")
        plt.ylabel("Number of Posts")
        plt.title("Number of Posts per User")
        plt.xticks(user_ids)  # Ensure all user IDs are shown on x-axis

        # Optional: Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height}",
                ha="center",
                va="bottom",
            )

        # Show plot
        plt.tight_layout()
        plt.show()

        return True, "Data visualized successfully"
