import pytest
from app import process_message

def test_qr_worker_processes_message_success(mocker):
    mock_channel = mocker.Mock()
    mock_method = mocker.Mock(delivery_tag="delivery-tag")
    mocker.patch("app.create_qr_payload", return_value="encoded-image")

    process_message(
        mock_channel,
        mock_method,
        None,
        b'{"task_id":"mock_task_id","text":"Mocked Flow"}',
    )

    mock_channel.basic_publish.assert_called_once()
    mock_channel.basic_ack.assert_called_once_with(delivery_tag="delivery-tag")
