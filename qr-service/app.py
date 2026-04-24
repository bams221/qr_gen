import io
import base64
import json
import logging
import os
import sys
import time
import qrcode
import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
REQUEST_QUEUE = os.getenv("QR_REQUEST_QUEUE", "qr_requests")
RESULT_QUEUE = os.getenv("QR_RESULT_QUEUE", "qr_results")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
SERVICE_NAME = "qr-worker"


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


def create_qr_payload(text: str):
    """Generates a QR code image asynchronously, returning base64 string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    time.sleep(5)  # Simulate long processing time
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    return base64.b64encode(img_buffer.getvalue()).decode('utf-8')

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


def process_message(channel, method, _properties, body):
    payload = json.loads(body.decode("utf-8"))
    task_id = payload["task_id"]
    text = payload["text"]
    status = "SUCCESS"
    result_payload = {"task_id": task_id}

    log_event(
        logging.INFO,
        "message_consumed",
        "Consumed QR generation request",
        task_id=task_id,
        text_length=len(text),
        queue=REQUEST_QUEUE,
    )
    try:
        result_payload["image_base64"] = create_qr_payload(text)
        result_payload["status"] = status
        log_event(
            logging.INFO,
            "qr_generated",
            "Generated QR code successfully",
            task_id=task_id,
            status=status,
        )
    except Exception as exc:
        status = "FAILURE"
        result_payload["status"] = status
        result_payload["error"] = str(exc)
        log_event(
            logging.ERROR,
            "qr_generation_failed",
            "QR generation failed",
            task_id=task_id,
            error=str(exc),
        )

    channel.basic_publish(
        exchange="",
        routing_key=RESULT_QUEUE,
        body=json.dumps(result_payload),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    log_event(
        logging.INFO,
        "result_published",
        "Published QR result",
        task_id=task_id,
        status=status,
        queue=RESULT_QUEUE,
    )
    channel.basic_ack(delivery_tag=method.delivery_tag)


def run_worker():
    log_event(logging.INFO, "metrics_server_started", "Prometheus metrics server started", port=METRICS_PORT)
    while True:
        connection = None
        try:
            connection, channel = _open_broker_channel()
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=REQUEST_QUEUE, on_message_callback=process_message)
            log_event(logging.INFO, "worker_ready", "Worker is consuming QR requests")
            channel.start_consuming()
        except Exception as exc:
            log_event(
                logging.ERROR,
                "worker_loop_failed",
                "Worker loop failed and will retry",
                error=str(exc),
            )
            time.sleep(2)
        finally:
            if connection and connection.is_open:
                connection.close()

if __name__ == '__main__':
    run_worker()
