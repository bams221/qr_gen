import pytest
import app as gateway_app_module

app = gateway_app_module.app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_generate_qr_gateway_success(client, mocker):
    mock_channel = mocker.Mock()
    mock_connection = mocker.Mock()
    mocker.patch("app._open_broker_channel", return_value=(mock_connection, mock_channel))
    mocker.patch("app.uuid.uuid4", return_value="1234")
    mocker.patch("app.time.time", return_value=100.0)

    response = client.post('/api/generate', json={'text': 'Hello World'})

    assert response.status_code == 202
    assert response.json == {"task_id": "1234"}
    mock_channel.basic_publish.assert_called_once()
    mock_connection.close.assert_called_once()

def test_status_qr_gateway_success(client):
    gateway_app_module.TASKS = {"1234": {"status": "SUCCESS", "image_base64": "base64str"}}

    response = client.get('/api/status/1234')

    assert response.status_code == 200
    assert response.json == {"status": "SUCCESS", "image_base64": "base64str"}

def test_status_qr_gateway_missing_task(client):
    response = client.get('/api/status/missing')
    assert response.status_code == 404
