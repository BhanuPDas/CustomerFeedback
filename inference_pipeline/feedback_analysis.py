from feedback_request_model import FeedbackRequest
from feedback_response_model import FeedbackResponse
from fastapi import FastAPI, HTTPException
import time
import torch
import json
import queue
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterHTTP,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Sentiment labels
sentiment_labels = {0: "Very Negative", 1: "Negative", 2: "Neutral", 3: "Positive", 4: "Very Positive"}
feedback_queue = queue.Queue()
OTLP_HTTP_ENDPOINT = os.environ.get(
    "OTLP_HTTP_ENDPOINT", "http://172.22.229.100:4318/v1/traces"
)

MODE = os.environ.get("MODE", "otlp-http")
TARGET_ONE_HOST = os.environ.get("TARGET_ONE_HOST", "inference-helper-service")
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "feedback-inference-service")

class FeedbackAnalysis:
    def __init__(self, app: FastAPI, new_data_file_local, logger, model, tokenizer, s3_client, s3_bucket, new_data_path, device):
        self.app = app
        self.new_data_file_local = new_data_file_local
        self.logger = logger
        self.model = model
        self.tokenizer = tokenizer
        self.s3_client = s3_client
        self.S3_BUCKET = s3_bucket
        self.NEW_DATA_PATH = new_data_path
        self.device = device
        self.initialize_routes()
        setting_jaeger(self.app)

    def initialize_routes(self):
        @self.app.post("/feedback/analyse", response_model=FeedbackResponse)
        def analyze(feedback:FeedbackRequest):
            return self.analyze(feedback)

        @self.app.get("/uploadInputFile")
        def upload_new_datafile():
            return self.upload_new_datafile()

    # Log new data to S3
    @staticmethod
    def create_new_input_file(feedback):
        new_data = {
            "text": feedback.text,
            "stars": feedback.stars
        }
        feedback_queue.put(json.dumps(new_data) + "\n")

    def write_to_file(self):
        self.logger.info(f"Write feedback requests if queue is not empty- {feedback_queue.empty()}")
        try:
            if not feedback_queue.empty():
                with open(self.new_data_file_local, "a") as f:
                    while not feedback_queue.empty():
                        f.write(feedback_queue.get())
        except Exception as ex:
            self.logger.error(f"write failed. {ex}", exc_info=True)

    # Calculate accuracy
    @staticmethod
    def calculate_accuracy(feedback_score):
        if 0 < feedback_score < 1.0:
            return feedback_score
        elif 1.0 <= feedback_score < 5.0:
            return feedback_score / 5.0
        else:
            return 1.0

    def analyze_feedback(self,feedback):
        self.logger.info("Starting inference for new feedback.")
        try:
            tokens = self.tokenizer.tokenize(feedback.text.lower())
            input_ids = self.tokenizer.convert_tokens_to_ids(tokens)
            inputs = torch.tensor([input_ids]).to(self.device)

            # Predict sentiment
            with torch.no_grad():
                outputs = self.model(inputs)
                predictions = torch.argmax(outputs.logits, dim=1).item()
                sentiment = sentiment_labels[predictions]

            # Feedback scoring based on stars
            stars_weight = feedback.stars / 5
            feedback_score = predictions + stars_weight

            # Accuracy
            accuracy = FeedbackAnalysis.calculate_accuracy(feedback_score)

            # Interpret overall sentiment
            if feedback_score <= 1:
                overall_sentiment = "Angry"
            elif feedback_score <= 2:
                overall_sentiment = "Disappointed"
            elif feedback_score <= 3:
                overall_sentiment = "Neutral"
            elif feedback_score <= 4:
                overall_sentiment = "Satisfied"
            else:
                overall_sentiment = "Happy"

            return sentiment, feedback_score, overall_sentiment, accuracy

        except Exception as e:
            self.logger.error("Error during inference.", exc_info=True)
            raise e

    def analyze(self, feedback):
        start = time.perf_counter()
        if feedback.stars < 1 or feedback.stars > 5:
            raise HTTPException(status_code=400, detail="Stars must be between 1 and 5")

        FeedbackAnalysis.create_new_input_file(feedback)
        pod_name = os.getenv("POD_NAME", "unknown_pod")

        # Perform inference and send response
        try:
            sentiment, feedback_score, overall_sentiment, accuracy = self.analyze_feedback(
                feedback)
            end = time.perf_counter()
            execution_time = (end - start) * 1000
            self.logger.info(f"Final Analysis: " +
                        f"Sentiment: {sentiment} " +
                        f"Overall sentiment: {overall_sentiment} " +
                        f"Feedback score: {round(feedback_score, 2)} " +
                        f"Accuracy: {round(accuracy, 2)} " +
                        f"Inference time: {round(execution_time, 2)} ")
            return FeedbackResponse(
                sentiment=overall_sentiment,
                feedback_score=round(feedback_score, 2),
                accuracy=round(accuracy, 2),
                inference_time=round(execution_time, 2),
                pod_name=pod_name
            )
        except Exception:
            self.logger.error("Failed to process feedback.", exc_info=True)
            raise HTTPException(status_code=500, detail="An error occurred during inference.")

    def upload_new_datafile(self):
        # Upload to S3
        try:
            self.write_to_file()
            self.s3_client.upload_file(self.new_data_file_local, self.S3_BUCKET, f"{self.NEW_DATA_PATH}inputFile.jsonl")
            self.logger.info("New feedback data uploaded to S3.")
        except Exception:
            self.logger.error("Failed to upload new feedback data to S3.", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to upload file.")

def setting_jaeger(app: FastAPI, log_correlation: bool = True) -> None:
    # set the tracer provider
    tracer = TracerProvider()
    trace.set_tracer_provider(tracer)
    if MODE == "otlp-http":
        tracer.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporterHTTP(endpoint=OTLP_HTTP_ENDPOINT))
        )
    if log_correlation:
        LoggingInstrumentor().instrument(set_logging_format=True)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer)