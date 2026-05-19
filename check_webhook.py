import httpx

def test_local_webhook():
    url = "http://127.0.0.1:8000/webhook"
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "gayri_menkul",
        "hub.challenge": "1234567890"
    }
    
    try:
        print("Yerel Webhook test ediliyor (http://127.0.0.1:8000/webhook)...")
        with httpx.Client() as client:
            response = client.get(url, params=params)
            if response.status_code == 200 and response.text == "1234567890":
                print("[BASARILI] FastAPI sunucunuz Webhook dogrulamasini dogru sekilde yanitliyor.")
                print("Sorun ngrok linkinizde veya Meta paneline girdiginiz adreste olabilir.")
            else:
                print(f"[HATA] Sunucu yaniti ({response.status_code}): {response.text}")
    except httpx.ConnectError:
        print("[BAGLANTI HATASI] FastAPI sunucunuz calismiyor! Lutfen once 'py -m uvicorn src.main:app --reload' komutunu calistirin.")

if __name__ == "__main__":
    test_local_webhook()
