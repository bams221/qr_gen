import json
import logging
import os
import sys
import threading
import time
import uuid

import pika
from flask import Flask, request, jsonify, Response
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    return {"status": "ok"}

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
REQUEST_QUEUE = os.getenv("QR_REQUEST_QUEUE", "qr_requests")
RESULT_QUEUE = os.getenv("QR_RESULT_QUEUE", "qr_results")
SERVICE_NAME = "gateway"

TASKS = {}
TASKS_LOCK = threading.Lock()
CONSUMER_THREAD = None
CONSUMER_LOCK = threading.Lock()

PROCESSED_QR_CODES = 0
METRICS_LOCK = threading.Lock()

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "event": getattr(record, "event", record.msg),
            "message": record.getMessage(),
        }
        extra_fields = getattr(record, "extra_fields", {})
        payload.update(extra_fields)
        return json.dumps(payload, ensure_ascii=True)


logger = logging.getLogger(SERVICE_NAME)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_event(level, event, message, **fields):
    logger.log(level, message, extra={"event": event, "extra_fields": fields})


def _open_broker_channel():
    log_event(
        logging.INFO,
        "broker_connecting",
        "Opening RabbitMQ channel",
        broker_host=RABBITMQ_HOST,
        request_queue=REQUEST_QUEUE,
        result_queue=RESULT_QUEUE,
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=30)
    )
    channel = connection.channel()
    channel.queue_declare(queue=REQUEST_QUEUE, durable=True)
    channel.queue_declare(queue=RESULT_QUEUE, durable=True)
    return connection, channel


def _store_task(task_id, payload):
    with TASKS_LOCK:
        TASKS[task_id] = payload


def _get_task(task_id):
    with TASKS_LOCK:
        return TASKS.get(task_id)


def _increment_processed_qr_codes():
    global PROCESSED_QR_CODES
    with METRICS_LOCK:
        PROCESSED_QR_CODES += 1


def _get_processed_qr_codes():
    with METRICS_LOCK:
        return PROCESSED_QR_CODES


@app.route("/metrics")
def metrics():
    processed_count = _get_processed_qr_codes()
    body = (
        "# HELP qr_codes_processed_total Number of processed QR codes\n"
        "# TYPE qr_codes_processed_total counter\n"
        f"qr_codes_processed_total {processed_count}\n"
    )
    return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")


def consume_results_forever():
    while True:
        connection = None
        try:
            connection, channel = _open_broker_channel()
            log_event(logging.INFO, "result_consumer_ready", "Result consumer connected")

            def on_result(_channel, _method, _properties, body):
                now = time.time()
                payload = json.loads(body.decode("utf-8"))
                task_id = payload["task_id"]
                task_state = {
                    "status": payload["status"],
                    "updated_at": now,
                }
                if payload["status"] == "SUCCESS":
                    task_state["image_base64"] = payload["image_base64"]
                    _increment_processed_qr_codes()
                else:
                    task_state["error"] = payload.get("error", "Unknown worker error")

                _store_task(task_id, task_state)
                log_event(
                    logging.INFO,
                    "result_received",
                    "Received QR result from broker",
                    task_id=task_id,
                    status=payload["status"],
                )
                _channel.basic_ack(delivery_tag=_method.delivery_tag)

            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(queue=RESULT_QUEUE, on_message_callback=on_result)
            channel.start_consuming()
        except Exception as exc:
            log_event(
                logging.ERROR,
                "result_consumer_error",
                "Result consumer failed and will retry",
                error=str(exc),
            )
            time.sleep(2)
        finally:
            if connection and connection.is_open:
                connection.close()


def ensure_result_consumer_started():
    global CONSUMER_THREAD
    if app.config.get("TESTING"):
        return

    with CONSUMER_LOCK:
        if CONSUMER_THREAD and CONSUMER_THREAD.is_alive():
            return
        CONSUMER_THREAD = threading.Thread(target=consume_results_forever, daemon=True)
        CONSUMER_THREAD.start()
        log_event(logging.INFO, "result_consumer_started", "Started result consumer thread")

@app.route('/api/generate', methods=['POST'])
def generate_qr():
    data = request.json
    text = data.get('text') if data else None
    
    if not text:
        log_event(logging.WARNING, "generate_rejected", "QR generation request missing text")
        return jsonify({"error": "No text provided"}), 400
        
    try:
        ensure_result_consumer_started()
        task_id = str(uuid.uuid4())
        created_at = time.time()
        message = json.dumps({
            "task_id": task_id,
            "text": text,
            "created_at": created_at,
        })

        connection, channel = _open_broker_channel()
        try:
            channel.basic_publish(
                exchange="",
                routing_key=REQUEST_QUEUE,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            connection.close()

        _store_task(task_id, {"status": "PENDING", "created_at": created_at})
        log_event(
            logging.INFO,
            "request_published",
            "Published QR generation request",
            task_id=task_id,
            text_length=len(text),
            queue=REQUEST_QUEUE,
        )
        return jsonify({"task_id": task_id}), 202
    except Exception as e:
        log_event(
            logging.ERROR,
            "request_publish_failed",
            "Failed to publish QR generation request",
            error=str(e),
        )
        return jsonify({"error": str(e)}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
def check_status(task_id):
    ensure_result_consumer_started()
    task = _get_task(task_id)
    if not task:
        log_event(logging.WARNING, "status_missing", "Status requested for unknown task", task_id=task_id)
        return jsonify({"error": "Task not found"}), 404

    log_event(
        logging.INFO,
        "status_requested",
        "Status requested for task",
        task_id=task_id,
        status=task["status"],
    )
    response = {"status": task["status"]}
    if task["status"] == "SUCCESS":
        response["image_base64"] = task["image_base64"]
    if task["status"] == "FAILURE":
        response["error"] = task.get("error", "Unknown worker error")
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
